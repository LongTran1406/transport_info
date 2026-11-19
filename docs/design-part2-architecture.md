# Design (Part 2): Architecture and MVP

Nov 19, 2026 · @long

## Overview

The whole pipeline runs on one Hetzner VM with Docker Compose for about A$15–22 a month, covering every Sydney bus route. This part turns the problem in Part 1 (`ml-design-document.md`) and the data and ML design (`design.md`) into an architecture for the seven pipeline stages, from ingestion to the public demo.

Guiding principles:

- **Right tool for the data size.** About 2 million rows an hour fits on one machine, so the design uses DuckDB and Polars, not Spark, and micro-batch polling, not Kafka or Flink.
- **Always-on loops run in their own containers; batch work runs in Airflow.** The poller and the scorer run every 30–60 s, so they are long-running containers with `restart: always`. Airflow runs jobs that start and finish.
- **Code and models ship separately.** Code goes through CI/CD as Docker images. Models go through the MLflow registry and are promoted by alias.
- **One feature definition for training and serving.** Feast builds point-in-time training sets offline and serves the same features online.
- **Cost-capped and portable.** All storage goes through the S3 API (MinIO), so moving to a real cloud bucket only means changing the endpoint.

## Data flow

&#91;embedded content: data flow · 7 stages on one Hetzner VM\]

Feeds move down from TfNSW to visitors. Feast hands the same features to training (MLflow, on the right) and to the every-minute scorer, and the scorer loads whichever model carries the `@production` alias. Not drawn: the scorer's sampled prediction log goes back to MinIO for Stage 6, and GitHub Actions deploys every container over SSH (Stage 4).

## Stage 1: Ingestion

An always-on poller container pulls both realtime feeds every 30 s. Airflow orchestrates everything that starts and finishes.

- **Poller:** a Python script in its own Docker container with `restart: always`. Every 30 s it pulls VehiclePositions and TripUpdates, keeps only Sydney Buses Network routes, and writes gzipped protobuf to the `bronze` bucket. Each object is named by its feed timestamp, so duplicates are easy to spot.
- **Resilience:** the API key comes from an environment variable. A failed pull is logged and skipped, never a crash. Docker restarts the container within seconds if it does die.
- **Static GTFS:** a daily Airflow DAG downloads the schedule, cleans it into Silver, and rebuilds the list of Sydney `route_id`s the poller keeps.
- **Hourly Airflow DAG:** checks Bronze freshness (fails and emails if no new object for 5 min), then runs Bronze → Silver → Gold.
- **Quota:** 2 feeds × 2,880 pulls a day = 5,760 requests a day, well under the 60,000 a day and 5 a second limits.

**Why not Airflow for the 15–30 s loop:** an hourly Airflow run that loops for an hour leaves gaps at every handover, loses up to an hour of data when it crashes, and holds a worker slot all the time. Realtime data can't be backfilled, so gaps mean lost labels.

**Change from `design.md`:** the pull interval is 30 s instead of 15 s, within Part 1's "every 30–60 s". The trade-off is label precision: more buses pass a stop between snapshots, so more labels use `SEQUENCE_PASSED` interpolation (about ±15 s) instead of `STOPPED_AT` (about ±7 s). Every example keeps its label method.

## Stage 2: Storage and features

All three layers live in MinIO on about 100 GB of the VM's disk and are kept for 30 days. Gold is split into source tables that Feast joins, not one pre-joined table.

### Layers

| Layer | Format | Content | Built by | Retention |
| --- | --- | --- | --- | --- |
| Bronze | Gzipped protobuf | Raw feed pulls, Sydney routes only | Poller, every 30 s | 30 days |
| Silver | Parquet, partitioned by `date=` / `hour=` | Cleaned tables following the `design.md` schema, exact duplicate snapshots removed | Airflow hourly (Polars) | 30 days |
| Gold | Parquet, partitioned by `date=` | Feast source tables and labels (below) | Airflow hourly and daily (DuckDB) | 30 days |

- **Object store:** MinIO (S3 API), from a pinned community image such as `pgsty/minio`, with buckets `bronze`, `silver` and `gold`. Retention is a MinIO lifecycle rule, not a delete task.
- **Disk:** MinIO and Postgres are bind-mounted from host folders (`/srv/data/minio`, `/srv/data/postgres`), so `docker compose down -v` can't delete them.
- **Transforms:** Polars for Bronze → Silver (protobuf parsing and cleaning). DuckDB for Silver → Gold, including the `ASOF JOIN` for "latest observation at or before T".
- **Querying:** DuckDB views in a small `catalog.duckdb` file over `read_parquet(…, hive_partitioning = true)`, read from MinIO through the `httpfs` extension.

### Gold tables

| Table | Key | Refreshed | Columns |
| --- | --- | --- | --- |
| `trip_state` | `trip_id` + ingestion timestamp (TTL about 5 min) | Every 30 s | `route_id`, `current_stop_sequence`, `current_delay_seconds` |
| `trip_stop_schedule` | `trip_id` + `stop_id` | Daily, from static GTFS | `service_date`, `stop_sequence`, `scheduled_arrival` |
| `route_stop_history` | `route_id` + `stop_id` + hour + weekday | Daily, from earlier labels only | `hist_avg_delay`, `n_obs` |
| `labels` | `trip_id` + `stop_id` + `prediction_time` | Hourly | `route_id`, `sched_hour`, `sched_weekday`, `arrival_delay_seconds`, `label_method`, `tfnsw_predicted_delay` |

- **On-demand features**, computed by the same Python functions in training and serving, never stored: `minutes_until_scheduled_arrival`, `stops_ahead`, `trip_started`, `time_of_day`, `day_of_week`.
- **Event timestamps are ingestion times**, when the poller received the data, so a feature can never use data that arrived after the prediction time.
- A trip that hasn't started has no `trip_state` rows. Feast returns NULL within the TTL, so `trip_started = 0` falls out naturally.
- `tfnsw_predicted_delay` is the benchmark column and is never a feature.

### Sizing

Measured on 18 Nov 2026, 22:45–23:05 (off-peak), full network:

| Measure | Value |
| --- | --- |
| TripUpdates per pull, raw | 1,002–1,206 KB |
| TripUpdates per pull, gzipped | 280–333 KB |
| Trips per snapshot | 868–1,023 |
| Route IDs active at 23:05 | 229 |
| Rows per pull, flattened | about 26,000 |

The static schedule has about 5,900 route IDs, but 5,074 are school buses. The Sydney Buses Network has 565. Assuming Sydney is about 60% of active trips, one month comes to roughly 17–35 GB of Bronze TripUpdates, 2–4 GB of VehiclePositions (a guess, not measured), 6–40 GB of Silver, a few GB of Gold and about 10 GB of working space. That is 35–90 GB in total, so the design plans for about 100 GB of disk.

**Not used, and why:** Spark (about 2 million rows an hour fits on one node), Delta or Iceberg (append-only tables with one writer; date folders give idempotent reruns and simple retention).

## Stage 3: Training

Models train on point-in-time training sets from Feast and are tracked and registered in MLflow.

- **Feature store:** Feast. The offline store is Gold Parquet on MinIO, read through an S3 endpoint override. The online store is Redis.
- **Training set:** `get_historical_features()` on the `labels` table returns one row per label with every feature as of its `prediction_time`.
- **Models:** linear regression as the simple model, then XGBoost. The target is `arrival_delay_seconds`, so this is regression.
- **Baselines** from Part 1 §3: (a) schedule only, (b) current delay persists, (c) TfNSW. Every model is compared against all three.
- **Split:** by service date, 70/15/15. With 30 days of Gold that is about 21/4.5/4.5 days, and all rows from one service date stay in one split.
- **Metrics** from Part 1 §4: MAE and % of predictions within 1 and 2 min, reported separately for trips not yet started and running trips, and by stops ahead.
- **MLflow:** a tracking server with Postgres as its database and MinIO for artifacts. Each run logs parameters, metrics, the Gold date range and the Feast feature service name. The best model is registered as `bus-delay` and marked with the `@production` alias.
- **Where it runs:** an Airflow `retrain` DAG on the same VM (see Stage 6).

**Deferred:** Kafka and Flink streaming features. The data arrives as one poll every 30 s, which is already micro-batch, and both need several GB of RAM.

## Stage 4: CI/CD

GitHub Actions tests and builds every change, and deploys `main` to the VM over SSH. Models are not part of this path.

1. **CI, on every push and pull request:** lint, unit tests (cleaning rules, feature functions, on-demand features), `feast apply` validation, and Docker builds.
2. **Images:** five of our own: `poller`, `airflow` (with the DAGs), `api`, `scorer` and `streamlit`. MinIO, Postgres, Redis, Caddy, Prometheus, Grafana and node\_exporter use pinned public images.
3. **Registry:** Docker Hub. Images are tagged with the git commit SHA (plus `latest`), so a rollback means redeploying the previous SHA.
4. **CD, after CI passes on `main`:** Actions SSHes into the VM as a dedicated `deploy` user, with a key stored in GitHub Secrets, and runs `docker compose pull && docker compose up -d` with the SHA tags just built.
5. **Post-deploy check:** the workflow calls `/health` and fails visibly if the new version doesn't come up.

**Code and models ship separately.** Images contain code only. The scorer loads `models:/bus-delay@production` from MLflow, so promoting or rolling back a model means moving the alias, with no rebuild. Each model carries its Feast feature service name, and the scorer refuses a model that doesn't match its own.

## Stage 5: Serving

Predictions are precomputed every minute and stored in Redis. The FastAPI endpoint only reads them, which keeps p95 latency far under 200 ms.

- **Scorer:** its own container with `restart: always`. Every 60 s it takes all active trips and trips starting in the next 24 h on Sydney routes, reads their features from Feast's online store, scores them in **one batch XGBoost call**, and writes the results to Redis.
- **Prediction log:** the scorer also appends a sample of served predictions to MinIO as Parquet. Stage 6 joins it with labels once buses arrive.
- **FastAPI:**
  - `GET /predictions?route=…` and a per-trip variant. Each stop returns `scheduled_time`, `model_delay`, `tfnsw_delay` and `model_version`.
  - `GET /health` for the Stage 4 deploy check.
- **Not public:** the Streamlit page reaches the API inside the Docker network (`http://api:8000`). Caddy is the only public entry point, with HTTPS and a basic rate limit.

The TfNSW number is shown beside ours for display. Both are scored against the real delay later, in Stage 3 offline and Stage 6 live.

## Stage 6: Monitoring

Airflow, Evidently and MLflow watch the model. Prometheus and Grafana watch the services. Retraining is triggered by performance, and a new model goes live only if it beats the current one.

### ML monitoring

- **Daily `monitoring` DAG:**
  - **Data drift:** Evidently compares the last 24 h of served features against the training-set reference.
  - **Performance:** joins the prediction log with labels and compares live MAE with the production model's test MAE. It also tracks TfNSW's live MAE, to tell a bad day for everyone from a problem with our model.
  - Logs metrics and the Evidently HTML report to MLflow.
- **Retraining trigger:** live MAE more than X% worse than test MAE for N days in a row. Data drift alone only warns. The trigger emails and runs the `retrain` DAG.
- **`retrain` DAG:** trains a challenger on the latest 30 days, compares it with production on the same recent days, and moves `@production` only if the challenger wins.
- **Version pin:** Evidently's API has changed a lot between releases, so its version is pinned.

### Service monitoring

| Source | Metrics |
| --- | --- |
| API | Request count, p95 latency, errors |
| Scorer | Last successful run, run duration, freshness, coverage |
| Poller | Last successful pull, error count |
| node\_exporter | Disk, CPU, RAM |

- **Grafana alert rules, by email:** p95 above 200 ms, freshness above 2 min, coverage below 90%, disk above 80% (warning) or 90% (critical), checking both the OS disk and the data volume.
- Prometheus keeps about 15 days. Grafana sits behind Caddy with a login.

## Stage 7: Demo

A public Streamlit page proves the two claims from Part 1: predictions before a trip starts, and a benchmark against TfNSW.

- **Live view:** a route selector and a map or stop list. Each upcoming arrival shows scheduled time, our prediction and TfNSW's. It refreshes every 60 s with `st.fragment(run_every=60)`, and `st.cache_data(ttl=60)` means all visitors share one API call a minute.
- **"Before it starts" view:** predicted delays for trips that haven't started, where TfNSW only shows the timetable.
- **Scoreboard:** yesterday's MAE for our model, TfNSW and schedule-only, by segment, read from the monitoring DAG's output.
- **Footer:** TfNSW Open Data attribution.
- **Possible upgrade:** rebuild the page in React if the map feels limited. The API stays the same.

**README:** a one-line pitch with the live link and a GIF; a Mermaid architecture diagram; the results table against baselines (a), (b) and (c); key decisions linking to `DECISIONS.md`; `docker compose up` instructions; CI badges; limitations and future work.

## Infrastructure and cost

Everything runs on one Hetzner Cloud CX33 in the EU (4 vCPU, 8 GB RAM, about 80 GB disk) for about A$15–22 a month, with a Hetzner cost alert by email.

### Why Hetzner EU

| Option | Approx. monthly cost | Why not chosen |
| --- | --- | --- |
| Azure VM (B2s) + ADLS Gen2, Australia East | A$55–65 in month 1, rising as storage grows | The VM alone is about US$39 a month |
| Cheap VM outside Azure + ADLS Gen2 | About US$12 + US$25–70 egress | Hourly jobs read Bronze back out, so egress is paid on every byte |
| Sydney VPS with 4 GB (Vultr, DigitalOcean, Linode) | US$20–24 | Same specs cost about twice as much; 80 GB disk |
| **Hetzner CX33, EU (chosen)** | **A$15–22** | Server is far from Sydney users |

Ingestion doesn't care where the server is. The cost of the EU location is slower page loads from Sydney, which Cloudflare caching can hide later.

### Cost breakdown

| Item | EUR / month | Note |
| --- | --- | --- |
| CX33 server | about 8.50 | After Hetzner's June 2026 price increase |
| Primary IPv4 | 0.50 |  |
| Extra volume, only if needed | 0–4.40 | 0.044 per GB; added if measurements show the 80 GB disk is too small |
| **Total** | **about 9–13.40** | About A$15–22 at 1 EUR ≈ 1.65 AUD, excluding tax |

Data lives in host folders (`/srv/data`) bind-mounted into the containers. If an extra volume is needed, it is attached, mounted at `/srv/data`, and nothing else changes.

### Billing alert

- Hetzner Console → **Usage** lets you set an email alert when costs pass a limit ([Hetzner docs](https://docs.hetzner.com/cloud/billing/faq/)).
- Set two alerts: **€15** (above the expected €9–13.40, so it fires only on something unexpected) and **€25** (something is clearly wrong).
- Each server's bill is capped at its monthly price, so the risk is extra resources left running, such as a test server or an old snapshot. A powered-off server is still billed until it is deleted.

### Containers and memory

| Container | Role | RAM (estimate) |
| --- | --- | --- |
| Airflow (scheduler, web server; LocalExecutor) | Batch DAGs, including training | 1.5–2 GB, plus 1–2 GB while training |
| Postgres | Airflow, MLflow and Feast metadata | 200–300 MB |
| MinIO | Bronze, Silver, Gold, MLflow artifacts, prediction log | 200–400 MB |
| MLflow | Tracking server and model registry | 200–300 MB |
| Redis | Feast online store and precomputed predictions | Under 100 MB |
| Poller | Feed ingestion every 30 s | 100–200 MB |
| Scorer | Batch scoring every 60 s | 300–500 MB |
| API | FastAPI, internal only | 150–300 MB |
| Streamlit | Public demo page | 200–300 MB |
| Caddy | HTTPS, rate limit | Under 50 MB |
| Prometheus, Grafana, node\_exporter | Service monitoring | 300–550 MB |

Steady state is roughly 3.5–5.5 GB, with training on top. These are estimates to replace with `docker stats` once the stack runs. The LocalExecutor for Airflow is an assumption: it runs tasks on the same machine with no extra broker.

## MVP scope

The MVP includes all seven stages, running live on every Sydney Buses Network route. Some extras are deferred so the core pipeline ships first.

|  | Items |
| --- | --- |
| **In** | Poller and Airflow ingestion; MinIO medallion layers; Feast with Redis; linear regression and XGBoost in MLflow; GitHub Actions CI and SSH deploy; scorer and FastAPI; Evidently drift and performance retraining; Prometheus and Grafana; Streamlit page and README |
| **Deferred** | Kafka and Flink streaming features; React frontend; off-server backup; retention beyond 30 days; Delta Lake on Gold; Cloudflare caching |
| **Out** (from Part 1) | Trains, ferries, light rail, journey planning, replacement services; also school, regional and temporary bus routes |

## Risks and open items

| Risk | Impact | Mitigation |
| --- | --- | --- |
| MinIO community edition archived (Feb 2026) | No upstream security fixes | Pinned community build; any S3-compatible store works by changing the endpoint |
| One VM, no off-server copy | Disk or account loss deletes up to 30 days of data | Manual snapshot before risky changes; bind mounts protect against `down -v` |
| 30-day retention on all layers | At most about 21 training days; no reprocessing older data | Retention is one config value; extend later |
| 8 GB RAM shared by about 14 containers | Training could run out of memory | Measure real usage once running; move training off-box if needed |
| 30 s pulls | Lower label precision | Track `label_method`; evaluate label quality separately |
| Server in the EU | Slower page loads from Sydney | Cloudflare caching (deferred) |
| Feast reading Parquet from MinIO | Most likely integration snag | Test the S3 endpoint override early |

**Open items:**

- [ ] Measure VehiclePositions size, a weekday peak-hour run, and the Parquet and zstd tests, to decide whether the 80 GB disk needs an extra volume
- [ ] Keep `trip_state` fresh in Redis: Airflow materialisation every 1–2 min, or a push from the poller
- [ ] Feast registry: in Postgres or as a file in MinIO
- [ ] Training sample density for `labels` (for example, one prediction time every 5 min per trip)
- [ ] Retraining thresholds X% and N days, once daily MAE variation is known
- [ ] Domain for HTTPS: a cheap paid domain or a free subdomain
- [ ] Exact TfNSW Open Data attribution wording

# Sydney Transport Insight

## 1. Problem statement
Many Sydney commuters rely on buses, whose arrival times vary with traffic and demand.
Transport for NSW (TfNSW) publishes live predicted delays, but only once a bus is running;
before a trip starts, it shows only the timetable. This system predicts the arrival delay
(actual minus scheduled arrival time, in seconds) at each stop for any bus trip on the
chosen routes, both trips in progress and trips starting within the next 24 hours.
Predictions refresh every 1 minute, are shown on a live map, and are benchmarked
against TfNSW.

**Scope (MVP):** Sydney buses only; 3-5 busy routes (chosen after EDA).
**Out of scope:** trains, ferries, light rail, journey planning, replacement services.

## 2. Data
- GTFS static timetable: scheduled times, stops, routes
- GTFS-realtime TripUpdates (TfNSW predictions per upcoming stop) + VehiclePositions
- Ground truth: snapshot the feed every 30-60 s; the actual delay at a stop is the last
  reported delay before that stop drops off the trip's update list
- Collection runs continuously from 19 Nov 2026: real-time data cannot be backfilled
  (check whether TfNSW offers a historical archive)

## 3. Baselines
- (a) Schedule only: predict 0 delay
- (b) Current delay persists to every later stop (running trips only)
- (c) TfNSW: its live predicted delay for running trips; effectively the schedule
  before a trip starts (the main competitor)

## 4. Metrics
Model metrics are reported separately for **trips not yet started** and **running trips**,
and by stops ahead.

| Metric | Type | Compared with | Target |
|---|---|---|---|
| MAE of arrival delay (s) | Model, primary | (a), (b), (c) | See success tiers |
| % predictions within 1 min / 2 min | Model, secondary | (c) | Higher than (c) |
| p95 prediction API latency | Service | n/a | < 200 ms |
| Freshness (feed update to prediction available) | Service | n/a | < 2 min |
| Coverage (% active and upcoming trips on chosen routes with a prediction) | Service | n/a | > 90% |

## 5. Success tiers
- **Must:** pipeline runs live; MAE lower than (a) on trips not yet started and lower
  than (b) on running trips
- **Should:** MAE within 15% of (c) on running trips, plus error analysis of where (c) is weak
- **Stretch:** MAE lower than (c) on at least one segment of running trips
  (peak hours, a route, or far-ahead stops)

## 6. Model approach (decided)
One model for all trips, with a "trip started" input; inputs only available for running trips (current delay, stops ahead, vehicle position) are left missing for future trips.
TfNSW's predictions are not an input: TfNSW is the benchmark.
Reason: one clear story and a clean head-to-head comparison; covers the pre-trip gap
TfNSW leaves. Split into two models only if evaluation shows one segment suffers.
Recorded in DECISIONS.md.
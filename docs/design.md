# Design (Part 1): Data and ML problem
See [problem statement](ml-design-document.md)

## 1. Data sources
| Feed | Format | Endpoint | Update freq | Pull freq | Limits |
|---|---|---|---|---|---|
| Static GTFS (Bus Schedule) | ZIP (CSV) | https://api.transport.nsw.gov.au/v1/gtfs/schedule/buses | 1 day | 1 day | 60000 requests/day for all request |
| Vehicle Positions (Buses) | Protobuf | https://api.transport.nsw.gov.au/v1/gtfs/vehiclepos/buses | 15s | 15s | 60000 requests/day for all request |
| Trip Updates (Buses) | Protobuf | https://api.transport.nsw.gov.au/v1/gtfs/realtime/buses | 15s | 15s | 60000 requests/day for all request |

According to TfNSW's Open Data developer documentation, the default Bronze plan provides:
- Daily API quota: 60,000 requests/day
- Rate limit: 5 requests/second

## 2. Schema

### Raw tables

#### Static GTFS (Bus Schedule)

**API:** `GET /v1/gtfs/schedule/buses`

**Table: `agency`**

Stores information about transport agencies operating bus services.

| Column | Data type | Description |
|---|---|---|
| `agency_id` | STRING | Unique identifier for the transport agency (e.g. `7057`, `2448`). |
| `agency_name` | STRING | Name of the transport agency (e.g. `CDC NSW R4`, `Hunter Valley Buses`). |
| `agency_url` | STRING | Official website of the transport agency (e.g. `http://transportnsw.info`). |
| `agency_timezone` | STRING | Timezone used by the agency (e.g. `Australia/Sydney`). |
| `agency_lang` | STRING | Primary language used by the agency (e.g. `EN`). |
| `agency_phone` | STRING | Contact phone number of the agency (e.g. empty if not provided). |

**Table: `routes`**

Stores information about bus routes, including route identifiers, route names, route types and display colours.

| Column | Data type | Description |
|---|---|---|
| `route_id` | STRING | Unique identifier for a bus route (e.g. `2447_160`). |
| `agency_id` | STRING | Identifier of the transport agency operating the route (e.g. `2447`). |
| `route_short_name` | STRING | Short route name or number displayed to passengers (e.g. `160`, `161`). |
| `route_long_name` | STRING | Full name describing the route's origin and destination (e.g. `Cessnock to Newcastle`). |
| `route_desc` | STRING | Additional description of the route or service (e.g. `Hunter Buses Network`). |
| `route_type` | STRING | Transport mode classification (e.g. `700` for bus). |
| `route_color` | STRING | Background colour used to display the route in hexadecimal format (e.g. `00B5EF`). |
| `route_text_color` | STRING | Text colour used when displaying the route in hexadecimal format (e.g. `FFFFFF`). |

**Primary key:** `route_id`

**Table: `trips`**

Stores individual scheduled trips associated with bus routes and service calendars.

| Column | Data type | Description |
|---|---|---|
| `route_id` | STRING | Identifier of the route operated by the trip (e.g. `2449_130`). |
| `service_id` | STRING | Identifier linking the trip to its operating schedule (e.g. `32`, `61`). |
| `trip_id` | STRING | Unique identifier for an individual scheduled trip (e.g. `1012281`). |
| `shape_id` | STRING | Identifier linking the trip to its geographical route shape (e.g. `80047`). |
| `trip_headsign` | STRING | Destination displayed to passengers (e.g. `Nelson Bay`). |
| `direction_id` | STRING | Direction of travel for the trip (e.g. `0`). |
| `block_id` | STRING | Identifier grouping trips operated by the same vehicle (e.g. empty if not provided). |
| `wheelchair_accessible` | STRING | Indicates wheelchair accessibility (e.g. `1`). |
| `trip_note` | STRING | Additional notes about the trip (e.g. empty if not provided). |
| `route_direction` | STRING | Description of the route direction (e.g. `Newcastle to Fingal Bay via Gan Gan Rd`). |

**Primary key:** `trip_id`

**Table: `stop_times`**

Stores scheduled arrival and departure times for each stop along an individual trip.

| Column | Data type | Description |
|---|---|---|
| `trip_id` | STRING | Identifier of the scheduled trip (e.g. `1012281`). |
| `arrival_time` | STRING | Scheduled arrival time at the stop (e.g. `06:50:00`). |
| `departure_time` | STRING | Scheduled departure time from the stop (e.g. `06:50:32`). |
| `stop_id` | STRING | Identifier of the bus stop (e.g. `231660`). |
| `stop_sequence` | STRING | Order in which the stop appears along the trip (e.g. `1`, `2`, `3`). |
| `stop_headsign` | STRING | Additional destination information displayed at the stop (e.g. empty if not provided). |
| `pickup_type` | STRING | Indicates the passenger pickup method (e.g. `0`). |
| `drop_off_type` | STRING | Indicates the passenger drop-off method (e.g. `0`). |
| `shape_dist_traveled` | STRING | Distance travelled along the route shape (e.g. `363`). |
| `timepoint` | STRING | Indicates whether the scheduled time is an exact timepoint (e.g. `1`). |
| `stop_note` | STRING | Additional notes about the stop (e.g. empty if not provided). |

**Primary key:** Composite key (`trip_id`, `stop_sequence`)

**Table: `stops`**

Stores information about bus stops, including their names, geographical coordinates and accessibility information.

| Column | Data type | Description |
|---|---|---|
| `stop_id` | STRING | Unique identifier for a bus stop (e.g. `20002`). |
| `stop_name` | STRING | Name or location description of the bus stop (e.g. `Circular Quay, Alfred St, Stand B`). |
| `stop_lat` | STRING | Latitude coordinate of the bus stop (e.g. `-33.861592`). |
| `stop_lon` | STRING | Longitude coordinate of the bus stop (e.g. `151.211932`). |
| `location_type` | STRING | Classification of the stop location (e.g. empty for a regular stop). |
| `parent_station` | STRING | Identifier of the parent station or location (e.g. empty if not provided). |
| `wheelchair_boarding` | STRING | Indicates wheelchair boarding accessibility (e.g. `1`). |
| `platform_code` | STRING | Platform identifier associated with the stop (e.g. empty if not provided). |

**Primary key:** `stop_id`

**Table: `shapes`**

Stores geographical coordinates that define the physical path followed by a bus trip.

| Column | Data type | Description |
|---|---|---|
| `shape_id` | STRING | Identifier of the geographical route shape (e.g. `1464`). |
| `shape_pt_lat` | STRING | Latitude coordinate of a point along the route (e.g. `-33.6786866`). |
| `shape_pt_lon` | STRING | Longitude coordinate of a point along the route (e.g. `150.8605086`). |
| `shape_pt_sequence` | STRING | Order of the geographical point along the route (e.g. `1`, `2`, `3`). |
| `shape_dist_traveled` | STRING | Distance travelled along the route shape up to that point (e.g. `54`). |

**Primary key:** Composite key (`shape_id`, `shape_pt_sequence`)

**Table: `calendar`**

Stores the regular operating schedule for each service, including the days of the week and the validity period.

| Column | Data type | Description |
|---|---|---|
| `service_id` | STRING | Unique identifier for a service schedule (e.g. `1`, `2`, `3`). |
| `monday` | STRING | Indicates whether the service operates on Monday (e.g. `1` = operates, `0` = does not operate). |
| `tuesday` | STRING | Indicates whether the service operates on Tuesday (e.g. `1` = operates, `0` = does not operate). |
| `wednesday` | STRING | Indicates whether the service operates on Wednesday (e.g. `1` = operates, `0` = does not operate). |
| `thursday` | STRING | Indicates whether the service operates on Thursday (e.g. `1` = operates, `0` = does not operate). |
| `friday` | STRING | Indicates whether the service operates on Friday (e.g. `1` = operates, `0` = does not operate). |
| `saturday` | STRING | Indicates whether the service operates on Saturday (e.g. `1` = operates, `0` = does not operate). |
| `sunday` | STRING | Indicates whether the service operates on Sunday (e.g. `1` = operates, `0` = does not operate). |
| `start_date` | STRING | First date on which the service schedule is valid (e.g. `20261117`). |
| `end_date` | STRING | Last date on which the service schedule is valid (e.g. `20270913`). |

**Primary key:** `service_id`

**Table: `calendar_dates`**

Stores exceptions to regular service schedules, specifying additional or removed operating dates.

| Column | Data type | Description |
|---|---|---|
| `service_id` | STRING | Identifier of the affected service schedule (e.g. `1`, `3`). |
| `date` | STRING | Date on which the service exception applies (e.g. `20261225`). |
| `exception_type` | STRING | Type of service exception (e.g. `1` = service added, `2` = service removed). |

**Primary key:** Composite key (`service_id`, `date`)

**Table: `notes`**

Stores additional service notes and operational information associated with the bus schedule.

| Column | Data type | Description |
|---|---|---|
| `note_id` | STRING | Unique identifier for a service note (e.g. `8`, `23`, `26`). |
| `note_text` | STRING | Text describing service changes or operational instructions (e.g. `Operates on school days only`). |

**Primary key:** `note_id`

#### Real-time GTFS (Bus Vehicle Positions)

**API:** `GET /v1/gtfs/vehiclepos/buses`

**Message: `VehiclePosition`**

Stores real-time information about bus locations, movement and occupancy.

| Field | Data type | Description |
|---|---|---|
| `trip` | TripDescriptor | Information identifying the scheduled trip (e.g. `trip_id`, `route_id`). |
| `vehicle` | VehicleDescriptor | Information identifying the bus (e.g. vehicle ID, label, license plate). |
| `position` | Position | Geographical position of the bus (e.g. latitude, longitude, bearing, speed). |
| `current_stop_sequence` | UINT32 | Sequence number of the bus's current stop (e.g. `5`). |
| `stop_id` | STRING | Identifier of the current bus stop (e.g. `225616`). |
| `current_status` | VehicleStopStatus | Current status of the bus relative to its stop (e.g. `IN_TRANSIT_TO`). |
| `timestamp` | UINT64 | Unix timestamp indicating when the vehicle information was recorded (e.g. `1794980841`). |
| `congestion_level` | CongestionLevel | Current traffic congestion level (e.g. `UNKNOWN_CONGESTION_LEVEL`). |
| `occupancy_status` | OccupancyStatus | Current passenger occupancy level (e.g. `MANY_SEATS_AVAILABLE`). |
| `occupancy_percentage` | UINT32 | Estimated passenger occupancy percentage (e.g. `50`). |
| `multi_carriage_details` | MultiCarriageDetails | Occupancy information for individual carriages (e.g. carriage-level details if provided). |

#### Real-time GTFS (Bus Trip Updates)

**API:** `GET /v1/gtfs/realtime/buses`

**Message: `TripUpdate`**

Stores real-time updates about scheduled bus trips, including arrival and departure delays at individual stops.

| Field | Data type | Description |
|---|---|---|
| `trip` | TripDescriptor | Information identifying the scheduled trip (e.g. `trip_id`, `route_id`, `start_time`). |
| `vehicle` | VehicleDescriptor | Information identifying the bus operating the trip (e.g. vehicle ID, label, license plate). |
| `stop_time_update` | StopTimeUpdate | List of real-time updates for individual stops (e.g. stop sequence, stop ID, arrival and departure delays). |
| `timestamp` | UINT64 | Unix timestamp indicating when the trip update was recorded (e.g. `1794981060`). |
| `delay` | INT32 | Overall delay for the trip in seconds (e.g. `198`). |
| `trip_properties` | TripProperties | Additional properties associated with the trip (e.g. trip start date and other trip information). |

### Cleaned tables
Note: We use the GTFS Schedule & GTFS Realtime TfNSW Implementation Specification as a reference in the process of validating and defining constraints


#### agency

| Column | Data type | Nullable | Constraints and cleaning rules |
|---|---|---|---|
| `agency_id` | STRING | No | Primary key; must be unique and non-null. Trim whitespace and preserve as a string. |
| `agency_name` | STRING | No | Required by GTFS and TfNSW. Must not be empty. Trim whitespace. |
| `agency_url` | STRING | No | Required by GTFS and TfNSW. Must contain a valid URL. Trim whitespace. |
| `agency_timezone` | STRING | No | Required by GTFS and TfNSW. Must be a valid IANA timezone, e.g. `Australia/Sydney`. |
| `agency_lang` | STRING | No | Required by TfNSW. Validate against the specified language code; expected value is `EN`. |
| `agency_phone` | STRING | Yes | Optional. Trim whitespace and preserve as a string, including country codes and leading zeros. |

**Additional cleaning rules:**

- Convert empty or whitespace-only values to NULL before validation.
- Do not cast `agency_id` to an integer.
- Validate that `agency_id` values are unique.
- Validate that `agency_timezone` contains a recognised IANA timezone.
- If a required column is missing from the API response, fail schema validation.
- If an optional column is missing, add it with NULL values.
- Quarantine records with missing required values rather than inventing replacements.


#### routes

| Column | Data type | Nullable | Constraints and cleaning rules |
|---|---|---|---|
| `route_id` | STRING | No | Primary key; must be unique and non-null. Trim whitespace and preserve as a string. |
| `agency_id` | STRING | No | Foreign key referencing `agency.agency_id`. Trim whitespace and preserve as a string. |
| `route_short_name` | STRING | No | Maximum 4 characters according to TfNSW specification. Preserve original case. |
| `route_long_name` | STRING | No | Must not be empty. Preserve original name and case. |
| `route_desc` | STRING | No | Must not be empty. Must identify the TfNSW Wayfinding network. |
| `route_type` | INT | No | Must be a valid standard or extended GTFS route type supported by TfNSW. |
| `route_color` | STRING | No | Must be a six-character hexadecimal colour code. Validate against TfNSW requirements. |
| `route_text_color` | STRING | No | Must be a six-character hexadecimal colour code. Validate against TfNSW requirements. |

**Additional cleaning rules:**

- Convert empty or whitespace-only values to NULL before validation.
- Do not cast identifier columns to integers.
- Do not restrict `route_type` to values 0–7 because the feed contains extended values such as `700`.
- Preserve source identifiers even if their format differs from the specification's examples.
- Validate foreign-key integrity between `routes.agency_id` and `agency.agency_id`.

#### trips

| Column | Data type | Nullable | Constraints and cleaning rules |
|---|---|---|---|
| `route_id` | STRING | No | Foreign key referencing `routes.route_id`. Must match an existing route. |
| `service_id` | STRING | No | Must reference a valid service defined in `calendar` or `calendar_dates`. |
| `trip_id` | STRING | No | Primary key; must be unique and non-null. Preserve as a string. |
| `shape_id` | STRING | No | Foreign key referencing `shapes.shape_id`. Must match an existing shape. |
| `trip_headsign` | STRING | No | Must not be empty; maximum 18 characters. Preserve original case. |
| `direction_id` | INT | No | Only `0` (outbound) or `1` (inbound). Loop services are represented as `1`. |
| `block_id` | STRING | No | Required by TfNSW. Preserve as a string and validate against the feed's identifier conventions. |
| `wheelchair_accessible` | INT | No | Only `1` or `2`, as specified by TfNSW. |
| `trip_note` | STRING | Yes | Foreign key referencing `notes.note_id` when provided. Empty is allowed when a trip has no note. |
| `route_direction` | STRING | No | Passenger-facing description of the route direction. Must align with TfNSW Wayfinding requirements. |

**Additional cleaning rules:**

- Convert empty or whitespace-only values to NULL before validation.
- Preserve all identifier columns as STRING; do not cast them to integers.
- Validate foreign-key relationships with `routes`, `calendar`, `calendar_dates`, `shapes`, and `notes`.
- Validate `trip_id` uniqueness.
- Reject or quarantine records with missing required values or invalid domain values.
- Allow NULL in `trip_note` when no note applies.


#### stop_times

| Column | Data type | Nullable | Constraints and cleaning rules |
|---|---|---|---|
| `trip_id` | STRING | No | Foreign key referencing `trips.trip_id`. Must match an existing trip. |
| `arrival_time` | STRING | No | Must follow `HH:MM:SS` format. Supports times beyond 24 hours, e.g. `25:25:10`. |
| `departure_time` | STRING | No | Must follow `HH:MM:SS` format. Supports times beyond 24 hours. |
| `stop_id` | STRING | No | Foreign key referencing `stops.stop_id`. Must match an existing stop. |
| `stop_sequence` | INT | No | Must be positive and increase in chronological stop order within each trip. |
| `stop_headsign` | STRING | Yes | Maximum 18 characters. Use when the passenger-facing headsign changes between stops. |
| `pickup_type` | INT | No | Valid values: `0`, `1`, `2`, `3`. Follow GTFS pickup rules. |
| `drop_off_type` | INT | No | Valid values: `0`, `1`, `2`, `3`. Follow GTFS drop-off rules. |
| `shape_dist_traveled` | DOUBLE | No | Must be non-negative and use consistent distance units along the trip. |
| `timepoint` | INT | No | `0` = approximate time; `1` = exact time. |
| `stop_note` | STRING | Yes | Foreign key referencing `notes.note_id` when provided. Referenced note must not exceed 150 characters. |

**Additional cleaning rules:**

- Convert empty or whitespace-only values to NULL before validation.
- Enforce composite uniqueness on (`trip_id`, `stop_sequence`).
- Validate foreign-key relationships with `trips`, `stops`, and `notes`.
- Preserve times beyond 24 hours; do not cast directly to conventional SQL TIME.
- Validate that stop sequences and scheduled times progress chronologically within each trip.
- Quarantine records with missing required values or invalid domain values.


#### stops

| Column | Data type | Nullable | Constraints and cleaning rules |
|---|---|---|---|
| `stop_id` | STRING | No | Primary key; must be unique and non-null. Preserve as a string. |
| `stop_name` | STRING | No | Must not be empty. Trim whitespace and preserve original case. |
| `stop_lat` | DOUBLE | No | Must be numeric and between -90 and 90 degrees. |
| `stop_lon` | DOUBLE | No | Must be numeric and between -180 and 180 degrees. |
| `location_type` | INT | No | Valid values: `0`, `1`, `2`, `3`, `4`. |
| `parent_station` | STRING | Yes | Foreign key referencing `stops.stop_id` when provided. Must reference a valid parent station. |
| `wheelchair_boarding` | INT | Yes | Valid values: `0`, `1`, `2`. |
| `platform_code` | STRING | Yes | Trim whitespace and preserve platform identifiers as strings. |

**Additional cleaning rules:**

- Convert empty or whitespace-only values to NULL before validation.
- Preserve `stop_id` and `parent_station` as STRING.
- Validate uniqueness of `stop_id`.
- Validate latitude and longitude ranges.
- Validate `location_type` and `wheelchair_boarding` against their allowed values.
- Validate parent station references and prevent circular parent relationships.
- Investigate coordinates outside the expected NSW operating area rather than automatically deleting them.
- Quarantine records with missing required values or invalid domain values.


#### shapes

| Column | Data type | Nullable | Constraints and cleaning rules |
|---|---|---|---|
| `shape_id` | STRING | No | Must not be empty. Referenced by `trips.shape_id`. |
| `shape_pt_lat` | DOUBLE | No | Must be numeric and between -90 and 90 degrees. |
| `shape_pt_lon` | DOUBLE | No | Must be numeric and between -180 and 180 degrees. |
| `shape_pt_sequence` | INT | No | Must be non-negative and unique within each shape. Must increase in point order. |
| `shape_dist_traveled` | DOUBLE | Yes | Must be non-negative and non-decreasing within each shape when provided. |

**Additional cleaning rules:**

- Convert empty or whitespace-only values to NULL before validation.
- Enforce composite uniqueness on (`shape_id`, `shape_pt_sequence`).
- Preserve `shape_id` as STRING.
- Validate latitude and longitude ranges.
- Sort coordinate points by `shape_pt_sequence` when reconstructing a shape.
- Validate that `shape_dist_traveled` does not decrease within a shape when provided.
- Validate that every `trips.shape_id` references an existing shape.
- Investigate coordinates outside the expected NSW operating area rather than automatically deleting them.
- Quarantine records with invalid coordinates or missing required values.


#### calendar

| Column | Data type | Nullable | Constraints and cleaning rules |
|---|---|---|---|
| `service_id` | STRING | No | Primary key; must be unique and non-null. Preserve as a string. |
| `monday` | INT | No | Boolean flag; only `0` or `1`. |
| `tuesday` | INT | No | Boolean flag; only `0` or `1`. |
| `wednesday` | INT | No | Boolean flag; only `0` or `1`. |
| `thursday` | INT | No | Boolean flag; only `0` or `1`. |
| `friday` | INT | No | Boolean flag; only `0` or `1`. |
| `saturday` | INT | No | Boolean flag; only `0` or `1`. |
| `sunday` | INT | No | Boolean flag; only `0` or `1`. |
| `start_date` | DATE | No | Parse source format `YYYYMMDD` into DATE. Must be a valid date. |
| `end_date` | DATE | No | Parse source format `YYYYMMDD` into DATE. Must be greater than or equal to `start_date`. |

**Additional cleaning rules:**

- Convert empty or whitespace-only values to NULL before validation.
- Preserve `service_id` as STRING.
- Validate weekday flags against `0` and `1`.
- Parse dates from `YYYYMMDD` into DATE.
- Validate that `start_date` is less than or equal to `end_date`.
- Validate uniqueness of `service_id`.
- Validate service references from `trips.service_id`.
- Quarantine records with missing required values or invalid domain values.


#### calendar_dates

| Column | Data type | Nullable | Constraints and cleaning rules |
|---|---|---|---|
| `service_id` | STRING | No | References a valid service defined in `calendar` or `calendar_dates`. Must not be empty. |
| `date` | DATE | No | Parse source format `YYYYMMDD` into DATE. Must be a valid date. |
| `exception_type` | INT | No | Only `1` (service added) or `2` (service removed). |

**Additional cleaning rules:**

- Convert empty or whitespace-only values to NULL before validation.
- Preserve `service_id` as STRING.
- Parse `date` from `YYYYMMDD` into DATE.
- Enforce composite uniqueness on (`service_id`, `date`).
- Validate `exception_type` against `1` and `2`.
- Validate service references against the combined service definitions in `calendar` and `calendar_dates`.
- Apply exceptions as overrides to the regular weekly schedule.
- Quarantine records with missing required values or invalid domain values.


#### notes

| Column | Data type | Nullable | Constraints and cleaning rules |
|---|---|---|---|
| `note_id` | STRING | No | Primary key; must be unique and non-null. Preserve as a string. |
| `note_text` | STRING | No | Must not be empty. Trim leading and trailing whitespace; preserve original wording. |

**Additional cleaning rules:**

- Convert empty or whitespace-only values to NULL before validation.
- Preserve `note_id` as STRING.
- Validate uniqueness of `note_id`.
- Validate references from `trips.trip_note` and `stop_times.stop_note` against `notes.note_id`.
- Preserve the original note wording and meaningful punctuation.
- Quarantine records with missing required values or duplicate identifiers.


#### vehicle_positions

| Column | Data type | Nullable | Constraints and cleaning rules |
|---|---|---|---|
| `entity_id` | STRING | No | Extract from `FeedEntity.id`. Must be traceable to the source providing system. |
| `vehicle_id` | STRING | No | Extract from `VehiclePosition.vehicle.id`. Identifies the individual vehicle; preserve as STRING. |
| `vehicle_label` | STRING | Yes | Extract from `VehiclePosition.vehicle.label`. Passenger-visible vehicle identifier, where available. |
| `license_plate` | STRING | Yes | Extract from `VehiclePosition.vehicle.license_plate`. Vehicle registration, where available. |
| `trip_id` | STRING | No | Extract from `VehiclePosition.trip.trip_id`. Must match `trips.trip_id`, except for ADDED trips. |
| `route_id` | STRING | No | Extract from `VehiclePosition.trip.route_id`. Must match `routes.route_id`. |
| `direction_id` | INT | No | Extract from `VehiclePosition.trip.direction_id`. Valid values: 0 or 1. For scheduled trips, derive from `trips.direction_id` when missing; required for ADDED trips. |
| `start_date` | DATE | No | Extract from `VehiclePosition.trip.start_date`. Parse `YYYYMMDD` into DATE. |
| `start_time` | STRING | No | Extract from `VehiclePosition.trip.start_time`. Preserve GTFS time format. |
| `schedule_relationship` | STRING | No | Extract from `VehiclePosition.trip.schedule_relationship`. Validate against TfNSW-supported values, including `SCHEDULED`, `ADDED`, `CANCELED` and `REPLACEMENT`. |
| `latitude` | FLOAT | No | Extract from `VehiclePosition.position.latitude`. Must be between -90 and 90; source precision must be at least 6 decimal places. |
| `longitude` | FLOAT | No | Extract from `VehiclePosition.position.longitude`. Must be between -180 and 180; source precision must be at least 6 decimal places. |
| `bearing` | FLOAT | Yes | Extract from `VehiclePosition.position.bearing`. Must be between 0 (inclusive) and 360 (exclusive); round to 2 decimal places. |
| `speed` | FLOAT | Yes | Extract from `VehiclePosition.position.speed`. Must be non-negative; preserve source unit (metres per second); round to 2 decimal places. |
| `odometer` | DOUBLE | Yes | Extract from `VehiclePosition.position.odometer`. Optional; must be non-negative when supplied. |
| `current_stop_sequence` | INT | No | Must match the current stop sequence in `stop_times`. Must be positive; when travelling towards the first stop, value must be 1. |
| `stop_id` | STRING | No | Must reference `stops.stop_id`. Represents the associated stop (TSN). |
| `current_status` | STRING | No | Valid values: `STOPPED_AT` and `IN_TRANSIT_TO`. `INCOMING_AT` is not used by TfNSW. |
| `timestamp` | TIMESTAMP | No | Extract from `VehiclePosition.timestamp`. Convert Unix timestamp (seconds since 1970-01-01 UTC) into TIMESTAMP. |
| `congestion_level` | STRING | No | Validate against TfNSW values: `UNKNOWN_CONGESTION_LEVEL`, `RUNNING_SMOOTHLY`, `STOP_AND_GO`, `CONGESTION`, `SEVERE_CONGESTION`. |
| `occupancy_status` | STRING | No | Validate against TfNSW values: `MANY_SEATS_AVAILABLE`, `FEW_SEATS_AVAILABLE`, `STANDING_ROOM_ONLY`, `NO_DATA_AVAILABLE`. Do not use `EMPTY`, `CRUSHED_STANDING_ROOM_ONLY`, `FULL`, `NOT_ACCEPTING_PASSENGERS` or `NOT_BOARDABLE`. |
| `occupancy_percentage` | INT | Yes | Available in the protobuf schema but not specified as a required TfNSW field. Must be between 0 and 100 when supplied. |

**Additional cleaning rules:**

- Flatten nested protobuf objects into individual columns.
- Preserve all identifiers as STRING to avoid unintended conversion.
- Derive `direction_id` from the static `trips` table when it is missing for a scheduled trip.
- Validate `trip_id`, `route_id` and `stop_id` against their corresponding static tables where applicable.
- Convert `start_date` from `YYYYMMDD` into DATE.
- Convert the Unix `timestamp` into TIMESTAMP using UTC.
- Validate latitude and longitude together; both must be present for a valid vehicle position.
- Preserve missing optional fields as NULL; do not replace them with zero or empty strings.
- Flag or quarantine records missing required TfNSW fields.
- Validate enum fields against TfNSW-approved values.
- Use `NO_DATA_AVAILABLE` for occupancy when the occupancy information is unavailable, where applicable.
- Retain the source ingestion timestamp separately from the vehicle-reported timestamp.
- Do not use `vehicle_id` alone as a primary key because the same vehicle appears in multiple feed snapshots.
- Preserve `multi_carriage_details` in Bronze and model it separately if carriage-level information is required.

#### trip_updates

| Column | Data type | Nullable | Constraints and cleaning rules |
|---|---|---|---|
| `entity_id` | STRING | No | Extract from `FeedEntity.id`. Preserve as STRING to identify the source feed entity. |
| `trip_id` | STRING | No | Extract from `TripDescriptor.trip_id`. Preserve as STRING; validate against the static `trips` table where applicable. |
| `route_id` | STRING | Yes | Extract from `TripDescriptor.route_id`. Preserve as STRING; validate against the static `routes` table where available. |
| `start_date` | DATE | Yes | Extract from `TripDescriptor.start_date`. Parse `YYYYMMDD` into DATE. |
| `start_time` | STRING | Yes | Extract from `TripDescriptor.start_time`. Preserve as `HH:MM:SS` STRING because GTFS service times can exceed 24 hours. |
| `trip_schedule_relationship` | STRING | Yes | Extract from `TripDescriptor.schedule_relationship`. Validate against supported enum values. |
| `vehicle_id` | STRING | Yes | Extract from `TripUpdate.vehicle.id`. Preserve as STRING. |
| `vehicle_label` | STRING | Yes | Extract from `TripUpdate.vehicle.label`. Preserve as STRING. |
| `license_plate` | STRING | Yes | Extract from `TripUpdate.vehicle.license_plate`. Preserve as STRING. |
| `trip_timestamp` | TIMESTAMP | Yes | Extract from `TripUpdate.timestamp`. Convert Unix seconds to UTC TIMESTAMP. |
| `trip_delay_seconds` | INT | Yes | Extract from `TripUpdate.delay`, when provided. Store delay in seconds; positive means late and negative means early. |
| `stop_sequence` | INT | Yes | Extract from `StopTimeUpdate.stop_sequence`. Must be a positive integer when provided. |
| `stop_id` | STRING | Yes | Extract from `StopTimeUpdate.stop_id`. Preserve as STRING; validate against the static `stops` table where available. |
| `stop_schedule_relationship` | STRING | Yes | Extract from `StopTimeUpdate.schedule_relationship`. Validate against supported enum values. |
| `arrival_delay_seconds` | INT | Yes | Extract from `StopTimeUpdate.arrival.delay`. Store delay in seconds. |
| `arrival_time` | TIMESTAMP | Yes | Extract from `StopTimeUpdate.arrival.time`. Convert Unix seconds to UTC TIMESTAMP. |
| `departure_delay_seconds` | INT | Yes | Extract from `StopTimeUpdate.departure.delay`. Store delay in seconds. |
| `departure_time` | TIMESTAMP | Yes | Extract from `StopTimeUpdate.departure.time`. Convert Unix seconds to UTC TIMESTAMP. |

**Additional cleaning rules:**

- Flatten the nested `TripUpdate` protobuf structure into columns.
- Explode `stop_time_update` into separate rows, with one row per stop update.
- Repeat trip-level and vehicle-level fields across all stop updates belonging to the same trip update.
- Preserve the original `entity_id` to maintain traceability to the source feed.
- Do not assume a missing arrival or departure prediction means zero delay; retain NULL.
- Do not assume `stop_sequence` or `stop_id` is always populated. Retain NULL when absent.
- Validate `trip_id`, `route_id`, and `stop_id` against their corresponding static GTFS tables where applicable.
- Preserve the raw protobuf data in Bronze so the original message can be reprocessed if cleaning rules change.
- Add an ingestion timestamp separately from `trip_timestamp` to record when the pipeline collected the update.
- Do not treat `entity_id` or `trip_id` alone as a unique key for individual stop updates. Use a composite key or retain a separate source-record identifier.

## 3. ML problem
- Unit of prediction: One (trip, stop, prediction time) combination: “trip T123, Bondi Beach stop, predicted at 8:10”
- Label and how it’s measured: The time of bus actually arrived at a stop minus the scheduled time, in seconds. It’s measured from VehiclePositions
- Prediction time and what’s known then: Only use current delay, the stops left and the time of day, can not use anuthing after the time calling model, since it is data leakage
- Segments: Running trip (trip already started and may be affected by the delay) vs Trip not started (for example: tomorrow schedule trips are not affected)

## 4. Features

**First version (V1):** Start with five minimal features. Use one model for both upcoming and running trips. Features requiring a current vehicle position are NULL for trips that have not started.

| Feature | Source | Not started? | Running? | Leakage check |
|---|---|---|---|---|
| `trip_started` | Derived from VehiclePositions observations. | Yes | Yes | Only use observations collected at or before prediction time. |
| `minutes_until_scheduled_arrival` | Derived from `stop_times.arrival_time`, service date and prediction timestamp. | Yes | Yes | Use scheduled arrival time, never actual arrival time. |
| `time_of_day` | Derived from the target stop's scheduled arrival timestamp. | Yes | Yes | Use the scheduled arrival time, not the prediction generation time. |
| `day_of_week` | Derived from the target stop's scheduled arrival timestamp. | Yes | Yes | Use the scheduled arrival date, not the prediction generation date. |
| `stops_ahead` | Derived from the target stop's `stop_sequence` in `stop_times` and the bus's `current_stop_sequence` in `vehicle_positions`. | NULL | Yes | Only use the latest available vehicle position at prediction time. |
| `current_delay_seconds` | Derived from the latest VehiclePositions snapshot at or before T and the corresponding scheduled progress from `stop_times`. | NULL | Yes | Only use VehiclePositions observations collected at or before T. Do not use TfNSW's predicted arrival delays. |
| `route_id` | `trips.route_id`. | Yes | Yes | Use the route associated with the target trip. |
| `stop_id` | `stop_times.stop_id`. | Yes | Yes | Use the target stop, not a stop identified using future observations. |
| `historical_avg_delay_route_stop_hour_weekday` | Derived from previously labelled historical data. | Yes | Yes | Calculate using only historical labels available before the prediction timestamp. |

**Feature definitions:**

- `trip_started`: 0 if the trip has not appeared in VehiclePositions; 1 if the matching trip is present in VehiclePositions. Only classify trips as not started when the feed is available and complete enough to support that conclusion.
- `minutes_until_scheduled_arrival`: Difference between the scheduled arrival datetime at the target stop and the prediction timestamp, converted into minutes.
- `time_of_day`: Time of the scheduled arrival at the target stop.
- `day_of_week`: Day of the week of the scheduled arrival at the target stop.
- `stops_ahead`: Target stop sequence minus the bus's current stop sequence. For example, target sequence 5 minus current sequence 3 equals 2 stops ahead.
- `current_delay_seconds`: Estimated delay of the running bus at its current or last passed stop, derived from the latest VehiclePositions snapshot at or before prediction timestamp T and the corresponding scheduled progress from `stop_times`. NULL for trips that have not started. Do not use TfNSW's predicted arrival delays.
- `route_id`: Route associated with the scheduled trip, sourced from `trips.route_id`. Treat as a categorical feature.
- `stop_id`: Target stop identifier, sourced from `stop_times.stop_id`. Treat as a categorical feature.
- `historical_avg_delay_route_stop_hour_weekday`: Historical average arrival delay for the same route, target stop, scheduled arrival hour and weekday. Calculate using previously labelled observations available before the prediction timestamp.

**### Training label (target variable)**

The model predicts `arrival_delay_seconds`, defined as:

`actual_arrival_timestamp - scheduled_arrival_timestamp`

**Source of actual arrival time: `vehicle_positions`**

We continuously collect VehiclePositions snapshots. For each trip and target stop:

1. Identify the first VehiclePositions observation where:
   - `trip_id` matches the scheduled trip.
   - `stop_id` matches the target stop.
   - `current_status` = `STOPPED_AT`.
2. If no matching `STOPPED_AT` observation is available, use a fallback:
   - Identify the first snapshot where `current_stop_sequence` has moved past the target stop's `stop_sequence`.
   - Retrieve the immediately preceding valid snapshot for the same trip.
   - Confirm that the previous `current_stop_sequence` was before the target stop's sequence.
   - Estimate the arrival timestamp between the two observations.
3. Use the identified or estimated timestamp as the actual arrival timestamp.
4. Join the observation to `stop_times` using `trip_id` and the target stop's `stop_sequence` to retrieve the scheduled arrival time.
5. Combine the scheduled arrival time with the applicable service date to obtain the scheduled arrival datetime.
6. Calculate the arrival delay in seconds.

**Example:**

| Information | Value |
|---|---|
| Trip ID | `1012281` |
| Target stop | `20005` |
| Scheduled arrival | `08:30:00` |
| Estimated actual arrival | `08:33:00` |
| Label method | `STOPPED_AT` |
| Training label (`arrival_delay_seconds`) | `+180` |

The bus arrived approximately 3 minutes late, so the training label is `180` seconds.

**How the label becomes training data:**

Build training examples by replaying stored VehiclePositions snapshots rather than depending on the live prediction service to save features.

For each historical prediction timestamp (T):

1. Retrieve the static GTFS data applicable to the trip.
2. Retrieve only realtime snapshots collected at or before T.
3. Reconstruct all features using only information available at T.
4. Create a feature row for the trip and target stop.
5. Use subsequent VehiclePositions observations to estimate the actual arrival timestamp and calculate the label.
6. Attach the label and its generation method to the corresponding feature row.

Each `(trip_id, target stop, prediction timestamp)` combination becomes one training example once its arrival outcome is available.

**Important considerations:**

- VehiclePositions provides an estimated arrival time, not an exact physical arrival timestamp. The label's accuracy is limited by the feed update and collection intervals.
- Retain the vehicle-reported timestamp and ingestion timestamp separately.
- Record the label-generation method (`STOPPED_AT` or `SEQUENCE_PASSED`) for each example so that label quality can be evaluated separately.
- Never use observations collected after the prediction timestamp to construct features.
- Do not use TfNSW TripUpdates' predicted arrival delays as training labels. TfNSW predictions remain the benchmark for model evaluation.
- Historical average delay features must only use labels that were available before the prediction timestamp.
- Exclude examples where the arrival event cannot be reliably identified.

## 5. Evaluation
- **Metrics**: see problem statement §4
- **Train/test split:** Use a time-based split by service date, not a random split. Train on older historical data and test on more recent, unseen dates. This simulates real-world deployment, where the model learns from past trips and predicts future trips.

  - Training set: Earliest 70% of dates.
  - Validation set: Next 15% of dates.
  - Test set: Most recent 15% of dates.

  Ensure all prediction records belonging to the same service date remain in the same split to prevent data leakage.
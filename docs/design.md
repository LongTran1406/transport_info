# Design (Part 1): Data and ML problem
See [problem statement](ml-design-document.md)

## 1. Data sources
| Feed | Format | Endpoint | Update freq | Pull freq | Limits |
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
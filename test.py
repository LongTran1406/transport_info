import os
import requests
import zipfile
import io
from dotenv import load_dotenv
from google.transit import gtfs_realtime_pb2
import gzip

load_dotenv()

API_KEY = os.getenv("NSW_TRANSPORT_API_KEY")

HEADERS = {
    "Authorization": f"apikey {API_KEY.strip()}",
    "Accept": "application/x-protobuf"
}


def get_bus_static_schedule():
    """Downloads the static bus GTFS schedule and prints each CSV table's schema."""

    url = "https://api.transport.nsw.gov.au/v1/gtfs/schedule/buses"

    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        for filename in z.namelist():
            print(f"\n--- {filename} ---")
            if filename.endswith(".txt"):
                with z.open(filename) as f:
                    content = f.read().decode("utf-8")
                    print(content[:500])

                    # Print table schema (column names)
                    print("Schema:", content.splitlines()[0])

    return response.content


def get_bus_vehicle_positions():
    """Fetches real-time bus locations and prints the first vehicle position and schema."""

    url = "https://api.transport.nsw.gov.au/v1/gtfs/vehiclepos/buses"

    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    size = len(response.content)
    print(f"VehiclePositions: {size/1024:.1f} KB raw, {len(gzip.compress(response.content))/1024:.1f} KB gzipped")

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    print(f"Entities: {len(feed.entity)}")

    if feed.entity:
        print(feed.entity[0])

    # Print protobuf schema
    print("\nVehicle Position Schema:")
    print(gtfs_realtime_pb2.VehiclePosition.DESCRIPTOR.fields_by_name.keys())

    return feed


def get_bus_trip_updates():
    """Fetches real-time bus trip updates and prints the first trip update and schema."""

    url = "https://api.transport.nsw.gov.au/v1/gtfs/realtime/buses"

    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    size = len(response.content)
    print(f"TripUpdates: {size/1024:.1f} KB raw, {len(gzip.compress(response.content))/1024:.1f} KB gzipped")

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    print(f"Entities: {len(feed.entity)}")

    if feed.entity:
        print(feed.entity[0])

    # Print protobuf schema
    print("\nTrip Update Schema:")
    print(gtfs_realtime_pb2.TripUpdate.DESCRIPTOR.fields_by_name.keys())

    return feed

import pandas as pd

def count_routes(zip_bytes, tu_feed):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        routes = pd.read_csv(z.open("routes.txt"), dtype=str)

    print(f"route_ids:          {routes['route_id'].nunique()}")
    print(f"route_short_names:  {routes['route_short_name'].nunique()}")
    print(f"agencies:           {routes['agency_id'].nunique()}")
    print("\nTop networks (route_desc):")
    print(routes['route_desc'].value_counts().head(15))

    active = {e.trip_update.trip.route_id for e in tu_feed.entity}
    print(f"\nroute_ids active in this TripUpdates snapshot: {len(active)}")

import time
import gzip
import pandas as pd

TU_URL = "https://api.transport.nsw.gov.au/v1/gtfs/realtime/buses"


def flatten_trip_updates(feed, pulled_at):
    """One row per stop_time_update, like the Silver trip_updates table."""
    rows = []
    for e in feed.entity:
        if not e.HasField("trip_update"):
            continue
        tu = e.trip_update
        for stu in tu.stop_time_update:
            rows.append({
                "pulled_at": pulled_at,
                "entity_id": e.id,
                "trip_id": tu.trip.trip_id,
                "route_id": tu.trip.route_id,
                "start_date": tu.trip.start_date,
                "start_time": tu.trip.start_time,
                "trip_schedule_relationship": tu.trip.schedule_relationship,
                "vehicle_id": tu.vehicle.id,
                "trip_timestamp": tu.timestamp,
                "stop_sequence": stu.stop_sequence,
                "stop_id": stu.stop_id,
                "stop_schedule_relationship": stu.schedule_relationship,
                "arrival_delay": stu.arrival.delay if stu.HasField("arrival") else None,
                "arrival_time": stu.arrival.time if stu.HasField("arrival") else None,
                "departure_delay": stu.departure.delay if stu.HasField("departure") else None,
                "departure_time": stu.departure.time if stu.HasField("departure") else None,
            })
    return rows


def parquet_size(df):
    buf = io.BytesIO()
    df.to_parquet(buf, compression="zstd", index=False)
    return buf.tell()


def compare_sizes(n_pulls=10, interval=30):
    raws, rows = [], []
    for i in range(n_pulls):
        r = requests.get(TU_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(r.content)
        raws.append(r.content)
        rows += flatten_trip_updates(feed, pulled_at=int(time.time()))
        print(f"pull {i+1}/{n_pulls}: {len(r.content)/1024:.0f} KB, {len(feed.entity)} trips")
        if i < n_pulls - 1:
            time.sleep(interval)

    df = pd.DataFrame(rows)
    dedup = df.drop_duplicates(subset=[c for c in df.columns if c != "pulled_at"])

    kb = lambda b: b / 1024 / n_pulls  # per-pull average, KB
    print(f"\nRows: {len(df):,}  (after removing exact duplicates: {len(dedup):,})")
    print(f"Per pull, averaged over {n_pulls} pulls:")
    print(f"  Raw protobuf:              {kb(sum(map(len, raws))):8.1f} KB")
    print(f"  Gzip, one file per pull:   {kb(sum(len(gzip.compress(x)) for x in raws)):8.1f} KB")
    print(f"  Gzip, all pulls together:  {kb(len(gzip.compress(b''.join(raws)))):8.1f} KB")
    print(f"  Parquet (zstd):            {kb(parquet_size(df)):8.1f} KB")
    print(f"  Parquet, exact dups gone:  {kb(parquet_size(dedup)):8.1f} KB")

if __name__ == "__main__":
    get_bus_static_schedule()
    get_bus_vehicle_positions()
    get_bus_trip_updates()
    zip_bytes = get_bus_static_schedule()
    tu_feed = get_bus_trip_updates()
    count_routes(zip_bytes, tu_feed)
    compare_sizes()
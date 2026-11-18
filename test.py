import os
import requests
import zipfile
import io
from dotenv import load_dotenv
from google.transit import gtfs_realtime_pb2

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

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)

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

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)

    if feed.entity:
        print(feed.entity[0])

    # Print protobuf schema
    print("\nTrip Update Schema:")
    print(gtfs_realtime_pb2.TripUpdate.DESCRIPTOR.fields_by_name.keys())

    return feed


if __name__ == "__main__":
    get_bus_static_schedule()
    get_bus_vehicle_positions()
    get_bus_trip_updates()
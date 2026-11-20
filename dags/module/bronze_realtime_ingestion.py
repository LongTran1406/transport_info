
"""Bronze realtime ingestion function."""

import os
import time
import logging
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from google.transit import gtfs_realtime_pb2
from minio import Minio
import io
import zipfile
import csv
import gzip

load_dotenv()

API_KEY = os.getenv("NSW_TRANSPORT_API_KEY")

HEADERS = {
    "Authorization": f"apikey {API_KEY.strip()}",
    "Accept": "application/x-protobuf"
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

VEHICLE_POSITIONS_URL = "https://api.transport.nsw.gov.au/v1/gtfs/vehiclepos/buses"
TRIP_UPDATES_URL = "https://api.transport.nsw.gov.au/v1/gtfs/realtime/buses"

# MinIO client
minio_client = Minio(
    "minio:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False
)

BUCKET = "bronze"

def get_sydney_route_ids():
    """Downloads static GTFS and returns Sydney Buses Network route IDs."""

    response = requests.get(
        "https://api.transport.nsw.gov.au/v1/gtfs/schedule/buses",
        headers={
            "Authorization": f"apikey {API_KEY.strip()}",
            "Accept": "application/zip"
        },
        timeout=60
    )
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        with z.open("routes.txt") as f:
            reader = csv.DictReader(
                io.TextIOWrapper(f, encoding="utf-8")
            )

            route_ids = {
                row["route_id"]
                for row in reader
                if row.get("route_desc") == "Sydney Buses Network"
            }

    if not route_ids:
        raise ValueError("No Sydney Buses Network routes found.")

    logger.info("Sydney Buses Network routes: %d", len(route_ids))

    return route_ids



def upload_to_bronze(data, source):
    """Compresses and uploads GTFS-Realtime protobuf data to Bronze."""

    now = datetime.now(timezone.utc)

    object_name = (
        f"gtfs/realtime/{source}/"
        f"date={now:%Y-%m-%d}/"
        f"hour={now:%H}/"
        f"data_{now:%H%M%S}.pb.gz"
    )

    compressed_data = gzip.compress(data)

    minio_client.put_object(
        BUCKET,
        object_name,
        io.BytesIO(compressed_data),
        length=len(compressed_data),
        content_type="application/gzip"
    )

    logger.info(
        "Uploaded compressed data to s3://%s/%s (%.2f MB → %.2f MB)",
        BUCKET,
        object_name,
        len(data) / (1024 * 1024),
        len(compressed_data) / (1024 * 1024)
    )


def get_bus_vehicle_positions(sydney_route_ids):
    """Fetches bus VehiclePositions and logs the first entity and schema."""

    response = requests.get(VEHICLE_POSITIONS_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)

    filtered_entities = [
        entity for entity in feed.entity
        if entity.HasField("vehicle")
        and entity.vehicle.HasField("trip")
        and entity.vehicle.trip.route_id in sydney_route_ids
    ]

    del feed.entity[:]
    feed.entity.extend(filtered_entities)

    if feed.entity:
        logger.info("First VehiclePosition entity:\n%s", feed.entity[0])
    
    upload_to_bronze(
        feed.SerializeToString(),
        "vehicle_positions"
    )

    return feed


def get_bus_trip_updates(sydney_route_ids):
    """Fetches bus TripUpdates and logs the first entity and schema."""

    response = requests.get(TRIP_UPDATES_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)

    filtered_entities = [
        entity for entity in feed.entity
        if entity.HasField("trip_update")
        and entity.trip_update.trip.route_id in sydney_route_ids
    ]

    del feed.entity[:]
    feed.entity.extend(filtered_entities)

    if feed.entity:
        logger.info("First TripUpdate entity:\n%s", feed.entity[0])
   
    upload_to_bronze(
        feed.SerializeToString(),
        "trip_updates"
    )
    return feed


def ingest_bronze_realtime():
    """Continuously fetch GTFS realtime data for the Bronze layer."""

    sydney_route_ids = get_sydney_route_ids()

    while True:
        try:
            logger.info("Starting bronze realtime ingestion.")

            get_bus_vehicle_positions(sydney_route_ids)
            get_bus_trip_updates(sydney_route_ids)

            logger.info("Bronze realtime ingestion completed.")

        except Exception:
            logger.exception("Bronze realtime ingestion failed.")

        time.sleep(30)


if __name__ == "__main__":
    ingest_bronze_realtime()

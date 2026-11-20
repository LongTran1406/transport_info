
"""Bronze static GTFS schedule ingestion."""

import os
import io
import logging
import requests

from datetime import datetime, timezone
from dotenv import load_dotenv
from minio import Minio

load_dotenv()

API_KEY = os.getenv("NSW_TRANSPORT_API_KEY")

HEADERS = {
    "Authorization": f"apikey {API_KEY.strip()}",
    "Accept": "application/zip"
}

SCHEDULE_URL = "https://api.transport.nsw.gov.au/v1/gtfs/schedule/buses"

# MinIO client
minio_client = Minio(
    "minio:9000",
    access_key=os.environ["MINIO_ROOT_USER"],
    secret_key=os.environ["MINIO_ROOT_PASSWORD"],
    secure=False
)

BUCKET = "bronze"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def ingest_bronze_schedule():
    """Downloads the static bus GTFS schedule and uploads it to Bronze."""

    try:
        logger.info("Starting bronze schedule ingestion.")

        response = requests.get(
            SCHEDULE_URL,
            headers=HEADERS,
            timeout=60
        )
        response.raise_for_status()

        data = response.content

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        object_name = (
            f"gtfs/schedule/run_id={timestamp}/schedule.zip"
        )

        minio_client.put_object(
            BUCKET,
            object_name,
            io.BytesIO(data),
            length=len(data),
            content_type="application/zip"
        )

        logger.info("Uploaded to s3://%s/%s", BUCKET, object_name)


    except Exception:
        logger.exception("Bronze schedule ingestion failed.")
        raise


if __name__ == "__main__":
    ingest_bronze_schedule()

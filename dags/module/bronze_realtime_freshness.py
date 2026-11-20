
import logging
import re
from datetime import datetime, timedelta, timezone

from minio import Minio

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

minio_client = Minio(
    "minio:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False
)

BUCKET = "bronze"
FEEDS = ["vehicle_positions", "trip_updates"]
MAX_AGE_MINUTES = 5


def check_feed_freshness(feed):
    """Checks whether the latest Bronze realtime file is fresh."""

    now = datetime.now(timezone.utc)

    prefix = f"gtfs/realtime/{feed}/"

    latest_timestamp = None
    latest_object = None

    objects = minio_client.list_objects(
        BUCKET,
        prefix=prefix,
        recursive=True
    )

    for obj in objects:
        # Expected: data_HHmmss.pb.gz
        match = re.search(r"data_(\d{6})\.pb\.gz$", obj.object_name)

        if not match:
            continue

        # Extract date and hour from object path
        date_match = re.search(r"date=(\d{4}-\d{2}-\d{2})", obj.object_name)
        hour_match = re.search(r"hour=(\d{2})", obj.object_name)

        if not date_match or not hour_match:
            continue

        timestamp_str = (
            f"{date_match.group(1)} "
            f"{hour_match.group(1)}:"
            f"{match.group(1)[2:4]}:"
            f"{match.group(1)[4:6]}"
        )

        timestamp = datetime.strptime(
            timestamp_str,
            "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)

        if latest_timestamp is None or timestamp > latest_timestamp:
            latest_timestamp = timestamp
            latest_object = obj.object_name

    if latest_timestamp is None:
        logger.error("[%s] No Bronze files found.", feed)
        return

    age = now - latest_timestamp

    if age > timedelta(minutes=MAX_AGE_MINUTES):
        logger.warning(
            "[%s] STALE: Latest file is %.1f minutes old. Object: %s",
            feed,
            age.total_seconds() / 60,
            latest_object
        )
    else:
        logger.info(
            "[%s] FRESH: Latest file is %.1f minutes old.",
            feed,
            age.total_seconds() / 60
        )


def check_bronze_realtime_freshness():
    """Checks freshness of all Bronze realtime feeds."""

    for feed in FEEDS:
        try:
            check_feed_freshness(feed)
        except Exception:
            logger.exception(
                "[%s] Failed to check Bronze freshness.",
                feed
            )


if __name__ == "__main__":
    check_bronze_realtime_freshness()
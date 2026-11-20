"""Airflow DAG for bronze realtime ingestion."""

import os
from datetime import timedelta

from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.python import PythonOperator

from module.bronze_realtime_freshness import check_bronze_realtime_freshness

# Comma-separated list in .env; email stays off until it is set (needs AIRFLOW__SMTP__* too).
ALERT_EMAILS = [e.strip() for e in os.getenv("ALERT_EMAIL", "").split(",") if e.strip()]

with DAG(
    "bronze_realtime_ingestion",
    schedule_interval="*/5 * * * *",
    start_date=days_ago(0),
    catchup=False,
    dagrun_timeout=timedelta(minutes=5),
    default_args={
        "email": ALERT_EMAILS,
        "email_on_failure": bool(ALERT_EMAILS),
        "email_on_retry": False,
    },
) as dag:

    bronze_realtime_ingestion_task = PythonOperator(
        task_id="bronze_realtime_ingestion",
        python_callable=check_bronze_realtime_freshness,
    )
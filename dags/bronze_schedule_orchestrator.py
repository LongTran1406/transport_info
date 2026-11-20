"""Airflow DAG for bronze schedule ingestion."""

from datetime import timedelta
import pendulum
from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.python import PythonOperator

from module.bronze_schedule_ingestion import ingest_bronze_schedule

with DAG(
    "bronze_schedule_ingestion",
    schedule_interval="0 5 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="Australia/Sydney"),
    catchup=False,
    dagrun_timeout=timedelta(minutes=60),
) as dag:

    bronze_schedule_ingestion_task = PythonOperator(
        task_id="bronze_schedule_ingestion",
        python_callable=ingest_bronze_schedule,
    )
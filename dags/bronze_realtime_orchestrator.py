"""Airflow DAG for bronze realtime ingestion."""

from datetime import timedelta

from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.python import PythonOperator

from module.bronze_realtime_freshness import check_bronze_realtime_freshness

with DAG(
    "bronze_realtime_ingestion",
    schedule_interval="*/5 * * * *",
    start_date=days_ago(0),
    catchup=False,
    dagrun_timeout=timedelta(minutes=5),
) as dag:

    bronze_realtime_ingestion_task = PythonOperator(
        task_id="bronze_realtime_ingestion",
        python_callable=check_bronze_realtime_freshness,
    )
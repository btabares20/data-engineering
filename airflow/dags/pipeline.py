from datetime import datetime

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator

from orchestrator import (
    run_jobs_govt_collector,
    run_trade_me_collector,
    run_jobs_govt_parser,
    run_trade_me_parser,
    run_jobs_govt_loader,
    run_trade_me_loader,
    run_transform,
)


with DAG(
    dag_id="pipeline",
    start_date=None,
    schedule=None,
    catchup=False,
) as dag:

    # Collectors
    jobs_govt_collector = PythonOperator(
        task_id="jobs_govt_collector",
        python_callable=run_jobs_govt_collector,
    )

    trade_me_collector = PythonOperator(
        task_id="trade_me_collector",
        python_callable=run_trade_me_collector,
    )

    # Parsers
    jobs_govt_parser = PythonOperator(
        task_id="jobs_govt_parser",
        python_callable=run_jobs_govt_parser,
    )

    trade_me_parser = PythonOperator(
        task_id="trade_me_parser",
        python_callable=run_trade_me_parser,
    )

    # Loaders
    jobs_govt_loader = PythonOperator(
        task_id="jobs_govt_loader",
        python_callable=run_jobs_govt_loader,
    )

    trade_me_loader = PythonOperator(
        task_id="trade_me_loader",
        python_callable=run_trade_me_loader,
    )

    # Transform
    transform = PythonOperator(
        task_id="transform",
        python_callable=run_transform,
    )

    # Collectors -> Parsers
    jobs_govt_collector >> [
        jobs_govt_parser,
        trade_me_parser,
    ]

    trade_me_collector >> [
        jobs_govt_parser,
        trade_me_parser,
    ]

    # Parsers -> Loaders
    jobs_govt_parser >> [
        jobs_govt_loader,
        trade_me_loader,
    ]

    trade_me_parser >> [
        jobs_govt_loader,
        trade_me_loader,
    ]

    # Loaders -> Transform
    jobs_govt_loader >> transform
    trade_me_loader >> transform


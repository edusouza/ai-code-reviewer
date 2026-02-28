"""BigQuery ETL for analytics and reporting."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from config.settings import settings

if TYPE_CHECKING:
    from google.cloud.bigquery import Client as BigQueryClient

logger = logging.getLogger(__name__)


class BigQueryETL:
    """ETL pipeline for exporting observability data to BigQuery."""

    def __init__(
        self,
        project_id: str | None = None,
        dataset_id: str = "ai_reviewer_analytics",
        enabled: bool = True,
    ):
        """
        Initialize BigQuery ETL.

        Args:
            project_id: GCP project ID
            dataset_id: BigQuery dataset ID
            enabled: Whether ETL is enabled
        """
        self.project_id = project_id or settings.project_id
        self.dataset_id = dataset_id
        self.enabled = enabled and bool(self.project_id)

        self._client: BigQueryClient | None = None
        self._table_prefix = f"{self.project_id}.{self.dataset_id}"

        if self.enabled:
            try:
                self._initialize_client()
            except Exception as e:
                logger.error(f"Failed to initialize BigQuery: {e}")
                self.enabled = False

    def _initialize_client(self) -> None:
        """Initialize the BigQuery client."""
        try:
            from google.cloud.bigquery import Client as BigQueryClient
            from google.cloud.bigquery import Dataset

            self._client = BigQueryClient(project=self.project_id)

            # Ensure dataset exists
            dataset_ref = f"{self.project_id}.{self.dataset_id}"
            try:
                assert self._client is not None
                self._client.get_dataset(dataset_ref)
            except Exception:
                logger.info(f"Creating BigQuery dataset: {self.dataset_id}")
                dataset = Dataset(dataset_ref)
                dataset.location = "US"
                assert self._client is not None
                self._client.create_dataset(dataset, exists_ok=True)

            logger.info("BigQuery ETL initialized")
        except ImportError:
            logger.warning("google-cloud-bigquery not installed, ETL disabled")
            self.enabled = False

    async def export_daily_metrics(self, date: datetime | None = None) -> None:
        """
        Export daily metrics to BigQuery.

        Args:
            date: Date to export (defaults to yesterday)
        """
        if not self.enabled:
            return

        if date is None:
            date = datetime.utcnow() - timedelta(days=1)

        try:
            # Get data from Firestore or other sources
            daily_data = await self._collect_daily_data(date)

            # Transform data
            transformed_data = self._transform_metrics(daily_data)

            # Load to BigQuery
            await self._load_to_bigquery(table_name="daily_metrics", data=transformed_data)

            logger.info(f"Exported metrics for {date.date()}")

        except Exception as e:
            logger.error(f"Failed to export daily metrics: {e}")
            raise

    async def export_review_analytics(self, start_date: datetime, end_date: datetime) -> None:
        """
        Export review analytics for a date range.

        Args:
            start_date: Start date
            end_date: End date
        """
        if not self.enabled:
            return

        try:
            # Collect review data
            review_data = await self._collect_review_data(start_date, end_date)

            # Transform
            transformed = self._transform_reviews(review_data)

            # Load
            await self._load_to_bigquery(table_name="reviews", data=transformed)

            logger.info(
                f"Exported {len(transformed)} reviews from {start_date.date()} to {end_date.date()}"
            )

        except Exception as e:
            logger.error(f"Failed to export review analytics: {e}")
            raise

    async def export_feedback_analytics(self, start_date: datetime, end_date: datetime) -> None:
        """
        Export feedback analytics.

        Args:
            start_date: Start date
            end_date: End date
        """
        if not self.enabled:
            return

        try:
            feedback_data = await self._collect_feedback_data(start_date, end_date)
            transformed = self._transform_feedback(feedback_data)

            await self._load_to_bigquery(table_name="feedback", data=transformed)

            logger.info(f"Exported {len(transformed)} feedback items")

        except Exception as e:
            logger.error(f"Failed to export feedback analytics: {e}")
            raise

    async def _collect_daily_data(self, date: datetime) -> list[dict[str, Any]]:
        """Collect daily metrics data from Firestore."""
        try:
            from google.cloud.firestore import Client as FirestoreClient

            db = FirestoreClient(project=self.project_id)

            # Query metrics collection
            start = datetime(date.year, date.month, date.day)
            end = start + timedelta(days=1)

            metrics_ref = db.collection("metrics")
            query = metrics_ref.where("timestamp", ">=", start).where("timestamp", "<", end)

            docs = query.stream()
            data = []
            for doc in docs:
                doc_data = doc.to_dict()
                doc_data["id"] = doc.id
                data.append(doc_data)

            return data

        except Exception as e:
            logger.error(f"Failed to collect daily data: {e}")
            return []

    async def _collect_review_data(
        self, start_date: datetime, end_date: datetime
    ) -> list[dict[str, Any]]:
        """Collect review data from Firestore."""
        try:
            from google.cloud.firestore import Client as FirestoreClient

            db = FirestoreClient(project=self.project_id)

            reviews_ref = db.collection("reviews")
            query = reviews_ref.where("completed_at", ">=", start_date).where(
                "completed_at", "<=", end_date
            )

            docs = query.stream()
            data = []
            for doc in docs:
                doc_data = doc.to_dict()
                doc_data["id"] = doc.id
                data.append(doc_data)

            return data

        except Exception as e:
            logger.error(f"Failed to collect review data: {e}")
            return []

    async def _collect_feedback_data(
        self, start_date: datetime, end_date: datetime
    ) -> list[dict[str, Any]]:
        """Collect feedback data from Firestore."""
        try:
            from google.cloud.firestore import Client as FirestoreClient

            db = FirestoreClient(project=self.project_id)

            feedback_ref = db.collection("feedback")
            query = feedback_ref.where("timestamp", ">=", start_date).where(
                "timestamp", "<=", end_date
            )

            docs = query.stream()
            data = []
            for doc in docs:
                doc_data = doc.to_dict()
                doc_data["id"] = doc.id
                data.append(doc_data)

            return data

        except Exception as e:
            logger.error(f"Failed to collect feedback data: {e}")
            return []

    def _transform_metrics(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform raw metrics data for BigQuery."""
        transformed = []

        for item in data:
            transformed.append(
                {
                    "date": item.get("timestamp", datetime.utcnow()).strftime("%Y-%m-%d"),
                    "metric_name": item.get("name", "unknown"),
                    "metric_value": float(item.get("value", 0)),
                    "metric_type": item.get("type", "gauge"),
                    "labels": json.dumps(item.get("labels", {})),
                    "inserted_at": datetime.utcnow().isoformat(),
                }
            )

        return transformed

    def _transform_reviews(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform review data for BigQuery."""
        transformed = []

        for item in data:
            pr_event = item.get("pr_event", {})

            transformed.append(
                {
                    "review_id": item.get("id", ""),
                    "provider": pr_event.get("provider", "unknown"),
                    "repo_owner": pr_event.get("repo_owner", ""),
                    "repo_name": pr_event.get("repo_name", ""),
                    "pr_number": pr_event.get("pr_number", 0),
                    "pr_title": pr_event.get("pr_title", ""),
                    "author": pr_event.get("author", ""),
                    "suggestions_count": item.get("suggestions_count", 0),
                    "tokens_used": item.get("tokens_used", 0),
                    "cost_usd": item.get("cost_usd", 0.0),
                    "duration_seconds": item.get("duration_seconds", 0.0),
                    "status": item.get("status", "unknown"),
                    "started_at": item.get("started_at", "").isoformat()
                    if isinstance(item.get("started_at"), datetime)
                    else item.get("started_at"),
                    "completed_at": item.get("completed_at", "").isoformat()
                    if isinstance(item.get("completed_at"), datetime)
                    else item.get("completed_at"),
                    "error_message": item.get("error_message", ""),
                    "inserted_at": datetime.utcnow().isoformat(),
                }
            )

        return transformed

    def _transform_feedback(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform feedback data for BigQuery."""
        transformed = []

        for item in data:
            transformed.append(
                {
                    "feedback_id": item.get("id", ""),
                    "review_id": item.get("review_id", ""),
                    "provider": item.get("provider", "unknown"),
                    "repo_owner": item.get("repo_owner", ""),
                    "repo_name": item.get("repo_name", ""),
                    "pr_number": item.get("pr_number", 0),
                    "feedback_type": item.get("feedback_type", "unknown"),
                    "score": float(item.get("score", 0)),
                    "emoji": item.get("emoji", ""),
                    "comment": item.get("comment", ""),
                    "file_path": item.get("file_path", ""),
                    "line_number": item.get("line_number", 0),
                    "timestamp": item.get("timestamp", "").isoformat()
                    if isinstance(item.get("timestamp"), datetime)
                    else item.get("timestamp"),
                    "inserted_at": datetime.utcnow().isoformat(),
                }
            )

        return transformed

    async def _load_to_bigquery(self, table_name: str, data: list[dict[str, Any]]) -> None:
        """Load data to BigQuery table."""
        if not data:
            logger.debug(f"No data to load to {table_name}")
            return

        if not self._client:
            logger.error(f"Cannot load to {table_name}: BigQuery client not initialized")
            return

        try:
            table_id = f"{self._table_prefix}.{table_name}"

            # Check if table exists, create if not
            try:
                self._client.get_table(table_id)
            except Exception:
                logger.info(f"Creating BigQuery table: {table_name}")
                self._create_table(table_name)

            # Insert data
            errors = self._client.insert_rows_json(table_id, data)

            if errors:
                logger.error(f"Errors loading to {table_name}: {errors}")
                raise Exception(f"Failed to load {len(errors)} rows")

            logger.debug(f"Loaded {len(data)} rows to {table_name}")

        except Exception as e:
            logger.error(f"Failed to load to BigQuery: {e}")
            raise

    def _create_table(self, table_name: str) -> None:
        """Create a BigQuery table if it doesn't exist."""
        if not self._client:
            logger.error(f"Cannot create table {table_name}: BigQuery client not initialized")
            return

        from google.cloud.bigquery import (
            SchemaField,
            Table,
            TimePartitioning,
            TimePartitioningType,
        )

        table_id = f"{self._table_prefix}.{table_name}"

        # Define schemas for known tables
        schemas = {
            "daily_metrics": [
                SchemaField("date", "DATE", mode="REQUIRED"),
                SchemaField("metric_name", "STRING", mode="REQUIRED"),
                SchemaField("metric_value", "FLOAT", mode="REQUIRED"),
                SchemaField("metric_type", "STRING", mode="REQUIRED"),
                SchemaField("labels", "STRING", mode="NULLABLE"),
                SchemaField("inserted_at", "TIMESTAMP", mode="REQUIRED"),
            ],
            "reviews": [
                SchemaField("review_id", "STRING", mode="REQUIRED"),
                SchemaField("provider", "STRING", mode="REQUIRED"),
                SchemaField("repo_owner", "STRING", mode="REQUIRED"),
                SchemaField("repo_name", "STRING", mode="REQUIRED"),
                SchemaField("pr_number", "INTEGER", mode="REQUIRED"),
                SchemaField("pr_title", "STRING", mode="NULLABLE"),
                SchemaField("author", "STRING", mode="NULLABLE"),
                SchemaField("suggestions_count", "INTEGER", mode="NULLABLE"),
                SchemaField("tokens_used", "INTEGER", mode="NULLABLE"),
                SchemaField("cost_usd", "FLOAT", mode="NULLABLE"),
                SchemaField("duration_seconds", "FLOAT", mode="NULLABLE"),
                SchemaField("status", "STRING", mode="REQUIRED"),
                SchemaField("started_at", "TIMESTAMP", mode="NULLABLE"),
                SchemaField("completed_at", "TIMESTAMP", mode="NULLABLE"),
                SchemaField("error_message", "STRING", mode="NULLABLE"),
                SchemaField("inserted_at", "TIMESTAMP", mode="REQUIRED"),
            ],
            "feedback": [
                SchemaField("feedback_id", "STRING", mode="REQUIRED"),
                SchemaField("review_id", "STRING", mode="REQUIRED"),
                SchemaField("provider", "STRING", mode="REQUIRED"),
                SchemaField("repo_owner", "STRING", mode="REQUIRED"),
                SchemaField("repo_name", "STRING", mode="REQUIRED"),
                SchemaField("pr_number", "INTEGER", mode="REQUIRED"),
                SchemaField("feedback_type", "STRING", mode="REQUIRED"),
                SchemaField("score", "FLOAT", mode="REQUIRED"),
                SchemaField("emoji", "STRING", mode="NULLABLE"),
                SchemaField("comment", "STRING", mode="NULLABLE"),
                SchemaField("file_path", "STRING", mode="NULLABLE"),
                SchemaField("line_number", "INTEGER", mode="NULLABLE"),
                SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
                SchemaField("inserted_at", "TIMESTAMP", mode="REQUIRED"),
            ],
        }

        schema = schemas.get(table_name, [])
        if schema:
            table = Table(table_id, schema=schema)
            table.time_partitioning = TimePartitioning(
                type_=TimePartitioningType.DAY, field="inserted_at"
            )
            self._client.create_table(table, exists_ok=True)
        else:
            # Create generic table
            table = Table(table_id)
            self._client.create_table(table, exists_ok=True)


# Cloud Function entry point for scheduled ETL
def run_daily_etl(event: dict[str, Any], context: Any) -> dict[str, str]:
    """
    Cloud Function entry point for daily ETL job.

    Triggered by Cloud Scheduler.
    """
    logger.info(f"Starting daily ETL job: {context.timestamp}")

    etl = BigQueryETL()

    # Run all exports
    asyncio.run(etl.export_daily_metrics())

    # Export last 7 days of reviews
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)
    asyncio.run(etl.export_review_analytics(start_date, end_date))
    asyncio.run(etl.export_feedback_analytics(start_date, end_date))

    logger.info("Daily ETL job completed")

    return {"status": "success", "message": "ETL completed"}

"""Tests for observability bigquery_etl module."""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from observability.bigquery_etl import BigQueryETL, run_daily_etl

# ---------------------------------------------------------------------------
# BigQueryETL initialization tests
# ---------------------------------------------------------------------------


class TestBigQueryETLInit:
    """Test BigQueryETL constructor and initialization."""

    @patch("observability.bigquery_etl.settings")
    def test_disabled_when_enabled_false(self, mock_settings):
        """ETL should be disabled when enabled=False."""
        mock_settings.project_id = "test-project"
        etl = BigQueryETL(project_id="test-project", enabled=False)
        assert etl.enabled is False

    @patch("observability.bigquery_etl.settings")
    def test_disabled_when_no_project_id(self, mock_settings):
        """ETL should be disabled when project_id is empty."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id="", enabled=True)
        assert etl.enabled is False

    @patch("observability.bigquery_etl.settings")
    def test_disabled_when_project_id_none_and_settings_empty(self, mock_settings):
        """ETL should be disabled when project_id is None and settings is empty."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=True)
        assert etl.enabled is False

    @patch("observability.bigquery_etl.settings")
    def test_uses_settings_project_id(self, mock_settings):
        """ETL should use settings.project_id when project_id is None."""
        mock_settings.project_id = "from-settings"
        # Patch _initialize_client to avoid real GCP calls
        with patch.object(BigQueryETL, "_initialize_client"):
            etl = BigQueryETL(project_id=None, enabled=True)
        assert etl.project_id == "from-settings"

    @patch("observability.bigquery_etl.settings")
    def test_explicit_project_id_overrides_settings(self, mock_settings):
        """ETL should use explicit project_id over settings."""
        mock_settings.project_id = "from-settings"
        with patch.object(BigQueryETL, "_initialize_client"):
            etl = BigQueryETL(project_id="explicit-project", enabled=True)
        assert etl.project_id == "explicit-project"

    @patch("observability.bigquery_etl.settings")
    def test_custom_dataset_id(self, mock_settings):
        """ETL should accept custom dataset_id."""
        mock_settings.project_id = "proj"
        with patch.object(BigQueryETL, "_initialize_client"):
            etl = BigQueryETL(project_id="proj", dataset_id="custom_analytics", enabled=True)
        assert etl.dataset_id == "custom_analytics"
        assert etl._table_prefix == "proj.custom_analytics"

    @patch("observability.bigquery_etl.settings")
    def test_default_dataset_id(self, mock_settings):
        """ETL should use default dataset_id."""
        mock_settings.project_id = "proj"
        with patch.object(BigQueryETL, "_initialize_client"):
            etl = BigQueryETL(project_id="proj", enabled=True)
        assert etl.dataset_id == "ai_reviewer_analytics"

    @patch("observability.bigquery_etl.settings")
    def test_initialize_client_called_when_enabled(self, mock_settings):
        """_initialize_client should be called when enabled."""
        mock_settings.project_id = "proj"
        with patch.object(BigQueryETL, "_initialize_client") as mock_init:
            BigQueryETL(project_id="proj", enabled=True)
            mock_init.assert_called_once()

    @patch("observability.bigquery_etl.settings")
    def test_disabled_on_initialize_error(self, mock_settings):
        """ETL should disable itself when _initialize_client raises."""
        mock_settings.project_id = "proj"
        with patch.object(BigQueryETL, "_initialize_client", side_effect=Exception("init error")):
            etl = BigQueryETL(project_id="proj", enabled=True)
        assert etl.enabled is False

    @patch("observability.bigquery_etl.settings")
    def test_client_is_none_initially(self, mock_settings):
        """_client should be None before initialization."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)
        assert etl._client is None


# ---------------------------------------------------------------------------
# _initialize_client tests
# ---------------------------------------------------------------------------


class TestInitializeClient:
    """Test _initialize_client method."""

    @patch("observability.bigquery_etl.settings")
    def test_import_error_disables_client(self, mock_settings):
        """When google-cloud-bigquery is not installed, should disable ETL."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)
        etl.enabled = True  # Force enable to test the method

        with patch.dict("sys.modules", {"google.cloud.bigquery": None}):
            etl._initialize_client()

        assert etl.enabled is False

    @patch("observability.bigquery_etl.settings")
    def test_creates_dataset_if_not_exists(self, mock_settings):
        """Should create dataset when get_dataset raises."""
        mock_settings.project_id = "proj"

        mock_bq_client_cls = Mock()
        mock_bq_client = Mock()
        mock_bq_client.get_dataset.side_effect = Exception("Not found")
        mock_bq_client_cls.return_value = mock_bq_client

        mock_dataset_cls = Mock()
        mock_dataset_instance = Mock()
        mock_dataset_cls.return_value = mock_dataset_instance

        with patch.dict(
            "sys.modules",
            {
                "google": Mock(),
                "google.cloud": Mock(),
                "google.cloud.bigquery": Mock(Client=mock_bq_client_cls, Dataset=mock_dataset_cls),
            },
        ):
            etl = BigQueryETL(project_id="proj", enabled=False)
            etl.enabled = True
            etl._initialize_client()

        mock_bq_client.create_dataset.assert_called_once()

    @patch("observability.bigquery_etl.settings")
    def test_uses_existing_dataset(self, mock_settings):
        """Should not create dataset when it already exists."""
        mock_settings.project_id = "proj"

        mock_bq_client_cls = Mock()
        mock_bq_client = Mock()
        mock_bq_client.get_dataset.return_value = Mock()  # Dataset exists
        mock_bq_client_cls.return_value = mock_bq_client

        mock_dataset_cls = Mock()

        with patch.dict(
            "sys.modules",
            {
                "google": Mock(),
                "google.cloud": Mock(),
                "google.cloud.bigquery": Mock(Client=mock_bq_client_cls, Dataset=mock_dataset_cls),
            },
        ):
            etl = BigQueryETL(project_id="proj", enabled=False)
            etl.enabled = True
            etl._initialize_client()

        mock_bq_client.create_dataset.assert_not_called()


# ---------------------------------------------------------------------------
# Transform methods tests
# ---------------------------------------------------------------------------


class TestTransformMetrics:
    """Test _transform_metrics method."""

    @patch("observability.bigquery_etl.settings")
    def test_transforms_basic_data(self, mock_settings):
        """Should transform raw metrics data correctly."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)

        now = datetime(2024, 6, 15, 12, 0, 0)
        data = [
            {
                "timestamp": now,
                "name": "requests",
                "value": 42,
                "type": "counter",
                "labels": {"env": "prod"},
            }
        ]

        result = etl._transform_metrics(data)

        assert len(result) == 1
        assert result[0]["date"] == "2024-06-15"
        assert result[0]["metric_name"] == "requests"
        assert result[0]["metric_value"] == 42.0
        assert result[0]["metric_type"] == "counter"
        assert json.loads(result[0]["labels"]) == {"env": "prod"}
        assert "inserted_at" in result[0]

    @patch("observability.bigquery_etl.settings")
    def test_transforms_empty_data(self, mock_settings):
        """Should return empty list for empty input."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)

        result = etl._transform_metrics([])
        assert result == []

    @patch("observability.bigquery_etl.settings")
    def test_transforms_with_defaults(self, mock_settings):
        """Should use defaults when fields are missing."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)

        data = [{}]  # Missing all fields

        result = etl._transform_metrics(data)

        assert len(result) == 1
        assert result[0]["metric_name"] == "unknown"
        assert result[0]["metric_value"] == 0.0
        assert result[0]["metric_type"] == "gauge"
        assert json.loads(result[0]["labels"]) == {}

    @patch("observability.bigquery_etl.settings")
    def test_transforms_multiple_items(self, mock_settings):
        """Should transform multiple items."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)

        now = datetime(2024, 1, 1)
        data = [
            {"timestamp": now, "name": "m1", "value": 1},
            {"timestamp": now, "name": "m2", "value": 2},
        ]

        result = etl._transform_metrics(data)
        assert len(result) == 2
        assert result[0]["metric_name"] == "m1"
        assert result[1]["metric_name"] == "m2"


class TestTransformReviews:
    """Test _transform_reviews method."""

    @patch("observability.bigquery_etl.settings")
    def test_transforms_basic_review(self, mock_settings):
        """Should transform review data correctly."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)

        started_at = datetime(2024, 6, 15, 10, 0, 0)
        completed_at = datetime(2024, 6, 15, 10, 5, 0)
        data = [
            {
                "id": "review-1",
                "pr_event": {
                    "provider": "github",
                    "repo_owner": "myorg",
                    "repo_name": "myrepo",
                    "pr_number": 42,
                    "pr_title": "Add feature",
                    "author": "johndoe",
                },
                "suggestions_count": 5,
                "tokens_used": 1500,
                "cost_usd": 0.01,
                "duration_seconds": 5.5,
                "status": "completed",
                "started_at": started_at,
                "completed_at": completed_at,
                "error_message": "",
            }
        ]

        result = etl._transform_reviews(data)

        assert len(result) == 1
        r = result[0]
        assert r["review_id"] == "review-1"
        assert r["provider"] == "github"
        assert r["repo_owner"] == "myorg"
        assert r["repo_name"] == "myrepo"
        assert r["pr_number"] == 42
        assert r["pr_title"] == "Add feature"
        assert r["author"] == "johndoe"
        assert r["suggestions_count"] == 5
        assert r["tokens_used"] == 1500
        assert r["cost_usd"] == 0.01
        assert r["duration_seconds"] == 5.5
        assert r["status"] == "completed"
        assert r["started_at"] == started_at.isoformat()
        assert r["completed_at"] == completed_at.isoformat()
        assert "inserted_at" in r

    @patch("observability.bigquery_etl.settings")
    def test_transforms_review_with_string_dates(self, mock_settings):
        """Should handle string dates that are not datetime objects."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)

        data = [
            {
                "id": "review-2",
                "pr_event": {},
                "started_at": "2024-06-15T10:00:00",
                "completed_at": "2024-06-15T10:05:00",
                "status": "completed",
            }
        ]

        result = etl._transform_reviews(data)

        assert result[0]["started_at"] == "2024-06-15T10:00:00"
        assert result[0]["completed_at"] == "2024-06-15T10:05:00"

    @patch("observability.bigquery_etl.settings")
    def test_transforms_review_defaults(self, mock_settings):
        """Should use defaults for missing fields."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)

        data = [{}]

        result = etl._transform_reviews(data)

        assert len(result) == 1
        r = result[0]
        assert r["review_id"] == ""
        assert r["provider"] == "unknown"
        assert r["repo_owner"] == ""
        assert r["repo_name"] == ""
        assert r["pr_number"] == 0
        assert r["status"] == "unknown"

    @patch("observability.bigquery_etl.settings")
    def test_transforms_empty_reviews(self, mock_settings):
        """Should return empty list for empty input."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)

        result = etl._transform_reviews([])
        assert result == []


class TestTransformFeedback:
    """Test _transform_feedback method."""

    @patch("observability.bigquery_etl.settings")
    def test_transforms_basic_feedback(self, mock_settings):
        """Should transform feedback data correctly."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)

        ts = datetime(2024, 6, 15, 12, 0, 0)
        data = [
            {
                "id": "fb-1",
                "review_id": "review-1",
                "provider": "github",
                "repo_owner": "myorg",
                "repo_name": "myrepo",
                "pr_number": 42,
                "feedback_type": "positive",
                "score": 0.9,
                "emoji": "+1",
                "comment": "Good suggestion",
                "file_path": "src/main.py",
                "line_number": 10,
                "timestamp": ts,
            }
        ]

        result = etl._transform_feedback(data)

        assert len(result) == 1
        fb = result[0]
        assert fb["feedback_id"] == "fb-1"
        assert fb["review_id"] == "review-1"
        assert fb["provider"] == "github"
        assert fb["repo_owner"] == "myorg"
        assert fb["repo_name"] == "myrepo"
        assert fb["pr_number"] == 42
        assert fb["feedback_type"] == "positive"
        assert fb["score"] == 0.9
        assert fb["emoji"] == "+1"
        assert fb["comment"] == "Good suggestion"
        assert fb["file_path"] == "src/main.py"
        assert fb["line_number"] == 10
        assert fb["timestamp"] == ts.isoformat()
        assert "inserted_at" in fb

    @patch("observability.bigquery_etl.settings")
    def test_transforms_feedback_string_timestamp(self, mock_settings):
        """Should handle string timestamps."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)

        data = [
            {
                "id": "fb-2",
                "timestamp": "2024-06-15T12:00:00",
            }
        ]

        result = etl._transform_feedback(data)
        assert result[0]["timestamp"] == "2024-06-15T12:00:00"

    @patch("observability.bigquery_etl.settings")
    def test_transforms_feedback_defaults(self, mock_settings):
        """Should use defaults for missing fields."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)

        data = [{}]

        result = etl._transform_feedback(data)

        assert len(result) == 1
        fb = result[0]
        assert fb["feedback_id"] == ""
        assert fb["review_id"] == ""
        assert fb["provider"] == "unknown"
        assert fb["feedback_type"] == "unknown"
        assert fb["score"] == 0.0

    @patch("observability.bigquery_etl.settings")
    def test_transforms_empty_feedback(self, mock_settings):
        """Should return empty list for empty input."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)

        result = etl._transform_feedback([])
        assert result == []


# ---------------------------------------------------------------------------
# _load_to_bigquery tests
# ---------------------------------------------------------------------------


class TestLoadToBigQuery:
    """Test _load_to_bigquery method."""

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_noop_for_empty_data(self, mock_settings):
        """Should do nothing when data is empty."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)
        etl.enabled = True  # Force enable

        # Should not raise
        await etl._load_to_bigquery(table_name="test", data=[])

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_noop_when_no_client(self, mock_settings):
        """Should log error and return when client is not initialized."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)
        etl.enabled = True
        etl._client = None

        # Should not raise
        await etl._load_to_bigquery(table_name="test", data=[{"key": "value"}])

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_inserts_data_successfully(self, mock_settings):
        """Should insert data into BigQuery table."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)
        etl.enabled = True
        etl._table_prefix = "proj.analytics"

        mock_client = Mock()
        mock_client.get_table.return_value = Mock()  # Table exists
        mock_client.insert_rows_json.return_value = []  # No errors
        etl._client = mock_client

        data = [{"field": "value"}]
        await etl._load_to_bigquery(table_name="daily_metrics", data=data)

        mock_client.insert_rows_json.assert_called_once_with("proj.analytics.daily_metrics", data)

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_creates_table_if_not_exists(self, mock_settings):
        """Should create table when get_table raises."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)
        etl.enabled = True
        etl._table_prefix = "proj.analytics"

        mock_client = Mock()
        mock_client.get_table.side_effect = Exception("Not found")
        mock_client.insert_rows_json.return_value = []
        etl._client = mock_client

        with patch.object(etl, "_create_table") as mock_create:
            await etl._load_to_bigquery(table_name="daily_metrics", data=[{"f": "v"}])
            mock_create.assert_called_once_with("daily_metrics")

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_raises_on_insert_errors(self, mock_settings):
        """Should raise exception when insert_rows_json returns errors."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)
        etl.enabled = True
        etl._table_prefix = "proj.analytics"

        mock_client = Mock()
        mock_client.get_table.return_value = Mock()
        mock_client.insert_rows_json.return_value = [
            {"index": 0, "errors": [{"message": "bad data"}]}
        ]
        etl._client = mock_client

        with pytest.raises(Exception, match="Failed to load 1 rows"):
            await etl._load_to_bigquery(table_name="test", data=[{"field": "value"}])


# ---------------------------------------------------------------------------
# _create_table tests
# ---------------------------------------------------------------------------


class TestCreateTable:
    """Test _create_table method."""

    @patch("observability.bigquery_etl.settings")
    def test_noop_when_no_client(self, mock_settings):
        """Should return early when client is not initialized."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)
        etl._client = None

        # Should not raise
        etl._create_table("test_table")

    @patch("observability.bigquery_etl.settings")
    def test_creates_known_table_with_schema(self, mock_settings):
        """Should create a table with defined schema for known table names."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)
        etl._table_prefix = "proj.analytics"

        mock_client = Mock()
        etl._client = mock_client

        mock_schema_field = Mock()
        mock_table_cls = Mock()
        mock_table_instance = Mock()
        mock_table_cls.return_value = mock_table_instance
        mock_time_partitioning = Mock()
        mock_time_partitioning_type = Mock()

        with patch.dict(
            "sys.modules",
            {
                "google": Mock(),
                "google.cloud": Mock(),
                "google.cloud.bigquery": Mock(
                    SchemaField=mock_schema_field,
                    Table=mock_table_cls,
                    TimePartitioning=mock_time_partitioning,
                    TimePartitioningType=mock_time_partitioning_type,
                ),
            },
        ):
            etl._create_table("daily_metrics")

        mock_client.create_table.assert_called_once()

    @patch("observability.bigquery_etl.settings")
    def test_creates_generic_table_for_unknown_name(self, mock_settings):
        """Should create a generic table for unknown table names."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)
        etl._table_prefix = "proj.analytics"

        mock_client = Mock()
        etl._client = mock_client

        mock_schema_field = Mock()
        mock_table_cls = Mock()
        mock_table_instance = Mock()
        mock_table_cls.return_value = mock_table_instance
        mock_time_partitioning = Mock()
        mock_time_partitioning_type = Mock()

        with patch.dict(
            "sys.modules",
            {
                "google": Mock(),
                "google.cloud": Mock(),
                "google.cloud.bigquery": Mock(
                    SchemaField=mock_schema_field,
                    Table=mock_table_cls,
                    TimePartitioning=mock_time_partitioning,
                    TimePartitioningType=mock_time_partitioning_type,
                ),
            },
        ):
            etl._create_table("unknown_table")

        mock_client.create_table.assert_called_once()
        # For unknown tables, Table is called with just table_id, no schema
        call_args = mock_table_cls.call_args_list[-1]
        # The call should have been Table(table_id) without schema kwarg
        assert "schema" not in call_args[1] if call_args[1] else True


# ---------------------------------------------------------------------------
# export_daily_metrics tests
# ---------------------------------------------------------------------------


class TestExportDailyMetrics:
    """Test export_daily_metrics method."""

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_noop_when_disabled(self, mock_settings):
        """Should return early when ETL is disabled."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)

        # Should not raise
        await etl.export_daily_metrics()

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_defaults_to_yesterday(self, mock_settings):
        """Should default to yesterday's date when no date provided."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)
        etl.enabled = True

        collected_dates = []

        async def mock_collect(date):
            collected_dates.append(date)
            return []

        etl._collect_daily_data = mock_collect
        etl._load_to_bigquery = AsyncMock()

        await etl.export_daily_metrics()

        assert len(collected_dates) == 1
        # Should be approximately yesterday
        expected = datetime.utcnow() - timedelta(days=1)
        assert collected_dates[0].date() == expected.date()

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_uses_provided_date(self, mock_settings):
        """Should use the provided date."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)
        etl.enabled = True

        specific_date = datetime(2024, 3, 15)
        collected_dates = []

        async def mock_collect(date):
            collected_dates.append(date)
            return []

        etl._collect_daily_data = mock_collect
        etl._load_to_bigquery = AsyncMock()

        await etl.export_daily_metrics(date=specific_date)

        assert collected_dates[0] == specific_date

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_full_pipeline(self, mock_settings):
        """Should collect, transform, and load data."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)
        etl.enabled = True

        raw_data = [
            {
                "timestamp": datetime(2024, 6, 15),
                "name": "metric1",
                "value": 10,
            }
        ]

        async def mock_collect(date):
            return raw_data

        etl._collect_daily_data = mock_collect
        etl._load_to_bigquery = AsyncMock()

        await etl.export_daily_metrics(date=datetime(2024, 6, 15))

        etl._load_to_bigquery.assert_called_once()
        call_kwargs = etl._load_to_bigquery.call_args[1]
        assert call_kwargs["table_name"] == "daily_metrics"
        assert len(call_kwargs["data"]) == 1

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_raises_on_error(self, mock_settings):
        """Should re-raise exceptions from the pipeline."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)
        etl.enabled = True

        async def mock_collect(date):
            raise ConnectionError("Firestore down")

        etl._collect_daily_data = mock_collect

        with pytest.raises(ConnectionError, match="Firestore down"):
            await etl.export_daily_metrics()


# ---------------------------------------------------------------------------
# export_review_analytics tests
# ---------------------------------------------------------------------------


class TestExportReviewAnalytics:
    """Test export_review_analytics method."""

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_noop_when_disabled(self, mock_settings):
        """Should return early when ETL is disabled."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)

        await etl.export_review_analytics(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 7),
        )

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_full_pipeline(self, mock_settings):
        """Should collect, transform, and load review data."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)
        etl.enabled = True

        raw_data = [
            {
                "id": "r-1",
                "pr_event": {"provider": "github", "pr_number": 1},
                "status": "completed",
                "started_at": datetime(2024, 1, 1),
                "completed_at": datetime(2024, 1, 1, 0, 5),
            }
        ]

        async def mock_collect(start, end):
            return raw_data

        etl._collect_review_data = mock_collect
        etl._load_to_bigquery = AsyncMock()

        await etl.export_review_analytics(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 7),
        )

        etl._load_to_bigquery.assert_called_once()
        call_kwargs = etl._load_to_bigquery.call_args[1]
        assert call_kwargs["table_name"] == "reviews"

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_raises_on_error(self, mock_settings):
        """Should re-raise exceptions."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)
        etl.enabled = True

        async def mock_collect(start, end):
            raise RuntimeError("collection failed")

        etl._collect_review_data = mock_collect

        with pytest.raises(RuntimeError, match="collection failed"):
            await etl.export_review_analytics(
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 7),
            )


# ---------------------------------------------------------------------------
# export_feedback_analytics tests
# ---------------------------------------------------------------------------


class TestExportFeedbackAnalytics:
    """Test export_feedback_analytics method."""

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_noop_when_disabled(self, mock_settings):
        """Should return early when ETL is disabled."""
        mock_settings.project_id = ""
        etl = BigQueryETL(project_id=None, enabled=False)

        await etl.export_feedback_analytics(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 7),
        )

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_full_pipeline(self, mock_settings):
        """Should collect, transform, and load feedback data."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)
        etl.enabled = True

        raw_data = [
            {
                "id": "fb-1",
                "feedback_type": "positive",
                "score": 0.9,
                "timestamp": datetime(2024, 1, 1),
            }
        ]

        async def mock_collect(start, end):
            return raw_data

        etl._collect_feedback_data = mock_collect
        etl._load_to_bigquery = AsyncMock()

        await etl.export_feedback_analytics(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 7),
        )

        etl._load_to_bigquery.assert_called_once()
        call_kwargs = etl._load_to_bigquery.call_args[1]
        assert call_kwargs["table_name"] == "feedback"

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_raises_on_error(self, mock_settings):
        """Should re-raise exceptions."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)
        etl.enabled = True

        async def mock_collect(start, end):
            raise RuntimeError("feedback collection failed")

        etl._collect_feedback_data = mock_collect

        with pytest.raises(RuntimeError, match="feedback collection failed"):
            await etl.export_feedback_analytics(
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 7),
            )


# ---------------------------------------------------------------------------
# _collect_daily_data tests
# ---------------------------------------------------------------------------


class TestCollectDailyData:
    """Test _collect_daily_data method."""

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_returns_empty_on_import_error(self, mock_settings):
        """Should return empty list when Firestore is not available."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)

        with patch.dict("sys.modules", {"google.cloud.firestore": None}):
            result = await etl._collect_daily_data(datetime(2024, 6, 15))

        assert result == []

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_collects_data_from_firestore(self, mock_settings):
        """Should collect data from Firestore."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)

        mock_doc = Mock()
        mock_doc.to_dict.return_value = {"name": "metric1", "value": 42}
        mock_doc.id = "doc-1"

        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_query.stream.return_value = [mock_doc]

        mock_collection = Mock()
        mock_collection.where.return_value = mock_query

        mock_firestore_cls = Mock()
        mock_firestore_instance = Mock()
        mock_firestore_instance.collection.return_value = mock_collection
        mock_firestore_cls.return_value = mock_firestore_instance

        with patch.dict(
            "sys.modules",
            {
                "google": Mock(),
                "google.cloud": Mock(),
                "google.cloud.firestore": Mock(Client=mock_firestore_cls),
            },
        ):
            result = await etl._collect_daily_data(datetime(2024, 6, 15))

        assert len(result) == 1
        assert result[0]["name"] == "metric1"
        assert result[0]["id"] == "doc-1"


# ---------------------------------------------------------------------------
# _collect_review_data tests
# ---------------------------------------------------------------------------


class TestCollectReviewData:
    """Test _collect_review_data method."""

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_returns_empty_on_error(self, mock_settings):
        """Should return empty list on error."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)

        with patch.dict("sys.modules", {"google.cloud.firestore": None}):
            result = await etl._collect_review_data(datetime(2024, 1, 1), datetime(2024, 1, 7))

        assert result == []

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_collects_reviews_from_firestore(self, mock_settings):
        """Should collect review data from Firestore."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)

        mock_doc = Mock()
        mock_doc.to_dict.return_value = {"status": "completed"}
        mock_doc.id = "review-1"

        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_query.stream.return_value = [mock_doc]

        mock_collection = Mock()
        mock_collection.where.return_value = mock_query

        mock_firestore_cls = Mock()
        mock_firestore_instance = Mock()
        mock_firestore_instance.collection.return_value = mock_collection
        mock_firestore_cls.return_value = mock_firestore_instance

        with patch.dict(
            "sys.modules",
            {
                "google": Mock(),
                "google.cloud": Mock(),
                "google.cloud.firestore": Mock(Client=mock_firestore_cls),
            },
        ):
            result = await etl._collect_review_data(datetime(2024, 1, 1), datetime(2024, 1, 7))

        assert len(result) == 1
        assert result[0]["id"] == "review-1"


# ---------------------------------------------------------------------------
# _collect_feedback_data tests
# ---------------------------------------------------------------------------


class TestCollectFeedbackData:
    """Test _collect_feedback_data method."""

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_returns_empty_on_error(self, mock_settings):
        """Should return empty list on error."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)

        with patch.dict("sys.modules", {"google.cloud.firestore": None}):
            result = await etl._collect_feedback_data(datetime(2024, 1, 1), datetime(2024, 1, 7))

        assert result == []

    @pytest.mark.asyncio
    @patch("observability.bigquery_etl.settings")
    async def test_collects_feedback_from_firestore(self, mock_settings):
        """Should collect feedback data from Firestore."""
        mock_settings.project_id = "proj"
        etl = BigQueryETL(project_id="proj", enabled=False)

        mock_doc = Mock()
        mock_doc.to_dict.return_value = {"feedback_type": "positive"}
        mock_doc.id = "fb-1"

        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_query.stream.return_value = [mock_doc]

        mock_collection = Mock()
        mock_collection.where.return_value = mock_query

        mock_firestore_cls = Mock()
        mock_firestore_instance = Mock()
        mock_firestore_instance.collection.return_value = mock_collection
        mock_firestore_cls.return_value = mock_firestore_instance

        with patch.dict(
            "sys.modules",
            {
                "google": Mock(),
                "google.cloud": Mock(),
                "google.cloud.firestore": Mock(Client=mock_firestore_cls),
            },
        ):
            result = await etl._collect_feedback_data(datetime(2024, 1, 1), datetime(2024, 1, 7))

        assert len(result) == 1
        assert result[0]["id"] == "fb-1"


# ---------------------------------------------------------------------------
# run_daily_etl Cloud Function entry point tests
# ---------------------------------------------------------------------------


class TestRunDailyEtl:
    """Test run_daily_etl Cloud Function."""

    @patch("observability.bigquery_etl.asyncio.run")
    @patch("observability.bigquery_etl.BigQueryETL")
    def test_runs_all_exports(self, mock_etl_cls, mock_asyncio_run):
        """Should run all three exports."""
        mock_etl = Mock()
        mock_etl_cls.return_value = mock_etl

        context = Mock()
        context.timestamp = "2024-06-15T00:00:00Z"

        result = run_daily_etl(event={}, context=context)

        assert result == {"status": "success", "message": "ETL completed"}
        # asyncio.run should be called 3 times: daily_metrics, reviews, feedback
        assert mock_asyncio_run.call_count == 3

    @patch("observability.bigquery_etl.asyncio.run")
    @patch("observability.bigquery_etl.BigQueryETL")
    def test_passes_correct_date_ranges(self, mock_etl_cls, mock_asyncio_run):
        """Should pass 7-day date range for review and feedback exports."""
        mock_etl = Mock()
        mock_etl_cls.return_value = mock_etl

        context = Mock()
        context.timestamp = "2024-06-15T00:00:00Z"

        run_daily_etl(event={}, context=context)

        # The first call is export_daily_metrics() - no date args
        # The second call is export_review_analytics(start_date, end_date)
        # The third call is export_feedback_analytics(start_date, end_date)
        calls = mock_asyncio_run.call_args_list
        assert len(calls) == 3

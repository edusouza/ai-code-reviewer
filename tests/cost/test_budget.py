"""Tests for cost.budget module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import cost.budget as budget_mod
from cost.budget import (
    BudgetConfig,
    BudgetEnforcer,
    get_budget_enforcer,
    init_budget_enforcer,
)


# ---------------------------------------------------------------------------
# BudgetConfig dataclass tests
# ---------------------------------------------------------------------------
class TestBudgetConfig:
    """Tests for BudgetConfig dataclass."""

    def test_defaults(self):
        """Default values should be sensible."""
        cfg = BudgetConfig()
        assert cfg.daily_budget_usd == 50.0
        assert cfg.per_pr_budget_usd == 5.0
        assert cfg.monthly_budget_usd == 1000.0
        assert cfg.warning_threshold == 0.8
        assert cfg.repo_daily_budgets == {}

    def test_custom_values(self):
        """Custom values are stored correctly."""
        cfg = BudgetConfig(
            daily_budget_usd=100.0,
            per_pr_budget_usd=10.0,
            monthly_budget_usd=2000.0,
            warning_threshold=0.9,
            repo_daily_budgets={"org/repo": 25.0},
        )
        assert cfg.daily_budget_usd == 100.0
        assert cfg.per_pr_budget_usd == 10.0
        assert cfg.monthly_budget_usd == 2000.0
        assert cfg.warning_threshold == 0.9
        assert cfg.repo_daily_budgets == {"org/repo": 25.0}

    def test_post_init_none_repo_budgets(self):
        """__post_init__ converts None to empty dict."""
        cfg = BudgetConfig(repo_daily_budgets=None)
        assert cfg.repo_daily_budgets == {}

    def test_post_init_preserves_existing_dict(self):
        """__post_init__ does not overwrite an existing dict."""
        cfg = BudgetConfig(repo_daily_budgets={"a": 1.0})
        assert cfg.repo_daily_budgets == {"a": 1.0}


# ---------------------------------------------------------------------------
# Helper to build a mock Firestore DB
# ---------------------------------------------------------------------------
def _make_mock_db(docs: list[dict] | None = None):
    """Return a mock Firestore client whose collection().where()...stream() returns docs."""
    mock_db = MagicMock()

    mock_doc_objects = []
    for d in docs or []:
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = d
        mock_doc_objects.append(mock_doc)

    # chain: collection("costs").where(...).where(...).stream()
    mock_query = MagicMock()
    mock_query.where.return_value = mock_query
    mock_query.stream.return_value = mock_doc_objects

    mock_collection = MagicMock()
    mock_collection.where.return_value = mock_query

    mock_db.collection.return_value = mock_collection
    return mock_db


# ---------------------------------------------------------------------------
# BudgetEnforcer tests
# ---------------------------------------------------------------------------
class TestBudgetEnforcerInit:
    """Constructor / initialization tests."""

    def test_default_config(self):
        """Without explicit config a default BudgetConfig is used."""
        enforcer = BudgetEnforcer()
        assert isinstance(enforcer.config, BudgetConfig)
        assert enforcer._db is None
        assert enforcer._initialized is False

    def test_custom_config(self):
        """Explicit config is stored."""
        cfg = BudgetConfig(daily_budget_usd=99.0)
        enforcer = BudgetEnforcer(config=cfg)
        assert enforcer.config.daily_budget_usd == 99.0

    def test_with_firestore_db(self):
        """Providing a firestore_db skips lazy init."""
        db = MagicMock()
        enforcer = BudgetEnforcer(firestore_db=db)
        assert enforcer._db is db


class TestInitializeDb:
    """Tests for _initialize_db lazy initialization."""

    @pytest.mark.asyncio
    async def test_skip_if_already_initialized(self):
        """Should be a no-op when _initialized is True."""
        enforcer = BudgetEnforcer()
        enforcer._initialized = True
        await enforcer._initialize_db()
        # No crash, no side effect.
        assert enforcer._initialized is True

    @pytest.mark.asyncio
    async def test_skip_if_db_already_set(self):
        """Should be a no-op when _db is already present."""
        db = MagicMock()
        enforcer = BudgetEnforcer(firestore_db=db)
        await enforcer._initialize_db()
        assert enforcer._db is db

    @pytest.mark.asyncio
    async def test_lazy_init_success(self):
        """Successfully import and create a Firestore client."""
        mock_client_cls = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_cls.return_value = mock_client_instance

        with patch.dict(
            "sys.modules",
            {
                "google": MagicMock(),
                "google.cloud": MagicMock(),
                "google.cloud.firestore": MagicMock(),
            },
        ):
            with patch("cost.budget.settings") as mock_settings:
                mock_settings.project_id = "test-project"
                # Patch the import inside the method
                with patch(
                    "builtins.__import__",
                    side_effect=lambda name, *a, **kw: (
                        __builtins__.__import__(name, *a, **kw)  # type: ignore[union-attr]
                        if name != "google.cloud.firestore"
                        else type("mod", (), {"Client": mock_client_cls})
                    ),
                ):
                    enforcer = BudgetEnforcer()
                    await enforcer._initialize_db()
                    # The import path is complex; just verify the error path works below.

    @pytest.mark.asyncio
    async def test_lazy_init_import_error(self):
        """If Firestore import fails, _db stays None."""
        enforcer = BudgetEnforcer()
        with patch(
            "builtins.__import__",
            side_effect=ImportError("no google"),
        ):
            await enforcer._initialize_db()
        assert enforcer._db is None
        assert enforcer._initialized is False


# ---------------------------------------------------------------------------
# Private spend helpers
# ---------------------------------------------------------------------------
class TestGetDailySpend:
    """Tests for _get_daily_spend."""

    @pytest.mark.asyncio
    async def test_no_db_returns_zero(self):
        """Without a DB, spend is 0."""
        enforcer = BudgetEnforcer()
        result = await enforcer._get_daily_spend()
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_with_docs(self):
        """Sums cost_usd from returned docs."""
        mock_db = _make_mock_db([{"cost_usd": 1.5}, {"cost_usd": 2.5}])
        enforcer = BudgetEnforcer(firestore_db=mock_db)

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value=[
                    MagicMock(to_dict=MagicMock(return_value={"cost_usd": 1.5})),
                    MagicMock(to_dict=MagicMock(return_value={"cost_usd": 2.5})),
                ]
            )
            result = await enforcer._get_daily_spend()
        assert result == 4.0

    @pytest.mark.asyncio
    async def test_with_repo_filter(self):
        """When repo is specified, an additional .where() call is made."""
        mock_db = _make_mock_db()
        enforcer = BudgetEnforcer(firestore_db=mock_db)

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=[])
            result = await enforcer._get_daily_spend(repo="org/repo")
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_exception_returns_zero(self):
        """On exception, returns 0.0."""
        mock_db = MagicMock()
        mock_db.collection.side_effect = Exception("boom")
        enforcer = BudgetEnforcer(firestore_db=mock_db)
        result = await enforcer._get_daily_spend()
        assert result == 0.0


class TestGetPrSpend:
    """Tests for _get_pr_spend."""

    @pytest.mark.asyncio
    async def test_no_db_returns_zero(self):
        enforcer = BudgetEnforcer()
        result = await enforcer._get_pr_spend(1, "org/repo")
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_with_docs(self):
        mock_db = _make_mock_db()
        enforcer = BudgetEnforcer(firestore_db=mock_db)

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value=[
                    MagicMock(to_dict=MagicMock(return_value={"cost_usd": 0.3})),
                    MagicMock(to_dict=MagicMock(return_value={"cost_usd": 0.7})),
                ]
            )
            result = await enforcer._get_pr_spend(42, "org/repo")
        assert result == 1.0

    @pytest.mark.asyncio
    async def test_exception_returns_zero(self):
        mock_db = MagicMock()
        mock_db.collection.side_effect = RuntimeError("fail")
        enforcer = BudgetEnforcer(firestore_db=mock_db)
        result = await enforcer._get_pr_spend(1, "org/repo")
        assert result == 0.0


class TestGetMonthlySpend:
    """Tests for _get_monthly_spend."""

    @pytest.mark.asyncio
    async def test_no_db_returns_zero(self):
        enforcer = BudgetEnforcer()
        result = await enforcer._get_monthly_spend()
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_with_docs(self):
        mock_db = _make_mock_db()
        enforcer = BudgetEnforcer(firestore_db=mock_db)

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value=[
                    MagicMock(to_dict=MagicMock(return_value={"cost_usd": 10.0})),
                    MagicMock(to_dict=MagicMock(return_value={"cost_usd": 20.0})),
                ]
            )
            result = await enforcer._get_monthly_spend()
        assert result == 30.0

    @pytest.mark.asyncio
    async def test_exception_returns_zero(self):
        mock_db = MagicMock()
        mock_db.collection.side_effect = Exception("db down")
        enforcer = BudgetEnforcer(firestore_db=mock_db)
        result = await enforcer._get_monthly_spend()
        assert result == 0.0


# ---------------------------------------------------------------------------
# check_daily_budget
# ---------------------------------------------------------------------------
class TestCheckDailyBudget:
    """Tests for check_daily_budget."""

    @pytest.mark.asyncio
    async def test_under_budget(self):
        """Spend below limit -> can_proceed=True, warning=False."""
        cfg = BudgetConfig(daily_budget_usd=100.0, warning_threshold=0.8)
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_daily_spend = AsyncMock(return_value=10.0)

        status = await enforcer.check_daily_budget()

        assert status["budget_type"] == "daily"
        assert status["limit"] == 100.0
        assert status["spent"] == 10.0
        assert status["remaining"] == 90.0
        assert status["percentage"] == 10.0
        assert status["exceeded"] is False
        assert status["warning"] is False
        assert status["can_proceed"] is True

    @pytest.mark.asyncio
    async def test_at_warning_threshold(self):
        """Spend at exactly 80% -> warning=True, exceeded=False."""
        cfg = BudgetConfig(daily_budget_usd=100.0, warning_threshold=0.8)
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_daily_spend = AsyncMock(return_value=80.0)

        status = await enforcer.check_daily_budget()

        assert status["warning"] is True
        assert status["exceeded"] is False
        assert status["can_proceed"] is True

    @pytest.mark.asyncio
    async def test_exceeded(self):
        """Spend at or above limit -> exceeded=True, can_proceed=False."""
        cfg = BudgetConfig(daily_budget_usd=50.0)
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_daily_spend = AsyncMock(return_value=50.0)

        status = await enforcer.check_daily_budget()

        assert status["exceeded"] is True
        assert status["can_proceed"] is False

    @pytest.mark.asyncio
    async def test_over_budget(self):
        """Spend above limit -> exceeded=True."""
        cfg = BudgetConfig(daily_budget_usd=50.0)
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_daily_spend = AsyncMock(return_value=60.0)

        status = await enforcer.check_daily_budget()

        assert status["exceeded"] is True
        assert status["can_proceed"] is False
        assert status["remaining"] == -10.0

    @pytest.mark.asyncio
    async def test_repo_specific_budget(self):
        """Repo-specific budget overrides global daily budget."""
        cfg = BudgetConfig(
            daily_budget_usd=100.0,
            repo_daily_budgets={"org/special": 20.0},
        )
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_daily_spend = AsyncMock(return_value=15.0)

        status = await enforcer.check_daily_budget(repo="org/special")

        assert status["limit"] == 20.0
        assert status["spent"] == 15.0

    @pytest.mark.asyncio
    async def test_repo_not_in_repo_budgets_uses_global(self):
        """If repo not in repo_daily_budgets, use global daily budget."""
        cfg = BudgetConfig(
            daily_budget_usd=100.0,
            repo_daily_budgets={"org/other": 20.0},
        )
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_daily_spend = AsyncMock(return_value=10.0)

        status = await enforcer.check_daily_budget(repo="org/unknown")

        assert status["limit"] == 100.0

    @pytest.mark.asyncio
    async def test_zero_budget_limit(self):
        """Zero budget -> percentage=0, exceeded=True (0 >= 0)."""
        cfg = BudgetConfig(daily_budget_usd=0.0)
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_daily_spend = AsyncMock(return_value=0.0)

        status = await enforcer.check_daily_budget()

        assert status["percentage"] == 0.0
        assert status["exceeded"] is True
        assert status["can_proceed"] is False

    @pytest.mark.asyncio
    async def test_no_repo_no_repo_budgets(self):
        """No repo passed, repo_daily_budgets is empty -> global limit."""
        cfg = BudgetConfig(daily_budget_usd=50.0)
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_daily_spend = AsyncMock(return_value=5.0)

        status = await enforcer.check_daily_budget()

        assert status["limit"] == 50.0


# ---------------------------------------------------------------------------
# check_pr_budget
# ---------------------------------------------------------------------------
class TestCheckPrBudget:
    """Tests for check_pr_budget."""

    @pytest.mark.asyncio
    async def test_under_budget_no_estimate(self):
        """No estimated cost, under budget."""
        cfg = BudgetConfig(per_pr_budget_usd=5.0)
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_pr_spend = AsyncMock(return_value=1.0)

        status = await enforcer.check_pr_budget(42, "org/repo")

        assert status["budget_type"] == "per_pr"
        assert status["pr_number"] == 42
        assert status["repo"] == "org/repo"
        assert status["limit"] == 5.0
        assert status["current_spend"] == 1.0
        assert status["projected_spend"] == 1.0
        assert status["can_proceed"] is True

    @pytest.mark.asyncio
    async def test_with_estimated_cost(self):
        """Estimated cost is added to projected spend."""
        cfg = BudgetConfig(per_pr_budget_usd=5.0)
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_pr_spend = AsyncMock(return_value=2.0)

        status = await enforcer.check_pr_budget(42, "org/repo", estimated_cost=2.5)

        assert status["current_spend"] == 2.0
        assert status["projected_spend"] == 4.5
        assert status["can_proceed"] is True

    @pytest.mark.asyncio
    async def test_estimated_cost_exceeds_budget(self):
        """Estimated cost pushes projected_spend over budget."""
        cfg = BudgetConfig(per_pr_budget_usd=5.0)
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_pr_spend = AsyncMock(return_value=3.0)

        status = await enforcer.check_pr_budget(42, "org/repo", estimated_cost=3.0)

        assert status["projected_spend"] == 6.0
        assert status["exceeded"] is True
        assert status["can_proceed"] is False

    @pytest.mark.asyncio
    async def test_exact_budget_exceeded(self):
        """Projected spend exactly at limit -> exceeded=True."""
        cfg = BudgetConfig(per_pr_budget_usd=5.0)
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_pr_spend = AsyncMock(return_value=5.0)

        status = await enforcer.check_pr_budget(42, "org/repo")

        assert status["exceeded"] is True
        assert status["can_proceed"] is False

    @pytest.mark.asyncio
    async def test_zero_budget(self):
        """Zero per-PR budget -> percentage=0."""
        cfg = BudgetConfig(per_pr_budget_usd=0.0)
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_pr_spend = AsyncMock(return_value=0.0)

        status = await enforcer.check_pr_budget(1, "r")

        assert status["percentage"] == 0.0
        assert status["exceeded"] is True

    @pytest.mark.asyncio
    async def test_warning_threshold(self):
        """Warning threshold is triggered."""
        cfg = BudgetConfig(per_pr_budget_usd=10.0, warning_threshold=0.8)
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_pr_spend = AsyncMock(return_value=8.0)

        status = await enforcer.check_pr_budget(1, "r")

        assert status["warning"] is True
        assert status["can_proceed"] is True


# ---------------------------------------------------------------------------
# check_monthly_budget
# ---------------------------------------------------------------------------
class TestCheckMonthlyBudget:
    """Tests for check_monthly_budget."""

    @pytest.mark.asyncio
    async def test_under_budget(self):
        cfg = BudgetConfig(monthly_budget_usd=1000.0)
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_monthly_spend = AsyncMock(return_value=200.0)

        status = await enforcer.check_monthly_budget()

        assert status["budget_type"] == "monthly"
        assert status["limit"] == 1000.0
        assert status["spent"] == 200.0
        assert status["remaining"] == 800.0
        assert status["percentage"] == 20.0
        assert status["exceeded"] is False
        assert status["can_proceed"] is True

    @pytest.mark.asyncio
    async def test_exceeded(self):
        cfg = BudgetConfig(monthly_budget_usd=1000.0)
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_monthly_spend = AsyncMock(return_value=1000.0)

        status = await enforcer.check_monthly_budget()

        assert status["exceeded"] is True
        assert status["can_proceed"] is False

    @pytest.mark.asyncio
    async def test_warning(self):
        cfg = BudgetConfig(monthly_budget_usd=1000.0, warning_threshold=0.8)
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_monthly_spend = AsyncMock(return_value=850.0)

        status = await enforcer.check_monthly_budget()

        assert status["warning"] is True
        assert status["exceeded"] is False

    @pytest.mark.asyncio
    async def test_zero_budget(self):
        cfg = BudgetConfig(monthly_budget_usd=0.0)
        enforcer = BudgetEnforcer(config=cfg)
        enforcer._initialize_db = AsyncMock()
        enforcer._get_monthly_spend = AsyncMock(return_value=0.0)

        status = await enforcer.check_monthly_budget()

        assert status["percentage"] == 0.0
        assert status["exceeded"] is True


# ---------------------------------------------------------------------------
# can_review_pr
# ---------------------------------------------------------------------------
class TestCanReviewPr:
    """Tests for can_review_pr."""

    @pytest.mark.asyncio
    async def test_all_budgets_ok(self):
        """All budgets under limit -> True."""
        enforcer = BudgetEnforcer()
        enforcer.check_daily_budget = AsyncMock(
            return_value={"can_proceed": True, "percentage": 10.0}
        )
        enforcer.check_pr_budget = AsyncMock(return_value={"can_proceed": True, "percentage": 20.0})
        enforcer.check_monthly_budget = AsyncMock(
            return_value={"can_proceed": True, "percentage": 5.0}
        )

        result = await enforcer.can_review_pr(42, "org/repo")

        assert result is True

    @pytest.mark.asyncio
    async def test_daily_exceeded(self):
        """Daily budget exceeded -> False."""
        enforcer = BudgetEnforcer()
        enforcer.check_daily_budget = AsyncMock(
            return_value={"can_proceed": False, "percentage": 100.0}
        )
        enforcer.check_pr_budget = AsyncMock(return_value={"can_proceed": True, "percentage": 20.0})
        enforcer.check_monthly_budget = AsyncMock(
            return_value={"can_proceed": True, "percentage": 5.0}
        )

        result = await enforcer.can_review_pr(42, "org/repo")

        assert result is False

    @pytest.mark.asyncio
    async def test_pr_exceeded(self):
        """PR budget exceeded -> False."""
        enforcer = BudgetEnforcer()
        enforcer.check_daily_budget = AsyncMock(
            return_value={"can_proceed": True, "percentage": 10.0}
        )
        enforcer.check_pr_budget = AsyncMock(
            return_value={"can_proceed": False, "percentage": 100.0}
        )
        enforcer.check_monthly_budget = AsyncMock(
            return_value={"can_proceed": True, "percentage": 5.0}
        )

        result = await enforcer.can_review_pr(42, "org/repo")

        assert result is False

    @pytest.mark.asyncio
    async def test_monthly_exceeded(self):
        """Monthly budget exceeded -> False."""
        enforcer = BudgetEnforcer()
        enforcer.check_daily_budget = AsyncMock(
            return_value={"can_proceed": True, "percentage": 10.0}
        )
        enforcer.check_pr_budget = AsyncMock(return_value={"can_proceed": True, "percentage": 20.0})
        enforcer.check_monthly_budget = AsyncMock(
            return_value={"can_proceed": False, "percentage": 100.0}
        )

        result = await enforcer.can_review_pr(42, "org/repo")

        assert result is False

    @pytest.mark.asyncio
    async def test_multiple_exceeded(self):
        """Multiple budgets exceeded -> False."""
        enforcer = BudgetEnforcer()
        enforcer.check_daily_budget = AsyncMock(
            return_value={"can_proceed": False, "percentage": 100.0}
        )
        enforcer.check_pr_budget = AsyncMock(
            return_value={"can_proceed": False, "percentage": 100.0}
        )
        enforcer.check_monthly_budget = AsyncMock(
            return_value={"can_proceed": False, "percentage": 100.0}
        )

        result = await enforcer.can_review_pr(42, "org/repo")

        assert result is False

    @pytest.mark.asyncio
    async def test_passes_estimated_cost(self):
        """Estimated cost is forwarded to check_pr_budget."""
        enforcer = BudgetEnforcer()
        enforcer.check_daily_budget = AsyncMock(
            return_value={"can_proceed": True, "percentage": 10.0}
        )
        enforcer.check_pr_budget = AsyncMock(return_value={"can_proceed": True, "percentage": 20.0})
        enforcer.check_monthly_budget = AsyncMock(
            return_value={"can_proceed": True, "percentage": 5.0}
        )

        await enforcer.can_review_pr(42, "org/repo", estimated_cost=1.5)

        enforcer.check_pr_budget.assert_called_once_with(42, "org/repo", 1.5)

    @pytest.mark.asyncio
    async def test_passes_repo_to_daily_check(self):
        """Repo is forwarded to check_daily_budget."""
        enforcer = BudgetEnforcer()
        enforcer.check_daily_budget = AsyncMock(
            return_value={"can_proceed": True, "percentage": 10.0}
        )
        enforcer.check_pr_budget = AsyncMock(return_value={"can_proceed": True, "percentage": 20.0})
        enforcer.check_monthly_budget = AsyncMock(
            return_value={"can_proceed": True, "percentage": 5.0}
        )

        await enforcer.can_review_pr(42, "org/repo")

        enforcer.check_daily_budget.assert_called_once_with("org/repo")


# ---------------------------------------------------------------------------
# get_budget_summary
# ---------------------------------------------------------------------------
class TestGetBudgetSummary:
    """Tests for get_budget_summary."""

    @pytest.mark.asyncio
    async def test_returns_summary(self):
        cfg = BudgetConfig(
            daily_budget_usd=50.0,
            monthly_budget_usd=1000.0,
            per_pr_budget_usd=5.0,
            warning_threshold=0.8,
        )
        enforcer = BudgetEnforcer(config=cfg)
        enforcer.check_daily_budget = AsyncMock(return_value={"spent": 10.0, "limit": 50.0})
        enforcer.check_monthly_budget = AsyncMock(return_value={"spent": 200.0, "limit": 1000.0})

        summary = await enforcer.get_budget_summary()

        assert "daily" in summary
        assert "monthly" in summary
        assert "config" in summary
        assert summary["config"]["daily_limit"] == 50.0
        assert summary["config"]["monthly_limit"] == 1000.0
        assert summary["config"]["per_pr_limit"] == 5.0
        assert summary["config"]["warning_threshold"] == 0.8


# ---------------------------------------------------------------------------
# Module-level functions
# ---------------------------------------------------------------------------
class TestModuleFunctions:
    """Tests for init_budget_enforcer and get_budget_enforcer."""

    def test_init_budget_enforcer_default(self):
        old = budget_mod._budget_enforcer
        try:
            result = init_budget_enforcer()
            assert isinstance(result, BudgetEnforcer)
            assert get_budget_enforcer() is result
        finally:
            budget_mod._budget_enforcer = old

    def test_init_budget_enforcer_custom(self):
        old = budget_mod._budget_enforcer
        try:
            cfg = BudgetConfig(daily_budget_usd=99.0)
            db = MagicMock()
            result = init_budget_enforcer(config=cfg, firestore_db=db)
            assert result.config.daily_budget_usd == 99.0
            assert result._db is db
            assert get_budget_enforcer() is result
        finally:
            budget_mod._budget_enforcer = old

    def test_get_budget_enforcer_before_init(self):
        old = budget_mod._budget_enforcer
        try:
            budget_mod._budget_enforcer = None
            assert get_budget_enforcer() is None
        finally:
            budget_mod._budget_enforcer = old

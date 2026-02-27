"""Budget enforcement for cost control."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class BudgetConfig:
    """Budget configuration."""

    daily_budget_usd: float = 50.0
    per_pr_budget_usd: float = 5.0
    monthly_budget_usd: float = 1000.0
    warning_threshold: float = 0.8  # Warn at 80% of budget

    # Per-repo budgets
    repo_daily_budgets: dict[str, float] | None = None

    def __post_init__(self):
        if self.repo_daily_budgets is None:
            self.repo_daily_budgets = {}


class BudgetEnforcer:
    """Enforce budget limits on reviews."""

    def __init__(self, config: BudgetConfig | None = None, firestore_db: Any | None = None):
        """
        Initialize budget enforcer.

        Args:
            config: Budget configuration
            firestore_db: Optional Firestore client
        """
        self.config = config or BudgetConfig()
        self._db = firestore_db
        self._initialized = False

    async def _initialize_db(self):
        """Lazy initialization of Firestore."""
        if self._initialized or self._db is not None:
            return

        try:
            from google.cloud import firestore

            self._db = firestore.Client(project=settings.project_id)
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {e}")

    async def check_daily_budget(self, repo: str | None = None) -> dict[str, Any]:
        """
        Check if daily budget has been exceeded.

        Args:
            repo: Optional repository to check specific budget

        Returns:
            Budget status dictionary
        """
        await self._initialize_db()

        # Get daily spend
        daily_spend = await self._get_daily_spend(repo)

        # Determine budget limit
        repo_budgets = self.config.repo_daily_budgets or {}
        if repo and repo in repo_budgets:
            budget_limit = repo_budgets[repo]
        else:
            budget_limit = self.config.daily_budget_usd

        # Calculate status
        percentage = (daily_spend / budget_limit) if budget_limit > 0 else 0

        status = {
            "budget_type": "daily",
            "limit": budget_limit,
            "spent": round(daily_spend, 4),
            "remaining": round(budget_limit - daily_spend, 4),
            "percentage": round(percentage * 100, 2),
            "exceeded": daily_spend >= budget_limit,
            "warning": percentage >= self.config.warning_threshold,
            "can_proceed": daily_spend < budget_limit,
        }

        if status["exceeded"]:
            logger.warning(
                f"Daily budget exceeded: ${daily_spend:.2f} / ${budget_limit:.2f} "
                f"({percentage * 100:.1f}%)"
            )
        elif status["warning"]:
            logger.warning(
                f"Daily budget warning: ${daily_spend:.2f} / ${budget_limit:.2f} "
                f"({percentage * 100:.1f}%)"
            )

        return status

    async def check_pr_budget(
        self, pr_number: int, repo: str, estimated_cost: float | None = None
    ) -> dict[str, Any]:
        """
        Check if PR budget allows for review.

        Args:
            pr_number: PR number
            repo: Repository identifier
            estimated_cost: Optional estimated cost for this review

        Returns:
            Budget status dictionary
        """
        await self._initialize_db()

        # Get current PR spend
        current_spend = await self._get_pr_spend(pr_number, repo)

        budget_limit = self.config.per_pr_budget_usd

        # Calculate with estimated cost
        projected_spend = current_spend + estimated_cost if estimated_cost else current_spend

        percentage = (projected_spend / budget_limit) if budget_limit > 0 else 0

        status = {
            "budget_type": "per_pr",
            "pr_number": pr_number,
            "repo": repo,
            "limit": budget_limit,
            "current_spend": round(current_spend, 4),
            "projected_spend": round(projected_spend, 4),
            "remaining": round(budget_limit - projected_spend, 4),
            "percentage": round(percentage * 100, 2),
            "exceeded": projected_spend >= budget_limit,
            "warning": percentage >= self.config.warning_threshold,
            "can_proceed": projected_spend < budget_limit,
        }

        return status

    async def check_monthly_budget(self) -> dict[str, Any]:
        """Check monthly budget status."""
        await self._initialize_db()

        monthly_spend = await self._get_monthly_spend()
        budget_limit = self.config.monthly_budget_usd

        percentage = (monthly_spend / budget_limit) if budget_limit > 0 else 0

        status = {
            "budget_type": "monthly",
            "limit": budget_limit,
            "spent": round(monthly_spend, 4),
            "remaining": round(budget_limit - monthly_spend, 4),
            "percentage": round(percentage * 100, 2),
            "exceeded": monthly_spend >= budget_limit,
            "warning": percentage >= self.config.warning_threshold,
            "can_proceed": monthly_spend < budget_limit,
        }

        return status

    async def can_review_pr(
        self, pr_number: int, repo: str, estimated_cost: float | None = None
    ) -> bool:
        """
        Check if a PR can be reviewed within budget.

        Args:
            pr_number: PR number
            repo: Repository identifier
            estimated_cost: Optional estimated cost

        Returns:
            True if review can proceed
        """
        # Check all budgets
        daily_status = await self.check_daily_budget(repo)
        pr_status = await self.check_pr_budget(pr_number, repo, estimated_cost)
        monthly_status = await self.check_monthly_budget()

        can_proceed = (
            daily_status["can_proceed"]
            and pr_status["can_proceed"]
            and monthly_status["can_proceed"]
        )

        if not can_proceed:
            logger.warning(
                f"Review blocked for {repo}#{pr_number}: "
                f"Daily: {daily_status['percentage']:.1f}%, "
                f"PR: {pr_status['percentage']:.1f}%, "
                f"Monthly: {monthly_status['percentage']:.1f}%"
            )

        return can_proceed

    async def get_budget_summary(self) -> dict[str, Any]:
        """Get comprehensive budget summary."""
        daily = await self.check_daily_budget()
        monthly = await self.check_monthly_budget()

        return {
            "daily": daily,
            "monthly": monthly,
            "config": {
                "daily_limit": self.config.daily_budget_usd,
                "monthly_limit": self.config.monthly_budget_usd,
                "per_pr_limit": self.config.per_pr_budget_usd,
                "warning_threshold": self.config.warning_threshold,
            },
        }

    async def _get_daily_spend(self, repo: str | None = None) -> float:
        """Get today's spending."""
        if not self._db:
            return 0.0

        try:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today + timedelta(days=1)

            costs_ref = self._db.collection("costs")
            query = costs_ref.where("timestamp", ">=", today.isoformat()).where(
                "timestamp", "<", tomorrow.isoformat()
            )

            if repo:
                query = query.where("repo", "==", repo)

            docs = await asyncio.get_event_loop().run_in_executor(
                None, lambda: list(query.stream())
            )

            return sum(doc.to_dict().get("cost_usd", 0) for doc in docs)

        except Exception as e:
            logger.error(f"Failed to get daily spend: {e}")
            return 0.0

    async def _get_pr_spend(self, pr_number: int, repo: str) -> float:
        """Get spending for a specific PR."""
        if not self._db:
            return 0.0

        try:
            costs_ref = self._db.collection("costs")
            query = costs_ref.where("repo", "==", repo).where("pr_number", "==", pr_number)

            docs = await asyncio.get_event_loop().run_in_executor(
                None, lambda: list(query.stream())
            )

            return sum(doc.to_dict().get("cost_usd", 0) for doc in docs)

        except Exception as e:
            logger.error(f"Failed to get PR spend: {e}")
            return 0.0

    async def _get_monthly_spend(self) -> float:
        """Get this month's spending."""
        if not self._db:
            return 0.0

        try:
            now = datetime.utcnow()
            start_of_month = datetime(now.year, now.month, 1)

            costs_ref = self._db.collection("costs")
            query = costs_ref.where("timestamp", ">=", start_of_month.isoformat())

            docs = await asyncio.get_event_loop().run_in_executor(
                None, lambda: list(query.stream())
            )

            return sum(doc.to_dict().get("cost_usd", 0) for doc in docs)

        except Exception as e:
            logger.error(f"Failed to get monthly spend: {e}")
            return 0.0


# Global enforcer instance
_budget_enforcer: BudgetEnforcer | None = None


def init_budget_enforcer(
    config: BudgetConfig | None = None, firestore_db: Any | None = None
) -> BudgetEnforcer:
    """
    Initialize the global budget enforcer.

    Args:
        config: Budget configuration
        firestore_db: Optional Firestore client

    Returns:
        BudgetEnforcer instance
    """
    global _budget_enforcer
    _budget_enforcer = BudgetEnforcer(config, firestore_db)
    return _budget_enforcer


def get_budget_enforcer() -> BudgetEnforcer | None:
    """Get the global budget enforcer instance."""
    return _budget_enforcer

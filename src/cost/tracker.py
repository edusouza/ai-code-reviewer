"""Cost tracking for LLM API calls and reviews."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)


class ModelPricing(Enum):
    """Pricing for different models (per 1K tokens)."""

    GEMINI_PRO = 0.00025  # Input: $0.00025 per 1K, Output: $0.0005 per 1K
    GEMINI_PRO_OUTPUT = 0.0005
    GEMINI_FLASH = 0.0001  # Cheaper, faster model
    GEMINI_FLASH_OUTPUT = 0.0002
    GPT4 = 0.03
    GPT4_OUTPUT = 0.06
    GPT35 = 0.0015
    GPT35_OUTPUT = 0.002


@dataclass
class CostRecord:
    """A single cost record."""

    timestamp: datetime
    model: str
    operation: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    pr_number: int | None = None
    repo: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CostTracker:
    """Track costs for API calls and reviews."""

    def __init__(self, firestore_db: Any | None = None) -> None:
        """
        Initialize the cost tracker.

        Args:
            firestore_db: Optional Firestore client for persistence
        """
        self._db = firestore_db
        self._buffer: list[CostRecord] = []
        self._buffer_size = 50
        self._initialized = False

        # Pricing map
        self._pricing = {
            "gemini-pro": ModelPricing.GEMINI_PRO,
            "gemini-1.5-pro": ModelPricing.GEMINI_PRO,
            "gemini-1.5-flash": ModelPricing.GEMINI_FLASH,
            "gemini-flash": ModelPricing.GEMINI_FLASH,
            "gpt-4": ModelPricing.GPT4,
            "gpt-4-turbo": ModelPricing.GPT4,
            "gpt-3.5-turbo": ModelPricing.GPT35,
        }

    async def _initialize_db(self) -> None:
        """Lazy initialization of Firestore."""
        if self._initialized or self._db is not None:
            return

        try:
            from google.cloud.firestore import Client as FirestoreClient

            self._db = FirestoreClient(project=settings.project_id)
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {e}")

    def calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculate the cost for an API call.

        Args:
            model: Model name
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        model_lower = model.lower()

        # Get pricing
        input_pricing = self._pricing.get(model_lower, ModelPricing.GEMINI_PRO)

        # Determine output pricing
        if "flash" in model_lower:
            output_pricing = ModelPricing.GEMINI_FLASH_OUTPUT
        elif model_lower in ["gpt-4", "gpt-4-turbo"]:
            output_pricing = ModelPricing.GPT4_OUTPUT
        elif model_lower == "gpt-3.5-turbo":
            output_pricing = ModelPricing.GPT35_OUTPUT
        else:
            output_pricing = ModelPricing.GEMINI_PRO_OUTPUT

        # Calculate cost (per 1K tokens)
        input_cost = (prompt_tokens / 1000) * input_pricing.value
        output_cost = (completion_tokens / 1000) * output_pricing.value

        total_cost = input_cost + output_cost

        logger.debug(
            f"Cost for {model}: ${total_cost:.6f} "
            f"({prompt_tokens} input + {completion_tokens} output tokens)"
        )

        return float(total_cost)

    async def track_call(
        self,
        model: str,
        operation: str,
        prompt_tokens: int,
        completion_tokens: int,
        pr_number: int | None = None,
        repo: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CostRecord:
        """
        Track an API call.

        Args:
            model: Model used
            operation: Type of operation (e.g., 'analyze', 'generate')
            prompt_tokens: Input tokens
            completion_tokens: Output tokens
            pr_number: Optional PR number
            repo: Optional repository identifier
            metadata: Optional metadata

        Returns:
            CostRecord
        """
        cost = self.calculate_cost(model, prompt_tokens, completion_tokens)

        record = CostRecord(
            timestamp=datetime.utcnow(),
            model=model,
            operation=operation,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            pr_number=pr_number,
            repo=repo,
            metadata=metadata or {},
        )

        # Add to buffer
        self._buffer.append(record)

        # Flush if buffer is full
        if len(self._buffer) >= self._buffer_size:
            await self.flush()

        return record

    async def track_review(
        self,
        pr_number: int,
        repo: str,
        model: str,
        total_prompt_tokens: int,
        total_completion_tokens: int,
        num_files: int,
        num_suggestions: int,
    ) -> CostRecord:
        """
        Track the total cost for a complete review.

        Args:
            pr_number: PR number
            repo: Repository identifier
            model: Primary model used
            total_prompt_tokens: Total input tokens
            total_completion_tokens: Total output tokens
            num_files: Number of files reviewed
            num_suggestions: Number of suggestions generated

        Returns:
            CostRecord
        """
        cost = self.calculate_cost(model, total_prompt_tokens, total_completion_tokens)

        record = CostRecord(
            timestamp=datetime.utcnow(),
            model=model,
            operation="full_review",
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            cost_usd=cost,
            pr_number=pr_number,
            repo=repo,
            metadata={
                "num_files": num_files,
                "num_suggestions": num_suggestions,
                "cost_per_file": cost / num_files if num_files > 0 else 0,
                "cost_per_suggestion": cost / num_suggestions if num_suggestions > 0 else 0,
            },
        )

        self._buffer.append(record)

        if len(self._buffer) >= self._buffer_size:
            await self.flush()

        logger.info(
            f"Review cost for {repo}#{pr_number}: ${cost:.4f} "
            f"({total_prompt_tokens + total_completion_tokens} tokens, "
            f"{num_suggestions} suggestions)"
        )

        return record

    async def flush(self) -> None:
        """Flush buffered records to storage."""
        if not self._buffer:
            return

        await self._initialize_db()

        if not self._db:
            logger.warning("Firestore not available, buffering costs in memory")
            return

        try:
            batch = self._db.batch()

            for record in self._buffer:
                doc_ref = self._db.collection("costs").document()
                batch.set(
                    doc_ref,
                    {
                        "timestamp": record.timestamp.isoformat(),
                        "model": record.model,
                        "operation": record.operation,
                        "prompt_tokens": record.prompt_tokens,
                        "completion_tokens": record.completion_tokens,
                        "total_tokens": record.prompt_tokens + record.completion_tokens,
                        "cost_usd": record.cost_usd,
                        "pr_number": record.pr_number,
                        "repo": record.repo,
                        "metadata": record.metadata,
                    },
                )

            await asyncio.get_event_loop().run_in_executor(None, batch.commit)

            logger.debug(f"Flushed {len(self._buffer)} cost records")
            self._buffer.clear()

        except Exception as e:
            logger.error(f"Failed to flush cost records: {e}")

    async def get_pr_cost(self, pr_number: int, repo: str) -> CostRecord | None:
        """
        Get the total cost for a PR review.

        Args:
            pr_number: PR number
            repo: Repository identifier

        Returns:
            CostRecord if found
        """
        await self._initialize_db()

        if not self._db:
            return None

        try:
            costs_ref = self._db.collection("costs")
            query = (
                costs_ref.where("repo", "==", repo)
                .where("pr_number", "==", pr_number)
                .where("operation", "==", "full_review")
                .limit(1)
            )

            docs = await asyncio.get_event_loop().run_in_executor(
                None, lambda: list(query.stream())
            )

            if docs:
                data = docs[0].to_dict()
                return CostRecord(
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    model=data["model"],
                    operation=data["operation"],
                    prompt_tokens=data["prompt_tokens"],
                    completion_tokens=data["completion_tokens"],
                    cost_usd=data["cost_usd"],
                    pr_number=data["pr_number"],
                    repo=data["repo"],
                    metadata=data.get("metadata", {}),
                )

            return None

        except Exception as e:
            logger.error(f"Failed to get PR cost: {e}")
            return None

    async def get_daily_cost(self, date: datetime | None = None) -> float:
        """
        Get total cost for a specific date.

        Args:
            date: Date to query (defaults to today)

        Returns:
            Total cost in USD
        """
        await self._initialize_db()

        if not self._db:
            return 0.0

        if date is None:
            date = datetime.utcnow()

        try:
            start_of_day = datetime(date.year, date.month, date.day)
            end_of_day = start_of_day.replace(hour=23, minute=59, second=59)

            costs_ref = self._db.collection("costs")
            query = costs_ref.where("timestamp", ">=", start_of_day.isoformat()).where(
                "timestamp", "<=", end_of_day.isoformat()
            )

            docs = await asyncio.get_event_loop().run_in_executor(
                None, lambda: list(query.stream())
            )

            total_cost = sum(doc.to_dict().get("cost_usd", 0) for doc in docs)

            return float(total_cost)

        except Exception as e:
            logger.error(f"Failed to get daily cost: {e}")
            return 0.0

    async def get_repo_cost_summary(self, repo: str, days: int = 30) -> dict[str, Any]:
        """
        Get cost summary for a repository.

        Args:
            repo: Repository identifier
            days: Number of days to look back

        Returns:
            Cost summary dictionary
        """
        await self._initialize_db()

        if not self._db:
            return {"error": "Database not available"}

        try:
            from datetime import timedelta

            start_date = datetime.utcnow() - timedelta(days=days)

            costs_ref = self._db.collection("costs")
            query = costs_ref.where("repo", "==", repo).where(
                "timestamp", ">=", start_date.isoformat()
            )

            docs = await asyncio.get_event_loop().run_in_executor(
                None, lambda: list(query.stream())
            )

            records = [doc.to_dict() for doc in docs]

            if not records:
                return {
                    "repo": repo,
                    "period_days": days,
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "total_reviews": 0,
                }

            total_cost = sum(r.get("cost_usd", 0) for r in records)
            total_tokens = sum(
                r.get("prompt_tokens", 0) + r.get("completion_tokens", 0) for r in records
            )

            full_reviews = [r for r in records if r.get("operation") == "full_review"]

            # Breakdown by model
            by_model = {}
            for r in records:
                model = r.get("model", "unknown")
                if model not in by_model:
                    by_model[model] = {"cost": 0, "tokens": 0}
                by_model[model]["cost"] += r.get("cost_usd", 0)
                by_model[model]["tokens"] += r.get("prompt_tokens", 0) + r.get(
                    "completion_tokens", 0
                )

            return {
                "repo": repo,
                "period_days": days,
                "total_cost": round(total_cost, 4),
                "total_tokens": total_tokens,
                "total_reviews": len(full_reviews),
                "total_calls": len(records),
                "average_cost_per_review": round(total_cost / len(full_reviews), 4)
                if full_reviews
                else 0,
                "by_model": by_model,
            }

        except Exception as e:
            logger.error(f"Failed to get repo cost summary: {e}")
            return {"error": str(e)}


# Global tracker instance
_cost_tracker: CostTracker | None = None


def init_cost_tracker(firestore_db: Any | None = None) -> CostTracker:
    """
    Initialize the global cost tracker.

    Args:
        firestore_db: Optional Firestore client

    Returns:
        CostTracker instance
    """
    global _cost_tracker
    _cost_tracker = CostTracker(firestore_db)
    return _cost_tracker


def get_cost_tracker() -> CostTracker | None:
    """Get the global cost tracker instance."""
    return _cost_tracker

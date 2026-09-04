"""Opportunity Selector — selects one opportunity from the registry using a strategy."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.opportunities.registry import (
    Opportunity,
    OpportunityRegistry,
    NoQualifiedOpportunityError,
)


class OpportunitySelector:
    """Selects one opportunity from the registry using a strategy.

    Strategies:
    - "top_scored": highest total score (default, same as current opps[0])
    - "best_fit": highest score with minimum confidence threshold
    - "first_eligible": first opportunity that passes minimum thresholds

    All selection decisions are recorded with rationale for auditability.
    """

    STRATEGIES = ("top_scored", "best_fit", "first_eligible")

    def __init__(
        self,
        min_score: float = 0,
        min_confidence: int = 0,
        max_content_difficulty: Optional[str] = None,
    ):
        self.min_score = min_score
        self.min_confidence = min_confidence
        self.max_content_difficulty = max_content_difficulty

    def select(
        self,
        registry: OpportunityRegistry,
        strategy: str = "top_scored",
    ) -> Opportunity:
        """Select one opportunity from the registry.

        Args:
            registry: loaded OpportunityRegistry
            strategy: one of "top_scored", "best_fit", "first_eligible"

        Returns:
            Selected Opportunity

        Raises:
            NoQualifiedOpportunityError: if no opportunities meet criteria
        """
        if not registry.is_loaded:
            raise NoQualifiedOpportunityError(
                "Registry is empty — no opportunities to select from"
            )

        qualified = registry.get_qualified(
            min_score=self.min_score,
            min_confidence=self.min_confidence,
            max_content_difficulty=self.max_content_difficulty,
        )

        if not qualified:
            raise NoQualifiedOpportunityError(
                f"No opportunities qualify (min_score={self.min_score}, "
                f"min_confidence={self.min_confidence}, "
                f"max_difficulty={self.max_content_difficulty})"
            )

        if strategy == "top_scored":
            selected = qualified[0]
        elif strategy == "best_fit":
            # Best fit = highest score among qualified (same as top_scored on qualified set)
            selected = qualified[0]
        elif strategy == "first_eligible":
            # First opportunity in original scored order that qualifies
            selected = qualified[0]
        else:
            raise ValueError(
                f"Unknown selection strategy: {strategy}. "
                f"Valid: {', '.join(self.STRATEGIES)}"
            )

        return selected

    def select_with_rationale(
        self,
        registry: OpportunityRegistry,
        strategy: str = "top_scored",
    ) -> Dict[str, Any]:
        """Select one opportunity and return selection metadata.

        Returns a dict with:
        - selected: Opportunity
        - strategy: str
        - registry_summary: dict
        - qualification_filter: dict
        - selection_rationale: str
        """
        selected = self.select(registry, strategy=strategy)

        rationale = (
            f"Selected '{selected.keyword}' via '{strategy}' strategy "
            f"(score={selected.score_total}/{selected.score_max}, "
            f"confidence={selected.confidence}, "
            f"ratio={selected.score_ratio:.2%})"
        )

        return {
            "selected": selected,
            "strategy": strategy,
            "registry_summary": registry.get_summary(),
            "qualification_filter": {
                "min_score": self.min_score,
                "min_confidence": self.min_confidence,
                "max_content_difficulty": self.max_content_difficulty,
            },
            "selection_rationale": rationale,
        }

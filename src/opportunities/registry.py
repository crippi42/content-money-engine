"""Opportunity Registry — loads and queries scored opportunities."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class NoQualifiedOpportunityError(Exception):
    """Raised when no opportunities meet the selection criteria."""


@dataclass
class Opportunity:
    """Single scored opportunity."""
    keyword: str
    score_total: float
    score_max: int
    score_dimensions: Dict[str, float]
    confidence: int
    score_note: str
    rationale: str
    content_type: str = ""
    monetization_concept: str = ""
    target_audience: str = ""
    evidence_references: List[str] = field(default_factory=list)

    @property
    def score_ratio(self) -> float:
        if self.score_max <= 0:
            return 0.0
        return round(self.score_total / self.score_max, 4)


class OpportunityRegistry:
    """Registry for scored opportunities produced by ScorerAgent.

    Loads from experiments/<id>/evidence/opportunities.json and provides
    indexed access by score, confidence, keyword, or qualification status.
    """

    def __init__(self, experiment_dir: Path):
        self.experiment_dir = Path(experiment_dir)
        self.evidence_path = self.experiment_dir / "evidence" / "opportunities.json"
        self._opportunities: List[Opportunity] = []
        self._loaded_at: Optional[str] = None
        self._source_type: str = "unknown"
        self._scoring_timestamp: Optional[str] = None

    def load(self) -> bool:
        """Load opportunities from evidence/opportunities.json.

        Returns True if loaded successfully, False if file missing or malformed.
        """
        if not self.evidence_path.exists():
            return False

        try:
            data = json.loads(self.evidence_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False

        raw_opportunities = data.get("opportunities", [])
        self._source_type = data.get("evidence_source_type", "unknown")
        self._scoring_timestamp = data.get("scoring_timestamp")

        self._opportunities = []
        for raw in raw_opportunities:
            opp = Opportunity(
                keyword=raw.get("keyword", "unknown"),
                score_total=float(raw.get("score", {}).get("total", 0)),
                score_max=int(raw.get("score", {}).get("max_possible", 100)),
                score_dimensions=raw.get("score", {}).get("dimensions", {}),
                confidence=int(raw.get("confidence", 0)),
                score_note=raw.get("score_note", ""),
                rationale=raw.get("rationale", ""),
                content_type=raw.get("content_type", ""),
                monetization_concept=raw.get("monetization_concept", ""),
                target_audience=raw.get("target_audience", ""),
                evidence_references=raw.get("evidence_references", []),
            )
            self._opportunities.append(opp)

        self._loaded_at = datetime.now(timezone.utc).isoformat()
        return True

    @property
    def is_loaded(self) -> bool:
        return len(self._opportunities) > 0

    @property
    def count(self) -> int:
        return len(self._opportunities)

    @property
    def source_type(self) -> str:
        return self._source_type

    def get_all(self) -> List[Opportunity]:
        """Return all opportunities in scored order (highest first)."""
        return list(self._opportunities)

    def get_top(self, n: int = 1) -> List[Opportunity]:
        """Return top N opportunities by score."""
        return self._opportunities[:n]

    def get_by_keyword(self, keyword: str) -> Optional[Opportunity]:
        """Return opportunity by exact keyword match, or None."""
        for opp in self._opportunities:
            if opp.keyword == keyword:
                return opp
        return None

    def get_qualified(
        self,
        min_score: float = 0,
        min_confidence: int = 0,
        max_content_difficulty: Optional[str] = None,
    ) -> List[Opportunity]:
        """Return opportunities meeting minimum thresholds.

        Args:
            min_score: minimum total score (0-100)
            min_confidence: minimum confidence (0-100)
            max_content_difficulty: if set, exclude opportunities with higher difficulty
                (e.g., "high" excludes "medium" and "high"; "medium" excludes "high" only)
        """
        difficulty_order = {"low": 0, "medium": 1, "high": 2, "unknown": 1}
        max_difficulty_level = difficulty_order.get(max_content_difficulty, 2)

        qualified = []
        for opp in self._opportunities:
            if opp.score_total < min_score:
                continue
            if opp.confidence < min_confidence:
                continue

            if max_content_difficulty is not None:
                opp_difficulty = getattr(opp, "content_difficulty", "unknown")
                if difficulty_order.get(opp_difficulty, 1) > max_difficulty_level:
                    continue

            qualified.append(opp)

        return qualified

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the registry state."""
        return {
            "count": self.count,
            "source_type": self._source_type,
            "scoring_timestamp": self._scoring_timestamp,
            "loaded_at": self._loaded_at,
            "top_keyword": self._opportunities[0].keyword if self._opportunities else None,
            "top_score": self._opportunities[0].score_total if self._opportunities else None,
            "score_range": {
                "min": min(o.score_total for o in self._opportunities) if self._opportunities else 0,
                "max": max(o.score_total for o in self._opportunities) if self._opportunities else 0,
            },
        }

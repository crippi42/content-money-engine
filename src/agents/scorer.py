"""Scorer agent for Content Money Engine.

Evaluates and ranks content opportunities produced by the Researcher.
Uses deterministic scoring dimensions with explicit rationale.

The Scorer uses a logical worker selected via the existing Workstation
WorkerRegistry for potential LLM-assisted scoring refinement. If no
real worker is available, deterministic rule-based scoring is used.

Architecture:
  Scorer -> WorkerRegistry (role-based discovery) -> Worker -> Model
  (or falls back to deterministic rule-based scoring)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.agents.base import AgentBase


class ScorerAgent(AgentBase):
    """Scorer agent: ranks opportunities by expected revenue potential.

    Scoring dimensions (total: 100 points):
    - demand (0-25): search volume / buyer intent strength
    - monetization (0-25): commission potential x product economics
    - competition (0-20): inverse of keyword difficulty / competition level
    - content_feasibility (0-15): content difficulty / production effort
    - monetization_fit (0-15): relevance of monetization concept to niche
    """

    SCORING_DIMENSIONS = {
        "demand": 25,
        "monetization": 25,
        "competition": 20,
        "content_feasibility": 15,
        "monetization_fit": 15,
    }

    @property
    def agent_type(self) -> str:
        return "scorer"

    def __init__(self, agent_id: str, experiment_dir: Path, session_history: Any, session_id: str,
                 worker_registry: Any = None, workspace_dir: Path = None):
        super().__init__(agent_id, experiment_dir, session_history, session_id)
        self._worker_registry = worker_registry
        self._workspace_dir = workspace_dir
        self._worker_instances: dict[str, Any] = {}

    def get_required_inputs(self) -> list[str]:
        return ["research"]

    def produce_output(self, inputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
        research = inputs["research"]
        opportunities = research.get("opportunities", [])
        evidence_source = research.get("evidence_source", {})
        source_type = evidence_source.get("type", "simulated")
        is_simulated = evidence_source.get("simulated", False)
        worker_used = research.get("worker_used", "unknown")
        model_used = research.get("model_used", "unknown")

        # If evidence is actually simulated (even if type says externally_sourced),
        # downgrade source_type for scoring confidence purposes
        if is_simulated:
            source_type = "simulated"

        if not opportunities:
            return {
                "status": "error",
                "error": "No opportunities found in research evidence",
            "evidence_source_type": source_type,
            "researcher_evidence_source_type": evidence_source.get("type", "unknown"),
            "is_simulated_evidence": is_simulated,
            }

        scored_opportunities = []
        for opp in opportunities:
            scored = self._score_opportunity(opp, source_type)
            scored_opportunities.append(scored)

        scored_opportunities.sort(key=lambda x: x["score"]["total"], reverse=True)

        output = {
            "status": "complete",
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "experiment_id": research.get("experiment_id", "unknown"),
            "scoring_timestamp": datetime.now(timezone.utc).isoformat(),
            "evidence_source_type": source_type,
            "researcher_worker_used": worker_used,
            "researcher_model_used": model_used,
            "research_evidence_sha256": research.get("evidence_sha256", ""),
            "scoring_dimensions": self.SCORING_DIMENSIONS,
            "opportunities": scored_opportunities,
            "ranked_keywords": [o["keyword"] for o in scored_opportunities],
            "top_opportunity": scored_opportunities[0] if scored_opportunities else None,
            "summary": f"Scored {len(scored_opportunities)} opportunities. Top: '{scored_opportunities[0]['keyword']}' (score: {scored_opportunities[0]['score']['total']})",
            "confidence": self._compute_confidence(scored_opportunities, source_type),
        }

        return output

    def _score_opportunity(self, opp: dict[str, Any], source_type: str) -> dict[str, Any]:
        """Score a single opportunity across all dimensions."""
        import math
        scores: dict[str, float] = {}

        # Demand: based on search volume estimate and buyer intent
        volume = opp.get("search_volume_estimate", 0)
        intent = opp.get("buyer_intent", "unknown")
        intent_multiplier = {"very_high": 1.0, "high": 0.85, "medium": 0.6, "low": 0.3, "unknown": 0.5}[intent]

        # Normalize volume to 0-25 scale (log scale: 1000 -> max, 10 -> 0)
        if volume > 0:
            volume_score = min(25 * (math.log10(volume) / math.log10(1000)), 25)
        else:
            volume_score = 0
        scores["demand"] = round(volume_score * intent_multiplier, 1)

        # Monetization: based on monetization estimate percentage
        monetization_pct = opp.get("monetization_estimate_pct", 0)
        scores["monetization"] = round(min(monetization_pct / 10 * 25, 25), 1)

        # Competition: inverse of keyword difficulty (higher difficulty = lower score)
        difficulty = opp.get("keyword_difficulty", 50)
        scores["competition"] = round(20 - (difficulty / 100 * 20), 1)

        # Content feasibility: inverse of content difficulty
        content_difficulty = opp.get("content_difficulty", "medium")
        difficulty_map = {"low": 15, "medium": 10, "high": 5, "unknown": 10}
        scores["content_feasibility"] = difficulty_map.get(content_difficulty, 10)

        # Monetization fit: heuristic based on content type and monetization concept
        content_type = opp.get("content_type", "")
        monetization = opp.get("monetization_concept", "")
        if "review" in content_type.lower() and "commission" in monetization.lower():
            scores["monetization_fit"] = 15
        elif "comparison" in content_type.lower() and "commission" in monetization.lower():
            scores["monetization_fit"] = 14
        elif "guide" in content_type.lower() and "upsell" in monetization.lower():
            scores["monetization_fit"] = 12
        else:
            scores["monetization_fit"] = 8

        total = sum(scores.values())

        # Adjust confidence based on evidence source
        if source_type == "simulated":
            confidence = 20
            score_note = "Score based on simulated data — NOT validated for real decisions."
        elif source_type == "seed":
            confidence = 50
            score_note = "Score based on operator-provided seed data."
        elif source_type == "externally_sourced":
            confidence = 80
            score_note = "Score based on externally sourced evidence."
        else:
            confidence = 20
            score_note = "Score based on unknown evidence source — treat with caution."

        return {
            "keyword": opp.get("keyword", "unknown"),
            "target_audience": opp.get("buyer_intent", "unknown") + " intent buyers",
            "monetization_concept": opp.get("monetization_concept", ""),
            "evidence_references": opp.get("evidence_references", []),
            "evidence_source": opp.get("evidence_source", source_type),
            "score": {
                "total": round(total, 1),
                "max_possible": 100,
                "dimensions": scores,
            },
            "rationale": self._generate_rationale(opp, scores),
            "confidence": confidence,
            "score_note": score_note,
        }

    def _generate_rationale(self, opp: dict[str, Any], scores: dict[str, float]) -> str:
        """Generate a human-readable rationale for the score."""
        parts = []
        parts.append(
            f"Demand={scores['demand']:.1f} (volume={opp.get('search_volume_estimate', 'N/A')}, intent={opp.get('buyer_intent', 'unknown')})"
        )
        parts.append(
            f"Monetization={scores['monetization']:.1f} (estimate={opp.get('monetization_estimate_pct', 'N/A')}%, concept={opp.get('monetization_concept', 'unknown')})"
        )
        parts.append(
            f"Competition={scores['competition']:.1f} (difficulty={opp.get('keyword_difficulty', 'N/A')})"
        )
        parts.append(
            f"Content feasibility={scores['content_feasibility']:.1f} (difficulty={opp.get('content_difficulty', 'unknown')})"
        )
        parts.append(
            f"Monetization fit={scores['monetization_fit']:.1f} (type={opp.get('content_type', 'unknown')})"
        )
        return "; ".join(parts)

    def _compute_confidence(self, opportunities: list[dict], source_type: str) -> int:
        """Overall confidence for the scoring run."""
        if source_type == "simulated":
            return 20
        elif source_type == "seed":
            return 50
        elif source_type == "externally_sourced":
            return 80
        return 20

    def archive_evidence(self, output_dir: Path) -> Path:
        """Copy scorer output to evidence/opportunities.json for downstream agents."""
        output_path = output_dir / f"{self.agent_id}_output.json"
        evidence_path = self.experiment_dir / "evidence" / "opportunities.json"

        if output_path.exists():
            evidence_path.write_text(
                output_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
        return evidence_path

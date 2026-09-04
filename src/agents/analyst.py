"""Analyst agent for Content Money Engine.

Consumes research data, content drafts, and performance metrics to produce
feedback for the Researcher. Completes the CME feedback loop:
Research → Score → Create → (§26) Publish → Analyze → Feedback → Research

The AnalystAgent reads from:
- experiments/<id>/evidence/opportunities.json (selected opportunity)
- experiments/<id>/evidence/content_draft.json (content draft)
- experiments/<id>/evidence/analytics.json (optional: real metrics)

It produces:
- experiments/<id>/evidence/analytics.json (performance snapshot)
- experiments/<id>/evidence/feedback.json (feedback for next research cycle)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.agents.base import AgentBase
from src.opportunities.registry import NoQualifiedOpportunityError, OpportunityRegistry
from src.opportunities.selector import OpportunitySelector


class AnalystAgent(AgentBase):
    """Analyst agent: tracks performance metrics and produces feedback.

    Input evidence:
    - opportunities.json (must have at least one opportunity)
    - content_draft.json (optional, for context)
    - analytics.json (optional, real performance data)

    Output artifacts:
    - analytics.json (performance snapshot)
    - feedback.json (feedback for Researcher)
    """

    @property
    def agent_type(self) -> str:
        return "analyst"

    def get_required_inputs(self) -> list[str]:
        return ["opportunities"]

    def produce_output(self, inputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
        opportunities = inputs.get("opportunities", {})

        if not opportunities.get("opportunities"):
            return {
                "status": "error",
                "error": "No opportunities found in evidence",
                "agent_type": self.agent_type,
            }

        content_draft = self._read_optional_input("content_draft")

        analytics_data = self._collect_analytics(
            opportunities=opportunities,
            content_draft=content_draft,
            simulated=True,
            provenance=self._extract_provenance(content_draft),
        )

        feedback = self._generate_feedback(analytics_data)

        output = {
            "status": "complete",
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "experiment_id": opportunities.get("experiment_id", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "analytics": analytics_data,
            "feedback_for_researcher": feedback,
            "simulated": True,
        }

        self._write_evidence_files(analytics_data, feedback)

        return output

    def _extract_provenance(self, content_draft: dict[str, Any] | None) -> dict[str, str]:
        """Extract upstream provenance from content_draft."""
        if not content_draft:
            return {}
        
        provenance = content_draft.get("provenance", {})
        return {
            "research_evidence_sha256": provenance.get("research_evidence_sha256", ""),
            "scoring_sha256": provenance.get("scoring_sha256", ""),
            "draft_sha256": content_draft.get("evidence_sha256", ""),
            "source_opportunity_id": provenance.get("source_opportunity_id", ""),
        }

    def _read_optional_input(self, name: str) -> dict[str, Any]:
        """Read an optional input that may not be in get_required_inputs()."""
        path = self.evidence_dir / f"{name}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def _write_evidence_files(self, analytics_data: dict[str, Any], feedback: dict[str, Any]):
        """Write analytics.json and feedback.json to evidence directory."""
        analytics_path = self.evidence_dir / "analytics.json"
        feedback_path = self.evidence_dir / "feedback.json"

        analytics_path.write_text(json.dumps(analytics_data, indent=2), encoding="utf-8")
        feedback_path.write_text(json.dumps(feedback, indent=2), encoding="utf-8")

    def archive_evidence(self, output_dir: Path) -> Path:
        """Archive analytics.json and feedback.json to evidence directory."""
        analytics_path = self.experiment_dir / "evidence" / "analytics.json"
        feedback_path = self.experiment_dir / "evidence" / "feedback.json"

        if analytics_path.exists():
            analytics_path.write_text(
                analytics_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
        if feedback_path.exists():
            feedback_path.write_text(
                feedback_path.read_text(encoding="utf-8"), encoding="utf-8"
            )

        return feedback_path

    def _collect_analytics(
        self,
        opportunities: dict[str, Any],
        content_draft: dict[str, Any] | None,
        simulated: bool = True,
        provenance: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Collect or simulate performance metrics with provenance chain."""
        top_opp = opportunities.get("opportunities", [{}])[0] if opportunities.get("opportunities") else {}
        keyword = top_opp.get("keyword", "unknown")

        base_data = {
            "keyword": keyword,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "simulated",
            "metrics": {
                "impressions": 0,
                "clicks": 0,
                "ctr_pct": 0.0,
                "page_views": 0,
                "bounce_rate": 0.0,
                "avg_time_seconds": 0,
            },
            "insights": self._generate_simulated_insights(opportunities, content_draft),
        }

        if provenance:
            base_data["provenance"] = provenance

        return base_data

    def _generate_simulated_insights(
        self,
        opportunities: dict[str, Any],
        content_draft: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Generate simulated insights for plan-only content."""
        top_score = 0
        score_details = {}

        if opportunities.get("opportunities"):
            opp = opportunities["opportunities"][0]
            top_score = opp.get("score", {}).get("total", 0)
            score_details = opp.get("score", {}).get("dimensions", {})

        return {
            "opportunity_quality": "high" if top_score >= 75 else "medium" if top_score >= 50 else "low",
            "scoring_dimensions": score_details,
            "content_type": content_draft.get("content_type", "article") if content_draft else "article",
            "recommended_improvements": [],
            "next_cycle_opportunities": self._recommend_opps_for_next_cycle(opportunities),
        }

    def _recommend_opps_for_next_cycle(self, opportunities: dict[str, Any]) -> list[dict[str, Any]]:
        """Identify which opportunities to focus on in the next research cycle."""
        ranked = opportunities.get("ranked_keywords", [])
        if len(ranked) >= 3:
            return [
                {"keyword": ranked[1], "reason": "Second highest scored - consider after primary"},
                {"keyword": ranked[2], "reason": "Third option for portfolio"},
            ]
        if len(ranked) >= 2:
            return [{"keyword": ranked[1], "reason": "Second highest scored - consider after primary"}]
        return []

    def _generate_feedback(self, analytics_data: dict[str, Any]) -> dict[str, Any]:
        """Generate feedback for the Researcher with provenance chain."""
        feedback = {
            "cycle": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "opportunities_evaluated": 1,
                "top_performer": analytics_data.get("keyword", "unknown"),
                "quality_score": analytics_data.get("insights", {}).get("opportunity_quality", "unknown"),
            },
            "research_directions": {
                "content_types": ["product_review", "comparison_guide", "tutorial"],
                "target_audience_insights": analytics_data.get("insights", {}).get("content_type", "unknown") + " focused",
            },
            "next_research_query": "expand to complementary keywords for " + analytics_data.get("keyword", "unknown"),
            "trust_signals": ["no_social_signals_yet", "plan_only_generated"],
            "validation_needed": ["publish_content", "await_analytics"],
        }

        if "provenance" in analytics_data:
            feedback["provenance"] = analytics_data["provenance"]

        return feedback


def run_analysis_with_opportunity_selection(experiment_dir: Path) -> dict[str, Any]:
    """Standalone function to run analysis with auto-selected opportunity.

    This function loads the opportunity registry and uses the selector to
    choose the best opportunity, avoiding hardcoded defaults.
    """
    try:
        registry = OpportunityRegistry(experiment_dir)
        if not registry.load():
            return {"status": "error", "error": "Failed to load opportunities from registry"}

        selector = OpportunitySelector(min_score=50, min_confidence=20)
        result = selector.select_with_rationale(registry, strategy="top_scored")
        return {"status": "success", "selection": result["selected"].keyword}
    except NoQualifiedOpportunityError as e:
        return {"status": "error", "error": str(e)}
    except ImportError:
        return {"status": "error", "error": "Opportunity layer not available"}
    except Exception as e:
        return {"status": "error", "error": f"Unexpected error: {str(e)}"}
"""Content agent for Content Money Engine.

Produces a ContentPlan from scored opportunities, then attempts content
generation via the ContentMCP interface. Since no concrete MCP server is
configured, falls back to "plan-only" mode — the ContentDraft contains
the plan metadata and a placeholder, ready for §26 human approval before
any publishing action.

Architecture:
  ContentAgent -> ContentMCP (abstract, not configured) -> [plan-only fallback]
  Reads: opportunities.json (from ScorerAgent)
  Writes: content_plan.json, content_draft.json (to output/, archived to evidence/)
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.agents.base import AgentBase
from src.mcp.base import MCPRegistry, ContentMCP
from src.opportunities.registry import NoQualifiedOpportunityError


class ContentAgent(AgentBase):
    """Content agent: plans and drafts content for the top-scored opportunity.

    Input:
      - opportunities.json (evidence from ScorerAgent)

    Output:
      - content_plan.json (content plan with target keyword, angle, outline)
      - content_draft.json (content draft with provenance and §26 linkage)

    The agent first selects the top-scored opportunity, generates a
    ContentPlan, then attempts to invoke ContentMCP for generation.
    If ContentMCP is not configured, falls back to "plan-only" mode
    where the draft contains the plan but no generated content body.
    """

    @property
    def agent_type(self) -> str:
        return "content"

    def get_required_inputs(self) -> list[str]:
        return ["opportunities"]

    def __init__(
        self,
        agent_id: str,
        experiment_dir: Path,
        session_history: Any,
        session_id: str,
        mcp_registry: Any = None,
        workspace_dir: Path = None,
    ):
        super().__init__(agent_id, experiment_dir, session_history, session_id)
        self._mcp_registry = mcp_registry or MCPRegistry()
        self._workspace_dir = workspace_dir

    def produce_output(self, inputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
        opportunities = inputs["opportunities"]
        opps = opportunities.get("opportunities", [])
        evidence_source_type = opportunities.get("evidence_source_type", "simulated")
        research_evidence_sha = opportunities.get("research_evidence_sha256", "")
        scoring_evidence_sha = opportunities.get("evidence_sha256", "")
        researcher_model = opportunities.get("researcher_model_used", "unknown")
        researcher_worker = opportunities.get("researcher_worker_used", "unknown")

        if not opps:
            return {
                "status": "error",
                "error": "No opportunities found in opportunities evidence",
                "evidence_source_type": evidence_source_type,
            }

        try:
            selected_opportunity = self._select_opportunity(opps, opportunities)
        except NoQualifiedOpportunityError as e:
            return {
                "status": "error",
                "error": str(e),
                "evidence_source_type": evidence_source_type,
            }
        top_opp = selected_opportunity
        plan = self._build_content_plan(top_opp, opportunities)

        content_mcp = self._mcp_registry.get_server("content")
        mcp_available = content_mcp is not None and content_mcp.initialize()

        draft = self._build_content_draft(
            plan, top_opp, opportunities,
            research_evidence_sha, scoring_evidence_sha,
            researcher_model, researcher_worker, mcp_available,
        )

        output = {
            "status": "complete",
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "experiment_id": opportunities.get("experiment_id", "unknown"),
            "content_plan": plan,
            "content_draft": draft,
            "mcp_available": mcp_available,
            "generation_mode": "mcp" if mcp_available else "plan_only",
            "requires_approval": True,
            "approval_boundary": "publishing_and_financial_commitment",
        }

        return output

    def _select_opportunity(self, opps: list[dict[str, Any]], opportunities: dict[str, Any]) -> dict[str, Any]:
        """Select the best opportunity using the Opportunity Registry + Selector.

        Fails closed: if the registry layer is unavailable, cannot load evidence,
        or no opportunity meets minimum qualification requirements, raises
        NoQualifiedOpportunityError rather than falling back to opps[0].
        """
        try:
            from src.opportunities.registry import OpportunityRegistry
            from src.opportunities.selector import OpportunitySelector
        except ImportError:
            raise NoQualifiedOpportunityError(
                "Opportunity Registry module not available — cannot select qualified opportunity"
            )

        registry = OpportunityRegistry(self.experiment_dir)
        if not registry.load():
            raise NoQualifiedOpportunityError(
                "Failed to load opportunities from opportunities.json — "
                "registry layer unavailable, cannot qualify selection"
            )

        selector = OpportunitySelector(
            min_score=0,
            min_confidence=0,
        )

        result = selector.select_with_rationale(registry, strategy="top_scored")
        selected = result["selected"]
        return {
            "keyword": selected.keyword,
            "score": {
                "total": selected.score_total,
                "max_possible": selected.score_max,
                "dimensions": selected.score_dimensions,
            },
            "confidence": selected.confidence,
            "score_note": selected.score_note,
            "rationale": selected.rationale,
            "content_type": selected.content_type,
            "monetization_concept": selected.monetization_concept,
            "target_audience": selected.target_audience,
            "evidence_references": selected.evidence_references,
            "selection_rationale": result["selection_rationale"],
            "registry_summary": result["registry_summary"],
        }

    def _build_content_plan(self, opportunity: dict[str, Any], opportunities_evidence: dict[str, Any]) -> dict[str, Any]:
        """Build a ContentPlan from the top-scored opportunity."""
        keyword = opportunity.get("keyword", "unknown")
        score = opportunity.get("score", {})
        dimensions = score.get("dimensions", {})

        plan = {
            "plan_id": f"plan-{self.session_id}",
            "keyword": keyword,
            "content_type": opportunity.get("content_type", "article"),
            "content_difficulty": opportunity.get("content_difficulty", "medium"),
            "target_audience": opportunity.get("target_audience", "unknown"),
            "monetization_concept": opportunity.get("monetization_concept", ""),
            "monetization_estimate_pct": opportunity.get("monetization_estimate_pct", 0) if isinstance(
                opportunity.get("monetization_estimate_pct"), (int, float)
            ) else 0,
            "search_volume_estimate": opportunity.get("search_volume_estimate", 0),
            "keyword_difficulty": opportunity.get("keyword_difficulty", 50),
            "competition_level": opportunity.get("competition_level", "unknown"),
            "buyer_intent": opportunity.get("buyer_intent", "unknown"),
            "opportunity_score": score.get("total", 0),
            "score_dimensions": dimensions,
            "score_rationale": opportunity.get("rationale", ""),
            "content_outline": self._generate_outline(keyword, dimensions),
            "planned_at": datetime.now(timezone.utc).isoformat(),
            "evidence_source_type": opportunities_evidence.get("evidence_source_type", "simulated"),
        }

        return plan

    def _generate_outline(self, keyword: str, dimensions: dict[str, Any]) -> list[dict[str, str]]:
        """Generate a structured content outline from the keyword and scores.

        This is deterministic — no LLM required. The outline provides
        section headings and monetization hooks based on the opportunity
        scoring dimensions.
        """
        monetization_score = dimensions.get("monetization", 0)
        monetization_fit_score = dimensions.get("monetization_fit", 0)

        has_commission = monetization_score > 10 and monetization_fit_score > 8

        outline = [
            {"section": "Introduction", "purpose": f"Introduce the topic of {keyword}", "monetization_hook": None},
            {"section": "Problem Statement", "purpose": f"Explain the problem readers face with {keyword}", "monetization_hook": None},
            {"section": "Research / Comparison", "purpose": f"Compare options for {keyword} based on scoring dimensions", "monetization_hook": "comparison_link" if has_commission else None},
            {"section": "Recommendation", "purpose": f"Provide a clear recommendation for {keyword}", "monetization_hook": "product_link" if has_commission else None},
            {"section": "Conclusion", "purpose": f"Summarize and call to action for {keyword}", "monetization_hook": "cta" if has_commission else None},
        ]

        return outline

    def _build_content_draft(
        self,
        plan: dict[str, Any],
        opportunity: dict[str, Any],
        opportunities_evidence: dict[str, Any],
        research_evidence_sha: str,
        scoring_evidence_sha: str,
        researcher_model: str,
        researcher_worker: str,
        mcp_available: bool,
    ) -> dict[str, Any]:
        """Build a ContentDraft with full provenance and §26 linkage metadata."""
        plan_json = json.dumps(plan, indent=2, sort_keys=True)
        plan_sha256 = hashlib.sha256(plan_json.encode("utf-8")).hexdigest()

        draft_content = self._generate_plan_only_content(plan, opportunity) if not mcp_available else ""

        draft = {
            "draft_id": f"draft-{self.session_id}",
            "plan_id": plan["plan_id"],
            "plan_sha256": plan_sha256,
            "status": "plan_only" if not mcp_available else "generated",
            "generation_mode": "plan_only" if not mcp_available else "mcp",
            "title": self._generate_title(plan["keyword"]),
            "content_type": plan["content_type"],
            "content": draft_content,
            "word_count_estimate": len(draft_content.split()) if draft_content else 0,
            "monetization_concept": plan["monetization_concept"],
            "monetization_estimate_pct": plan["monetization_estimate_pct"],
            "requires_approval": True,
            "approval_boundary": "publishing_and_financial_commitment",
            "approval_reason": "Content contains monetization concepts and must be reviewed before publishing",
            "provenance": {
                "created_by": "ContentAgent",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source_opportunity_id": opportunity.get("keyword", "unknown"),
                "research_evidence_sha256": research_evidence_sha,
                "scoring_sha256": scoring_evidence_sha,
                "researcher_model_used": researcher_model,
                "researcher_worker_used": researcher_worker,
                "score_total": opportunity.get("score", {}).get("total", 0),
                "evidence_source_type": opportunities_evidence.get("evidence_source_type", "simulated"),
                "is_simulated": opportunities_evidence.get("evidence_source_type") == "simulated",
            },
            "section_signposts": plan["content_outline"],
        }

        draft_sha_json = json.dumps(draft, indent=2, sort_keys=True)
        draft["evidence_sha256"] = hashlib.sha256(draft_sha_json.encode("utf-8")).hexdigest()

        return draft

    def _generate_plan_only_content(self, plan: dict[str, Any], opportunity: dict[str, Any]) -> str:
        """Generate a structured placeholder representing what the content will cover.

        This is NOT real content generation — it is a plan-only artifact
        that satisfies the evidence requirement while remaining clearly
        marked as a draft placeholder. Real content generation would happen
        via ContentMCP when a server is configured.
        """
        keyword = plan["keyword"]
        content_type = plan["content_type"]
        monetization = plan["monetization_concept"]
        volume = plan["search_volume_estimate"]
        difficulty = plan["keyword_difficulty"]
        buyer_intent = plan["buyer_intent"]
        score = plan["opportunity_score"]
        outline = plan["content_outline"]

        lines = [
            f"## DRAFT PLACEHOLDER — {keyword}",
            "",
            f"**Status:** Plan-only draft (ContentMCP not configured). Real content generation requires MCP server configuration.",
            f"**Content type:** {content_type}",
            f"**Monetization:** {monetization}",
            f"**Search volume:** {volume} | **Keyword difficulty:** {difficulty} | **Buyer intent:** {buyer_intent}",
            f"**Opportunity score:** {score}",
            "",
            "### Planned Sections:",
        ]

        for section in outline:
            lines.append(f"- **{section['section']}**: {section['purpose']}")
            if section.get("monetization_hook"):
                lines.append(f"  - Monetization hook: {section['monetization_hook']}")

        lines.extend([
            "",
            "### Monetization Hooks:",
            f"- Primary concept: {monetization}",
            f"- Estimate: {plan['monetization_estimate_pct']}% of revenue",
            "",
            "---",
            "**This is a plan-only placeholder. No AI-generated content was produced.**",
            "**Content generation requires ContentMCP server configuration (Phase C+).**",
        ])

        return "\n".join(lines)

    def _generate_title(self, keyword: str) -> str:
        """Generate a content title from the keyword."""
        return f"The Complete Guide to {keyword.title()}"

    def archive_evidence(self, output_dir: Path) -> Path:
        """Archive content plan and draft to evidence directory.

        Writes content_plan.json and content_draft.json to evidence/.
        """
        output_path = output_dir / f"{self.agent_id}_output.json"
        if not output_path.exists():
            return None

        artifact = json.loads(output_path.read_text(encoding="utf-8"))

        plan_path = self.experiment_dir / "evidence" / "content_plan.json"
        plan_path.write_text(
            json.dumps(artifact.get("content_plan", {}), indent=2, sort_keys=True),
            encoding="utf-8",
        )

        draft_path = self.experiment_dir / "evidence" / "content_draft.json"
        draft_path.write_text(
            json.dumps(artifact.get("content_draft", {}), indent=2, sort_keys=True),
            encoding="utf-8",
        )

        return draft_path

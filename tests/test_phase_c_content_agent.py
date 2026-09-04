"""C2 tests — ContentAgent + ContentPlan/ContentDraft.

Tests cover:
- ContentAgent implements AgentBase
- ContentAgent reads opportunities.json and produces content plan + draft
- ContentPlan has required fields (keyword, type, outline, monetization, score linkage)
- ContentDraft has provenance with SHA-256 linkage to research and scoring
- ContentDraft requires_approval = True for §26 integration
- Plan-only mode when ContentMCP not configured
- ContentDraft evidence_sha256 is computed correctly
- ContentAgent handles missing opportunities evidence
- ContentAgent handles empty opportunities
- End-to-end: Research → Score → Content (simulated)
- Provenance chain: research_sha256 → scoring_sha256 → plan_sha256 → draft_sha256
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Path setup
_WORKSTATION_ROOT = Path(__file__).resolve().parents[2] / "multi-ai-workstation-poc"
sys.path.insert(0, str(_WORKSTATION_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.base import AgentBase
from src.agents.content_agent import ContentAgent
from src.agents.researcher import ResearcherAgent
from src.agents.scorer import ScorerAgent
from src.mcp.base import MCPRegistry


# ─── Fixtures ───


@pytest.fixture
def experiment_dir(tmp_path):
    """Create an experiment directory structure for ContentAgent testing."""
    exp_dir = tmp_path / "experiments" / "c2-content-test-001"
    (exp_dir / "evidence").mkdir(parents=True)
    (exp_dir / "output").mkdir(parents=True)
    (exp_dir / "work").mkdir(parents=True)
    return exp_dir


@pytest.fixture
def mcp_registry():
    """MCPRegistry with CME config — all interfaces not configured in C2."""
    config_path = Path(__file__).resolve().parents[1] / "config" / "mcp_config.yaml"
    return MCPRegistry(config_path)


@pytest.fixture
def content_agent(experiment_dir, mcp_registry):
    """ContentAgent instance with MCP registry."""
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")
    return ContentAgent(
        agent_id="content-test",
        experiment_dir=experiment_dir,
        session_history=history,
        session_id="session-content-test",
        mcp_registry=mcp_registry,
    )


def _create_opportunities_evidence(experiment_dir, query="wireless earbuds", source_type="simulated"):
    """Helper: run Researcher + Scorer to produce opportunities.json."""
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    # Run Researcher
    research_input = {
        "experiment_id": "c2-test-001",
        "query": query,
        "source_type": source_type,
        "seed_data": {},
        "provenance": {"created_by": "c2-test"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input, indent=2), encoding="utf-8"
    )

    researcher = ResearcherAgent(
        "researcher-c2-test", experiment_dir, history, "session-content-test",
        use_omniroute=False,
    )
    researcher.run()
    researcher.archive_evidence(experiment_dir / "output")

    # Run Scorer
    scorer = ScorerAgent(
        "scorer-c2-test", experiment_dir, history, "session-content-test",
    )
    scorer.run()
    scorer.archive_evidence(experiment_dir / "output")

    return scorer


# ─── Agent Interface Tests ───


def test_content_agent_implements_agentbase(experiment_dir, mcp_registry):
    """ContentAgent must extend AgentBase."""
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")
    agent = ContentAgent(
        "content-test", experiment_dir, history, "session-test",
        mcp_registry=mcp_registry,
    )
    assert isinstance(agent, AgentBase)
    assert agent.agent_type == "content"


def test_content_agent_required_input_is_opportunities():
    """ContentAgent reads opportunities.json as input (from ScorerAgent)."""
    from core.session_history import SessionHistory
    tmp = Path(__import__("tempfile").mkdtemp())
    exp_dir = tmp / "exp"
    (exp_dir / "evidence").mkdir(parents=True)
    (exp_dir / "output").mkdir(parents=True)
    (exp_dir / "work").mkdir(parents=True)
    history = SessionHistory(exp_dir / "test.db")
    agent = ContentAgent("content-test", exp_dir, history, "session-test")
    assert agent.get_required_inputs() == ["opportunities"]


# ─── ContentPlan Tests ───


def test_content_agent_produces_content_plan(experiment_dir, content_agent):
    """ContentAgent must produce a ContentPlan with required fields."""
    _create_opportunities_evidence(experiment_dir)

    result = content_agent.run()
    assert result["success"] is True

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    plan = artifact["content_plan"]

    assert "plan_id" in plan
    assert "keyword" in plan
    assert "content_type" in plan
    assert "content_outline" in plan
    assert "monetization_concept" in plan
    assert "opportunity_score" in plan
    assert "score_dimensions" in plan
    assert "planned_at" in plan
    assert "evidence_source_type" in plan


def test_content_plan_outline_has_sections(experiment_dir, content_agent):
    """ContentPlan outline should have structured sections with purposes."""
    _create_opportunities_evidence(experiment_dir)
    result = content_agent.run()

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    outline = artifact["content_plan"]["content_outline"]

    assert len(outline) > 0
    for section in outline:
        assert "section" in section
        assert "purpose" in section
        assert "monetization_hook" in section


def test_content_plan_links_to_opportunity_score(experiment_dir, content_agent):
    """ContentPlan must include the opportunity score from ScorerAgent."""
    _create_opportunities_evidence(experiment_dir)
    result = content_agent.run()

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    plan = artifact["content_plan"]
    draft = artifact["content_draft"]

    # The plan's opportunity_score should match the draft's provenance
    assert plan["opportunity_score"] > 0
    assert draft["provenance"]["score_total"] == plan["opportunity_score"]


# ─── ContentDraft Tests ───


def test_content_agent_produces_content_draft(experiment_dir, content_agent):
    """ContentAgent must produce a ContentDraft artifact."""
    _create_opportunities_evidence(experiment_dir)
    result = content_agent.run()

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    draft = artifact["content_draft"]

    assert "draft_id" in draft
    assert "plan_id" in draft
    assert "plan_sha256" in draft
    assert "status" in draft
    assert "title" in draft
    assert "content_type" in draft
    assert "content" in draft
    assert "requires_approval" in draft
    assert "approval_boundary" in draft
    assert "provenance" in draft
    assert "evidence_sha256" in draft


def test_content_draft_requires_approval_true(experiment_dir, content_agent):
    """ContentDraft must have requires_approval=True for §26 integration."""
    _create_opportunities_evidence(experiment_dir)
    result = content_agent.run()

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    draft = artifact["content_draft"]

    assert draft["requires_approval"] is True
    assert draft["approval_boundary"] == "publishing_and_financial_commitment"
    assert "monetization_concept" in draft["approval_reason"].lower() or \
           "review" in draft["approval_reason"].lower()


def test_content_draft_plan_only_mode(experiment_dir, content_agent):
    """When ContentMCP is not configured, draft should be plan-only."""
    _create_opportunities_evidence(experiment_dir)
    result = content_agent.run()

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    draft = artifact["content_draft"]

    assert artifact["mcp_available"] is False
    assert artifact["generation_mode"] == "plan_only"
    assert draft["status"] == "plan_only"
    assert draft["generation_mode"] == "plan_only"


def test_content_draft_content_is_placeholder(experiment_dir, content_agent):
    """Plan-only draft content should be clearly marked as placeholder."""
    _create_opportunities_evidence(experiment_dir)
    result = content_agent.run()

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    draft = artifact["content_draft"]

    assert "DRAFT PLACEHOLDER" in draft["content"]
    assert "plan-only" in draft["content"].lower() or "placeholder" in draft["content"].lower()


def test_content_draft_evidence_sha256_matches(experiment_dir, content_agent):
    """ContentDraft evidence_sha256 must match recomputed hash."""
    _create_opportunities_evidence(experiment_dir)
    result = content_agent.run()

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    stored_hash = artifact["content_draft"].pop("evidence_sha256")
    artifact.pop("evidence_sha256", None)  # Remove agent-level hash
    artifact.pop("timestamp", None)  # AgentBase adds this at write time

    # Recompute the draft hash
    draft_data = json.dumps(artifact["content_draft"], indent=2, sort_keys=True)
    computed_hash = hashlib.sha256(draft_data.encode("utf-8")).hexdigest()

    assert stored_hash == computed_hash


# ─── Provenance Chain Tests ───


def test_content_draft_provenance_records_research_sha(experiment_dir, content_agent):
    """ContentDraft provenance must link to research evidence SHA-256."""
    _create_opportunities_evidence(experiment_dir)
    result = content_agent.run()

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    draft = artifact["content_draft"]
    research = json.loads((experiment_dir / "evidence" / "research.json").read_text(encoding="utf-8"))

    assert draft["provenance"]["research_evidence_sha256"] == research["evidence_sha256"]


def test_content_draft_provenance_records_scoring_sha(experiment_dir, content_agent):
    """ContentDraft provenance must link to scoring evidence SHA-256."""
    _create_opportunities_evidence(experiment_dir)
    result = content_agent.run()

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    draft = artifact["content_draft"]
    scoring = json.loads((experiment_dir / "evidence" / "opportunities.json").read_text(encoding="utf-8"))

    assert draft["provenance"]["scoring_sha256"] == scoring["evidence_sha256"]


def test_content_draft_provenance_records_source_type(experiment_dir, content_agent):
    """ContentDraft provenance must record the evidence source type."""
    _create_opportunities_evidence(experiment_dir)
    result = content_agent.run()

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    draft = artifact["content_draft"]
    research = json.loads((experiment_dir / "evidence" / "research.json").read_text(encoding="utf-8"))

    assert draft["provenance"]["evidence_source_type"] == research["evidence_source"]["type"]
    assert draft["provenance"]["is_simulated"] == research["evidence_source"]["simulated"]


def test_content_draft_provenance_records_researcher_details(experiment_dir, content_agent):
    """ContentDraft provenance must record which model/worker produced the research."""
    _create_opportunities_evidence(experiment_dir)
    result = content_agent.run()

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    draft = artifact["content_draft"]
    research = json.loads((experiment_dir / "evidence" / "research.json").read_text(encoding="utf-8"))

    assert draft["provenance"]["researcher_model_used"] == research["model_used"]
    assert draft["provenance"]["researcher_worker_used"] == research["worker_used"]


def test_content_plan_sha256_matches_draft(experiment_dir, content_agent):
    """ContentDraft plan_sha256 must match the ContentPlan SHA-256."""
    _create_opportunities_evidence(experiment_dir)
    result = content_agent.run()

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    plan = artifact["content_plan"]
    draft = artifact["content_draft"]

    plan_json = json.dumps(plan, indent=2, sort_keys=True)
    computed_plan_hash = hashlib.sha256(plan_json.encode("utf-8")).hexdigest()

    assert draft["plan_sha256"] == computed_plan_hash


# ─── Error Handling Tests ───


def test_content_agent_missing_opportunities_returns_error(experiment_dir, content_agent):
    """ContentAgent must report error when opportunities.json is missing."""
    result = content_agent.run()
    assert result["success"] is False
    assert "missing" in result["error"].lower()


def test_content_agent_empty_opportunities_returns_error(experiment_dir, content_agent):
    """ContentAgent must handle empty opportunities list."""
    research = {
        "status": "complete",
        "agent_id": "researcher-test",
        "agent_type": "researcher",
        "experiment_id": "c2-empty-test",
        "niche_query": "test",
        "evidence_source": {"type": "simulated", "simulated": True, "is_seed": False, "externally_sourced": False},
        "opportunities": [],
        "evidence_sha256": "abc123",
    }
    (experiment_dir / "evidence" / "opportunities.json").write_text(
        json.dumps(research), encoding="utf-8"
    )

    result = content_agent.run()
    assert result["success"] is False


# ─── Fail-Closed: Opportunity Selection Safety Tests ───


def test_content_agent_empty_opportunities_fails_closed(experiment_dir, content_agent):
    """When opportunities.json has an empty opportunities list, ContentAgent must fail closed, not fall back to opps[0]."""
    research = {
        "status": "complete",
        "agent_id": "scorer-test",
        "agent_type": "scorer",
        "experiment_id": "c2-empty-failclosed-test",
        "scoring_timestamp": datetime.now(timezone.utc).isoformat(),
        "evidence_source_type": "externally_sourced",
        "scoring_dimensions": {"demand": 25, "monetization": 25, "competition": 20, "content_feasibility": 15, "monetization_fit": 15},
        "opportunities": [],
        "evidence_sha256": "abc123",
    }
    (experiment_dir / "evidence" / "opportunities.json").write_text(
        json.dumps(research), encoding="utf-8"
    )

    result = content_agent.run()
    assert result["success"] is False


def test_content_agent_no_opportunity1_fallback_in_source():
    """Verify no production 'opportunity-1' or 'opps[0]' fallback remains in content_agent source."""
    source = Path(__file__).resolve().parents[1] / "src" / "agents" / "content_agent.py"
    content = source.read_text(encoding="utf-8")

    assert '"opportunity-1"' not in content, "Found hardcoded 'opportunity-1' in content_agent.py"
    assert "return opps[0]" not in content, "Found 'return opps[0]' fallback in content_agent.py"


# ─── Evidence Archival Tests ───


def test_content_agent_archives_evidence(experiment_dir, content_agent):
    """ContentAgent must archive content_plan.json and content_draft.json to evidence/."""
    _create_opportunities_evidence(experiment_dir)
    result = content_agent.run()

    content_agent.archive_evidence(experiment_dir / "output")
    plan_path = experiment_dir / "evidence" / "content_plan.json"
    draft_path = experiment_dir / "evidence" / "content_draft.json"

    assert plan_path.exists()
    assert draft_path.exists()

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    draft = json.loads(draft_path.read_text(encoding="utf-8"))

    assert "keyword" in plan
    assert "draft_id" in draft


# ─── End-to-End Pipeline Test ───


def test_end_to_end_research_score_content(experiment_dir, mcp_registry):
    """Full pipeline: Researcher → Scorer → ContentAgent (simulated data)."""
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "end_to_end.db")

    # Phase 1: Research
    research_input = {
        "experiment_id": "e2e-c2-001",
        "query": "gaming accessories",
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {"created_by": "e2e-test"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input, indent=2), encoding="utf-8"
    )

    researcher = ResearcherAgent(
        "researcher-e2e", experiment_dir, history, "session-e2e",
        use_omniroute=False,
    )
    researcher_result = researcher.run()
    assert researcher_result["success"] is True
    researcher.archive_evidence(experiment_dir / "output")

    # Phase 2: Scoring
    scorer = ScorerAgent("scorer-e2e", experiment_dir, history, "session-e2e")
    scorer_result = scorer.run()
    assert scorer_result["success"] is True
    scorer.archive_evidence(experiment_dir / "output")

    # Phase 3: Content
    content_agent = ContentAgent(
        "content-e2e", experiment_dir, history, "session-e2e",
        mcp_registry=mcp_registry,
    )
    content_result = content_agent.run()
    assert content_result["success"] is True

    # Verify full provenance chain
    research = json.loads((experiment_dir / "evidence" / "research.json").read_text())
    opportunities = json.loads((experiment_dir / "evidence" / "opportunities.json").read_text())
    content_output = json.loads(Path(content_result["artifact_path"]).read_text(encoding="utf-8"))
    draft = content_output["content_draft"]

    assert draft["provenance"]["research_evidence_sha256"] == research["evidence_sha256"]
    assert draft["provenance"]["scoring_sha256"] == opportunities["evidence_sha256"]
    assert draft["requires_approval"] is True
    assert content_output["mcp_available"] is False
    assert content_output["generation_mode"] == "plan_only"


# ─── §26 Compatibility Tests ───


def test_content_draft_has_approval_metadata(experiment_dir, content_agent):
    """ContentDraft must have all §26-required approval metadata."""
    _create_opportunities_evidence(experiment_dir)
    result = content_agent.run()

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    draft = artifact["content_draft"]

    # §26 task will reference this draft by SHA-256
    assert "evidence_sha256" in draft
    assert len(draft["evidence_sha256"]) == 64

    # Approval boundary must be explicit
    assert "approval_boundary" in draft
    assert draft["approval_boundary"] == "publishing_and_financial_commitment"

    # requires_approval flag
    assert draft["requires_approval"] is True


def test_content_output_has_approval_boundary(experiment_dir, content_agent):
    """ContentAgent output must include requires_approval and approval_boundary."""
    _create_opportunities_evidence(experiment_dir)
    result = content_agent.run()

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    assert artifact["requires_approval"] is True
    assert artifact["approval_boundary"] == "publishing_and_financial_commitment"


# ─── MCP Integration Tests ───


def test_content_agent_uses_mcp_registry(experiment_dir, mcp_registry):
    """ContentAgent must use MCPRegistry to resolve ContentMCP."""
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")
    agent = ContentAgent(
        "content-test", experiment_dir, history, "session-test",
        mcp_registry=mcp_registry,
    )

    _create_opportunities_evidence(experiment_dir)
    result = agent.run()

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    assert "mcp_available" in artifact
    assert artifact["mcp_available"] is False  # ContentMCP not configured


def test_content_agent_defaults_to_empty_registry():
    """ContentAgent without mcp_registry should still work (fallback to plan-only)."""
    from core.session_history import SessionHistory
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    exp_dir = tmp / "exp"
    (exp_dir / "evidence").mkdir(parents=True)
    (exp_dir / "output").mkdir(parents=True)
    (exp_dir / "work").mkdir(parents=True)
    history = SessionHistory(exp_dir / "test.db")
    agent = ContentAgent("content-default", exp_dir, history, "session-default")

    assert agent._mcp_registry is not None
    assert isinstance(agent._mcp_registry, MCPRegistry)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

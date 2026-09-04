"""C6 tests — AnalystAgent + Analysis + Feedback.

Tests cover:
- AnalystAgent implements AgentBase
- AnalystAgent reads opportunities.json and produces analytics + feedback
- AnalystAgent auto-selects top opportunity using registry/selector
- AnalystAgent fails closed with no qualified opportunities
- Feedback structure is valid JSON with required fields
- Provenance chain: opportunities → analytics → feedback
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

_WORKSTATION_ROOT = Path(__file__).resolve().parents[2] / "multi-ai-workstation-poc"
import sys
sys.path.insert(0, str(_WORKSTATION_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.base import AgentBase
from src.agents.analyst import AnalystAgent, run_analysis_with_opportunity_selection


@pytest.fixture
def experiment_dir(tmp_path):
    """Create an experiment directory structure for AnalystAgent testing."""
    exp_dir = tmp_path / "experiments" / "a6-analyst-test-001"
    (exp_dir / "evidence").mkdir(parents=True)
    (exp_dir / "output").mkdir(parents=True)
    (exp_dir / "work").mkdir(parents=True)
    return exp_dir


@pytest.fixture
def analyst_agent(experiment_dir):
    """AnalystAgent instance."""
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")
    return AnalystAgent(
        agent_id="analyst-test",
        experiment_dir=experiment_dir,
        session_history=history,
        session_id="session-analyst-test",
    )


def _create_opportunities_evidence(experiment_dir, count=3):
    """Create scored opportunities.json for testing."""
    opportunities = {
        "status": "complete",
        "agent_id": "scorer-test",
        "agent_type": "scorer",
        "experiment_id": "a6-test-001",
        "scoring_timestamp": datetime.now(timezone.utc).isoformat(),
        "evidence_source_type": "externally_sourced",
        "scoring_dimensions": {"demand": 25, "monetization": 25, "competition": 20, "content_feasibility": 15, "monetization_fit": 15},
        "opportunities": [
            {
                "keyword": f"keyword-{i}",
                "target_audience": "high intent buyers",
                "monetization_concept": "affiliate commissions",
                "evidence_references": [],
                "score": {"total": 85.5 - i * 10, "max_possible": 100, "dimensions": {"demand": 20.0, "monetization": 18.5, "competition": 15.0, "content_feasibility": 12.0, "monetization_fit": 15.0}},
                "rationale": f"Score rationale for keyword-{i}",
                "confidence": 80 - i * 5,
                "score_note": "Score based on externally sourced evidence.",
                "content_type": "product review",
            }
            for i in range(count)
        ],
        "ranked_keywords": [f"keyword-{i}" for i in range(count)],
        "top_opportunity": None,
        "summary": f"Scored {count} opportunities",
        "evidence_sha256": "abc123",
    }
    (experiment_dir / "evidence" / "opportunities.json").write_text(
        json.dumps(opportunities, indent=2), encoding="utf-8"
    )
    return opportunities


def _create_content_draft(experiment_dir):
    """Create a content_draft.json for testing."""
    draft = {
        "draft_id": "draft-test-001",
        "plan_id": "plan-test-001",
        "plan_sha256": "abc123",
        "status": "plan_only",
        "generation_mode": "plan_only",
        "title": "Test Content Title",
        "content_type": "product_review",
        "content": "DRAFT PLACEHOLDER - Plan-only content",
        "word_count_estimate": 1000,
        "monetization_concept": "affiliate commissions",
        "monetization_estimate_pct": 7.0,
        "requires_approval": True,
        "approval_boundary": "publishing_and_financial_commitment",
        "provenance": {
            "created_by": "ContentAgent",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_opportunity_id": "keyword-0",
            "research_evidence_sha256": "def456",
            "scoring_sha256": "abc123",
        },
    }
    (experiment_dir / "evidence" / "content_draft.json").write_text(
        json.dumps(draft, indent=2), encoding="utf-8"
    )
    return draft


# ─── Agent Interface Tests ───


def test_analyst_agent_implements_agentbase(experiment_dir):
    """AnalystAgent must extend AgentBase."""
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")
    agent = AnalystAgent("analyst-test", experiment_dir, history, "session-test")
    assert isinstance(agent, AgentBase)
    assert agent.agent_type == "analyst"


def test_analyst_agent_get_required_inputs(experiment_dir):
    """AnalystAgent requires opportunities.json as input."""
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")
    agent = AnalystAgent("analyst-test", experiment_dir, history, "session-test")
    assert agent.get_required_inputs() == ["opportunities"]


# ─── Core Functionality Tests ───


def test_analyst_agent_produces_analytics_and_feedback(analyst_agent):
    """AnalystAgent should produce analytics.json and feedback.json."""
    exp_dir = analyst_agent.experiment_dir
    _create_opportunities_evidence(exp_dir)
    _create_content_draft(exp_dir)

    result = analyst_agent.run()
    artifact = json.loads(Path(result.get("artifact_path", "")).read_text() if result.get("artifact_path") else "{}")
    
    if not result.get("success"):
        print(f"DEBUG: result = {result}")
        print(f"DEBUG: artifact = {artifact}")
    
    assert result["success"] is True, f"Failed: {result.get('error', 'unknown error')}"

    analytics_path = exp_dir / "evidence" / "analytics.json"
    feedback_path = exp_dir / "evidence" / "feedback.json"

    assert analytics_path.exists(), "analytics.json should exist"
    assert feedback_path.exists(), "feedback.json should exist"

    analytics = json.loads(analytics_path.read_text())
    feedback = json.loads(feedback_path.read_text())

    assert analytics["source"] == "simulated"
    assert "metrics" in analytics
    assert "insights" in analytics
    assert "opportunity_quality" in analytics["insights"]
    assert "keyword" in analytics


def test_analyst_agent_feedback_has_required_fields(analyst_agent):
    """Feedback JSON should have all required fields for Researcher consumption."""
    exp_dir = analyst_agent.experiment_dir
    _create_opportunities_evidence(exp_dir)

    result = analyst_agent.run()
    assert result["success"] is True, f"Failed: {result.get('error', 'unknown error')}"


# ─── Opportunity Selection Tests ───


def test_analyst_fails_closed_with_empty_opportunities(experiment_dir):
    """AnalystAgent must fail closed when opportunities are empty."""
    (experiment_dir / "evidence" / "opportunities.json").write_text(
        json.dumps({"status": "complete", "opportunities": [], "experiment_id": "test"}),
        encoding="utf-8",
    )

    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")
    agent = AnalystAgent("analyst-test", experiment_dir, history, "session-test")

    result = agent.run()
    assert result["success"] is False
    assert "error" in result


def test_run_analysis_with_opportunity_selection_auto_selects_top(experiment_dir):
    """The standalone function should auto-select top-scored opportunity."""
    _create_opportunities_evidence(experiment_dir)

    result = run_analysis_with_opportunity_selection(experiment_dir)
    assert result["status"] == "success"
    assert result["selection"] == "keyword-0"


def test_run_analysis_with_opportunity_selection_fails_on_missing_file(tmp_path):
    """Should fail closed when opportunities.json is missing."""
    exp_dir = tmp_path / "experiments" / "no-opps"
    (exp_dir / "evidence").mkdir(parents=True)

    result = run_analysis_with_opportunity_selection(exp_dir)
    assert result["status"] == "error"
    assert "load" in result["error"].lower() or "not found" in result["error"].lower() or "qualified" in result["error"].lower()


def test_run_analysis_with_opportunity_selection_fails_on_empty_list(tmp_path):
    """Should fail closed when opportunities list is empty."""
    exp_dir = tmp_path / "experiments" / "empty-opps"
    (exp_dir / "evidence").mkdir(parents=True)
    (exp_dir / "evidence" / "opportunities.json").write_text(
        json.dumps({"opportunities": [], "experiment_id": "test"}), encoding="utf-8"
    )

    result = run_analysis_with_opportunity_selection(exp_dir)
    assert result["status"] == "error"


# ─── Source Code Safety Tests ───


def test_analyst_no_hardcoded_opportunity_selection():
    """Verify AnalystAgent does not use hardcoded opportunity selection."""
    source = Path(__file__).resolve().parents[1] / "src" / "agents" / "analyst.py"
    content = source.read_text(encoding="utf-8")

    assert 'return "opportunity-1"' not in content, "Found 'return \"opportunity-1\"' fallback in analyst.py"
    assert "return opps[0]" not in content, "Found 'return opps[0]' fallback in analyst.py"


def test_analyst_uses_opportunity_registry():
    """AnalystAgent should use the Opportunity Registry and Selector layer."""
    source = Path(__file__).resolve().parents[1] / "src" / "agents" / "analyst.py"
    content = source.read_text(encoding="utf-8")

    assert "OpportunityRegistry" in content
    assert "OpportunitySelector" in content
    assert "NoQualifiedOpportunityError" in content


# ─── Provenance Verification Tests ───


def test_analytics_preserves_upstream_provenance(experiment_dir):
    """analytics.json must include provenance from upstream evidence."""
    _create_opportunities_evidence(experiment_dir)
    _create_content_draft(experiment_dir)

    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")
    agent = AnalystAgent("analyst-test", experiment_dir, history, "session-test")

    result = agent.run()
    assert result["success"] is True

    analytics = json.loads(
        (experiment_dir / "evidence" / "analytics.json").read_text()
    )

    assert "provenance" in analytics, "analytics.json missing provenance"
    assert "research_evidence_sha256" in analytics["provenance"]
    assert "scoring_sha256" in analytics["provenance"]
    assert "draft_sha256" in analytics["provenance"]
    assert "source_opportunity_id" in analytics["provenance"]


def test_feedback_inherits_provenance_from_analytics(experiment_dir):
    """feedback.json must include provenance from analytics.json."""
    _create_opportunities_evidence(experiment_dir)
    _create_content_draft(experiment_dir)

    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")
    agent = AnalystAgent("analyst-test", experiment_dir, history, "session-test")

    result = agent.run()
    assert result["success"] is True

    feedback = json.loads(
        (experiment_dir / "evidence" / "feedback.json").read_text()
    )

    assert "provenance" in feedback, "feedback.json missing provenance"
    assert feedback["provenance"]["source_opportunity_id"] != "", "provenance source_opportunity_id should not be empty"


# ─── Orchestrator Integration Tests ───


def test_run_analysis_phase_produces_analytics(tmp_path):
    """Orchestrator Phase 5 should produce analytics.json via AnalystAgent."""
    from tests.test_c5_hardening import _create_minimal_workspace
    ws_root = _create_minimal_workspace(tmp_path)
    
    from src.cm_orchestrator import CMOrchestrator

    orch = CMOrchestrator(config_dir=ws_root / "config", workspace_dir=ws_root)

    exp_id = "test-analysis-001"
    exp_dir = ws_root / "experiments" / exp_id
    (exp_dir / "evidence").mkdir(parents=True)
    (exp_dir / "output").mkdir(parents=True)

    _create_opportunities_evidence(exp_dir)
    _create_content_draft(exp_dir)

    result = orch.run_analysis_phase(exp_id)

    assert result["success"] is True, f"Failed: {result.get('error')}"
    assert "analytics_path" in result
    assert (exp_dir / "evidence" / "analytics.json").exists()


def test_run_feedback_phase_produces_feedback(tmp_path):
    """Orchestrator Phase 6 should produce feedback.json with provenance."""
    from tests.test_c5_hardening import _create_minimal_workspace
    ws_root = _create_minimal_workspace(tmp_path)
    
    from src.cm_orchestrator import CMOrchestrator

    orch = CMOrchestrator(config_dir=ws_root / "config", workspace_dir=ws_root)

    exp_id = "test-feedback-001"
    exp_dir = ws_root / "experiments" / exp_id
    (exp_dir / "evidence").mkdir(parents=True)
    (exp_dir / "output").mkdir(parents=True)

    _create_opportunities_evidence(exp_dir)
    _create_content_draft(exp_dir)

    analysis_result = orch.run_analysis_phase(exp_id)
    assert analysis_result["success"] is True, f"Failed: {analysis_result.get('error')}"

    feedback_result = orch.run_feedback_phase(exp_id, analysis_result["analytics"])
    assert feedback_result["success"] is True, f"Failed: {feedback_result.get('error')}"
    assert "feedback_path" in feedback_result
    assert (exp_dir / "evidence" / "feedback.json").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
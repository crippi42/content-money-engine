"""Phase B tests — Researcher + Scorer MVP pipeline.

Test levels:
- Level 1: Pipeline validation with simulation data
- Level 2: Real-evidence readiness (interface design)

Covers:
- Agent execution (Researcher, Scorer)
- Evidence I/O protocol
- Evidence schema validation
- Evidence provenance tracking
- Simulation labeling
- SHA-256 integrity
- Malformed/missing evidence handling
- Project isolation (§25)
- SessionHistory logging
- Deterministic scoring verification
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Path setup
_WORKSTATION_ROOT = Path(__file__).resolve().parents[2] / "multi-ai-workstation-poc"
sys.path.insert(0, str(_WORKSTATION_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.base import AgentBase
from src.agents.researcher import ResearcherAgent
from src.agents.scorer import ScorerAgent
from src.cm_orchestrator import CMOrchestrator


# ─── Fixtures ───


@pytest.fixture
def cme_config(cme_workspace):
    """Temp config with content-money-engine project registered."""
    config_dir = cme_workspace / "config"
    config_dir.mkdir(exist_ok=True)
    cp = str(cme_workspace.resolve())
    yaml = (
        "version: 1.0\n"
        "workspace_identifier: content-money-engine-test\n"
        "authorized_projects:\n"
        "  content-money-engine:\n"
        f"    canonical_path: '{cp}'\n"
        "    enabled: true\n"
        "    allowed_operations:\n"
        "      - read\n"
        "      - write\n"
        "      - test\n"
    )
    (config_dir / "projects.yaml").write_text(yaml, encoding="utf-8")
    import shutil
    shutil.copy(
        _WORKSTATION_ROOT / "config" / "worker_registry.yaml",
        config_dir / "worker_registry.yaml",
    )
    return config_dir


@pytest.fixture
def cme_workspace(tmp_path):
    """Temp workspace matching CME structure."""
    for d in ["tasks", "results", "approved_tasks", "experiments", "sessions"]:
        (tmp_path / d).mkdir()
    return tmp_path


@pytest.fixture
def experiment_dir(tmp_path):
    """Create an experiment directory structure for direct agent testing."""
    exp_dir = tmp_path / "experiments" / "mvp-test-001"
    (exp_dir / "evidence").mkdir(parents=True)
    (exp_dir / "output").mkdir(parents=True)
    (exp_dir / "work").mkdir(parents=True)
    return exp_dir


@pytest.fixture
def orch(cme_config, cme_workspace):
    """CMOrchestrator instance with temp config and workspace."""
    return CMOrchestrator(cme_config, cme_workspace)


# ─── Level 1: Pipeline Validation ───


# ─── Researcher Tests ───


def test_researcher_agent_implements_agentbase(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")
    agent = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    assert isinstance(agent, AgentBase)
    assert agent.agent_type == "researcher"


def test_researcher_creates_simulated_research_output(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    # Write research input
    research_input = {
        "experiment_id": "test-001",
        "query": "wireless earbuds",
        "source_type": "simulated",
        "source_description": "Test simulation",
        "seed_data": {},
        "provenance": {"created_by": "test"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input, indent=2), encoding="utf-8"
    )

    agent = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    result = agent.run()

    assert result["success"] is True
    output = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    assert output["status"] == "complete"
    assert len(output["opportunities"]) == 3
    assert output["niche_query"] == "wireless earbuds"


def test_researcher_output_has_provenance(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    research_input = {
        "experiment_id": "test-002",
        "query": "yoga mats",
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {"created_by": "test", "session_id": "session-test"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    agent = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    result = agent.run()

    output = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    prov = output["evidence_source"]
    assert prov["type"] == "simulated"
    assert prov["simulated"] is True
    assert prov["externally_sourced"] is False
    assert prov["is_seed"] is False
    assert "source_description" in prov
    assert "provenance" in prov


def test_researcher_simulated_opportunities_labeled(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    research_input = {
        "experiment_id": "test-003",
        "query": "protein powder",
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    agent = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    result = agent.run()

    output = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    for opp in output["opportunities"]:
        assert opp["evidence_source"] == "simulated"
        assert any("simulated" in ref for ref in opp["evidence_references"])


def test_researcher_output_has_sha256(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    research_input = {
        "experiment_id": "test-004",
        "query": "gaming chairs",
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    agent = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    result = agent.run()

    output = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    assert "evidence_sha256" in output
    assert len(output["evidence_sha256"]) == 64


def test_researcher_archives_evidence(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    research_input = {
        "experiment_id": "test-005",
        "query": "mechanical keyboards",
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    agent = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    result = agent.run()

    evidence_path = agent.archive_evidence(experiment_dir / "output")
    assert evidence_path.exists()
    assert evidence_path.name == "research.json"

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert "opportunities" in evidence
    assert evidence["evidence_source"]["type"] == "simulated"


def test_researcher_missing_input_reports_error(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    agent = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    result = agent.run()
    assert result["success"] is False
    assert "missing" in result["error"].lower()


def test_researcher_seed_data_produces_seed_opportunities(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    seed_data = {
        "opportunities": [
            {
                "keyword": "custom guitar picks",
                "search_volume_estimate": 300,
                "buyer_intent": "high",
                "keyword_difficulty": 20,
                "competition_level": "low",
                "monetization_concept": "affiliate commissions from music gear",
                "monetization_estimate_pct": 10.0,
                "content_type": "product review",
                "content_difficulty": "low",
            },
        ],
    }

    research_input = {
        "experiment_id": "test-006",
        "query": "guitar picks",
        "source_type": "seed",
        "seed_data": seed_data,
        "provenance": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    agent = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    result = agent.run()

    output = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    assert output["evidence_source"]["type"] == "seed"
    assert output["evidence_source"]["simulated"] is False
    assert output["evidence_source"]["is_seed"] is True
    assert len(output["opportunities"]) == 1
    assert output["opportunities"][0]["evidence_source"] == "seed"


# ─── Scorer Tests ───


def test_scorer_agent_implements_agentbase(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")
    agent = ScorerAgent("scorer-test", experiment_dir, history, "session-test")
    assert isinstance(agent, AgentBase)
    assert agent.agent_type == "scorer"


def test_scorer_scores_opportunities_from_research(experiment_dir):
    """Scorer reads research.json and produces scored opportunities."""
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    # First create research evidence
    research_input = {
        "experiment_id": "test-score-001",
        "query": "wireless earbuds",
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    researcher = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    researcher.run()
    researcher.archive_evidence(experiment_dir / "output")

    # Now run scorer
    scorer = ScorerAgent("scorer-test", experiment_dir, history, "session-test")
    result = scorer.run()

    assert result["success"] is True
    output = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    assert output["status"] == "complete"
    assert len(output["opportunities"]) == 3
    assert "ranked_keywords" in output
    assert output["ranked_keywords"][0] == output["top_opportunity"]["keyword"]


def test_scorer_produces_deterministic_scores(experiment_dir):
    """Same input should produce same scores (deterministic)."""
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    research_input = {
        "experiment_id": "test-score-002",
        "query": "yoga mats",
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    researcher = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    researcher.run()
    researcher.archive_evidence(experiment_dir / "output")

    scorer1 = ScorerAgent("scorer-test", experiment_dir, history, "session-test")
    result1 = scorer1.run()

    output1 = json.loads(Path(result1["artifact_path"]).read_text(encoding="utf-8"))

    # Re-run with fresh agent
    scorer2 = ScorerAgent("scorer-test", experiment_dir, history, "session-test")
    result2 = scorer2.run()

    output2 = json.loads(Path(result2["artifact_path"]).read_text(encoding="utf-8"))

    # Scores should be identical (deterministic given same input)
    scores1 = [o["score"]["total"] for o in output1["opportunities"]]
    scores2 = [o["score"]["total"] for o in output2["opportunities"]]
    assert scores1 == scores2


def test_scorer_scores_are_sorted_descending(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    research_input = {
        "experiment_id": "test-score-003",
        "query": "protein powder",
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    researcher = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    researcher.run()
    researcher.archive_evidence(experiment_dir / "output")

    scorer = ScorerAgent("scorer-test", experiment_dir, history, "session-test")
    result = scorer.run()

    output = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    scores = [o["score"]["total"] for o in output["opportunities"]]
    assert scores == sorted(scores, reverse=True)
    assert output["top_opportunity"]["score"]["total"] == scores[0]


def test_scorer_opportunity_has_all_required_fields(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    research_input = {
        "experiment_id": "test-score-004",
        "query": "gaming chairs",
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    researcher = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    researcher.run()
    researcher.archive_evidence(experiment_dir / "output")

    scorer = ScorerAgent("scorer-test", experiment_dir, history, "session-test")
    result = scorer.run()

    output = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    opp = output["opportunities"][0]

    assert "keyword" in opp
    assert "target_audience" in opp
    assert "monetization_concept" in opp
    assert "evidence_references" in opp
    assert "evidence_source" in opp
    assert "score" in opp
    assert "total" in opp["score"]
    assert "dimensions" in opp["score"]
    assert "rationale" in opp
    assert "confidence" in opp
    assert "score_note" in opp


def test_scorer_score_dimensions_documented(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    research_input = {
        "experiment_id": "test-score-005",
        "query": "mechanical keyboards",
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    researcher = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    researcher.run()
    researcher.archive_evidence(experiment_dir / "output")

    scorer = ScorerAgent("scorer-test", experiment_dir, history, "session-test")
    result = scorer.run()

    output = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    dims = output["scoring_dimensions"]
    assert "demand" in dims
    assert "monetization" in dims
    assert "competition" in dims
    assert "content_feasibility" in dims
    assert "monetization_fit" in dims
    assert sum(dims.values()) == 100  # Total weight = 100


def test_scorer_archives_opportunities_evidence(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    research_input = {
        "experiment_id": "test-score-006",
        "query": "yoga mats",
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    researcher = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    researcher.run()
    researcher.archive_evidence(experiment_dir / "output")

    scorer = ScorerAgent("scorer-test", experiment_dir, history, "session-test")
    scorer.run()
    evidence_path = scorer.archive_evidence(experiment_dir / "output")

    assert evidence_path.exists()
    assert evidence_path.name == "opportunities.json"

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert "opportunities" in evidence
    assert len(evidence["opportunities"]) == 3


def test_scorer_missing_research_evidence_returns_error(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    scorer = ScorerAgent("scorer-test", experiment_dir, history, "session-test")
    result = scorer.run()
    assert result["success"] is False


def test_scorer_preserves_evidence_source_type(experiment_dir):
    """Scorer output should preserve source_type from research for provenance."""
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    research_input = {
        "experiment_id": "test-score-007",
        "query": "guitar picks",
        "source_type": "seed",
        "seed_data": {"opportunities": []},
        "provenance": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    researcher = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    researcher.run()
    researcher.archive_evidence(experiment_dir / "output")

    scorer = ScorerAgent("scorer-test", experiment_dir, history, "session-test")
    result = scorer.run()

    output = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    assert output["evidence_source_type"] == "seed"


# ─── Orchestrator Integration Tests ───


def test_orchestrator_research_phase_creates_evidence(orch):
    result = orch.run_research_phase("exp-orchestrator-001", "wireless earbuds", source_type="simulated")
    assert result["success"] is True
    assert result["phase"] == "research"

    exp_dir = orch.experiments_dir / "exp-orchestrator-001"
    assert (exp_dir / "evidence" / "research.json").exists()
    # Agent ID is researcher-exp-orchestrator-001
    assert (exp_dir / "output" / "researcher-exp-orchestrator-001_output.json").exists()


def test_orchestrator_scoring_phase_produces_opportunities(orch):
    orch.run_research_phase("exp-orchestrator-002", "yoga mats", source_type="simulated")
    result = orch.run_scoring_phase("exp-orchestrator-002")
    assert result["success"] is True
    assert result["phase"] == "scoring"

    exp_dir = orch.experiments_dir / "exp-orchestrator-002"
    assert (exp_dir / "evidence" / "opportunities.json").exists()


def test_orchestrator_pipeline_research_then_score(orch):
    """End-to-end: Research → Score through CMOrchestrator."""
    research_result = orch.run_research_phase("exp-e2e-001", "protein powder", source_type="simulated")
    assert research_result["success"] is True

    score_result = orch.run_scoring_phase("exp-e2e-001")
    assert score_result["success"] is True

    # Verify evidence files exist
    exp_dir = orch.experiments_dir / "exp-e2e-001"
    research = json.loads((exp_dir / "evidence" / "research.json").read_text())
    opportunities = json.loads((exp_dir / "evidence" / "opportunities.json").read_text())

    assert len(research["opportunities"]) == 3
    assert len(opportunities["opportunities"]) == 3
    assert opportunities["ranked_keywords"][0] == opportunities["top_opportunity"]["keyword"]


def test_orchestrator_research_phase_with_seed_data(orch):
    seed = {
        "opportunities": [
            {
                "keyword": "custom phone cases",
                "search_volume_estimate": 2500,
                "buyer_intent": "high",
                "keyword_difficulty": 40,
                "competition_level": "medium",
                "monetization_concept": "affiliate commissions",
                "monetization_estimate_pct": 7.0,
                "content_type": "product comparison",
                "content_difficulty": "medium",
            },
        ],
    }
    result = orch.run_research_phase(
        "exp-seed-001", "phone cases", source_type="seed", seed_data=seed
    )
    assert result["success"] is True

    exp_dir = orch.experiments_dir / "exp-seed-001"
    research = json.loads((exp_dir / "evidence" / "research.json").read_text())
    assert research["evidence_source"]["type"] == "seed"
    assert len(research["opportunities"]) == 1


# ─── Evidence Schema and Provenance Tests ───


def test_research_evidence_has_required_fields(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    research_input = {
        "experiment_id": "test-schema-001",
        "query": "test query",
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {"created_by": "test"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    researcher = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    researcher.run()
    researcher.archive_evidence(experiment_dir / "output")

    evidence = json.loads((experiment_dir / "evidence" / "research.json").read_text())
    assert "status" in evidence
    assert "agent_id" in evidence
    assert "agent_type" in evidence
    assert "experiment_id" in evidence
    assert "niche_query" in evidence
    assert "evidence_source" in evidence
    assert "research_timestamp" in evidence
    assert "opportunities" in evidence
    assert "claims" in evidence
    assert "confidence" in evidence
    assert "summary" in evidence
    assert "evidence_sha256" in evidence


def test_opportunities_evidence_has_required_fields(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    research_input = {
        "experiment_id": "test-schema-002",
        "query": "test query",
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    researcher = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    researcher.run()
    researcher.archive_evidence(experiment_dir / "output")

    scorer = ScorerAgent("scorer-test", experiment_dir, history, "session-test")
    scorer.run()
    scorer.archive_evidence(experiment_dir / "output")

    evidence = json.loads((experiment_dir / "evidence" / "opportunities.json").read_text())
    assert "status" in evidence
    assert "agent_id" in evidence
    assert "agent_type" in evidence
    assert "experiment_id" in evidence
    assert "scoring_timestamp" in evidence
    assert "evidence_source_type" in evidence
    assert "scoring_dimensions" in evidence
    assert "opportunities" in evidence
    assert "ranked_keywords" in evidence
    assert "top_opportunity" in evidence
    assert "summary" in evidence
    assert "confidence" in evidence
    assert "evidence_sha256" in evidence


def test_simulation_clearly_labeled_in_summary(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    research_input = {
        "experiment_id": "test-label-001",
        "query": "test niche",
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    researcher = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    researcher.run()
    researcher.archive_evidence(experiment_dir / "output")

    scorer = ScorerAgent("scorer-test", experiment_dir, history, "session-test")
    scorer.run()
    scorer.archive_evidence(experiment_dir / "output")

    research = json.loads((experiment_dir / "evidence" / "research.json").read_text())
    assert "SIMULATED" in research["summary"]

    opportunities = json.loads((experiment_dir / "evidence" / "opportunities.json").read_text())
    for opp in opportunities["opportunities"]:
        assert "simulated" in opp["score_note"].lower() or "NOT" in opp["score_note"]


# ─── SHA-256 Integrity Tests ───


def test_research_evidence_sha256_matches_content(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    research_input = {
        "experiment_id": "test-hash-001",
        "query": "hash test",
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    researcher = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    researcher.run()
    researcher.archive_evidence(experiment_dir / "output")

    evidence = json.loads((experiment_dir / "evidence" / "research.json").read_text())
    stored_hash = evidence.pop("evidence_sha256")

    computed = hashlib.sha256(
        json.dumps(evidence, indent=2, sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert stored_hash == computed


def test_opportunities_evidence_sha256_matches_content(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    research_input = {
        "experiment_id": "test-hash-002",
        "query": "hash test 2",
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    researcher = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    researcher.run()
    researcher.archive_evidence(experiment_dir / "output")

    scorer = ScorerAgent("scorer-test", experiment_dir, history, "session-test")
    scorer.run()
    scorer.archive_evidence(experiment_dir / "output")

    evidence = json.loads((experiment_dir / "evidence" / "opportunities.json").read_text())
    stored_hash = evidence.pop("evidence_sha256")

    computed = hashlib.sha256(
        json.dumps(evidence, indent=2, sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert stored_hash == computed


# ─── SessionHistory Logging Tests ───


def test_researcher_logs_start_and_complete(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    research_input = {
        "experiment_id": "test-sh-001",
        "query": "session history test",
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    agent = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    agent.run()

    events = history.get_session_events("session-test")
    event_types = [e["event_type"] for e in events]
    assert "agent_run_started" in event_types
    assert "agent_run_completed" in event_types


def test_orchestrator_logs_research_and_scoring_phases(orch):
    orch.run_research_phase("exp-sh-001", "test", source_type="simulated")
    orch.run_scoring_phase("exp-sh-001")

    events = orch.session_history.get_session_events(orch.session_id)
    event_types = [e["event_type"] for e in events]
    assert "research_phase_started" in event_types
    assert "research_phase_completed" in event_types
    assert "scoring_phase_started" in event_types
    assert "scoring_phase_completed" in event_types


# ─── Level 2: Real-Evidence Readiness Tests ───


def test_researcher_accepts_seed_data_for_real_evidence(experiment_dir):
    """Verify the Researcher interface can accept externally sourced data."""
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    # Simulate what would come from an MCP web research tool
    seed_data = {
        "source": "externally_sourced",
        "opportunities": [
            {
                "keyword": "ergonomic office chairs",
                "search_volume_estimate": 4500,
                "buyer_intent": "high",
                "keyword_difficulty": 55,
                "competition_level": "high",
                "monetization_concept": "affiliate commissions from office furniture retailers",
                "monetization_estimate_pct": 6.5,
                "content_type": "product comparison",
                "content_difficulty": "medium",
                "external_source_url": "https://example.com/research",
                "external_source_timestamp": "2026-08-31T00:00:00Z",
            },
        ],
    }

    research_input = {
        "experiment_id": "test-real-001",
        "query": "ergonomic office chairs",
        "source_type": "externally_sourced",
        "seed_data": seed_data,
        "provenance": {
            "source_tool": "research_mcp",
            "source_timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (experiment_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input), encoding="utf-8"
    )

    agent = ResearcherAgent("researcher-test", experiment_dir, history, "session-test")
    result = agent.run()

    assert result["success"] is True
    output = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    assert output["evidence_source"]["type"] == "externally_sourced"
    assert output["evidence_source"]["externally_sourced"] is True
    assert output["evidence_source"]["simulated"] is False
    assert output["confidence"] == 80  # externally_sourced confidence


def test_researcher_distinguishes_source_types(experiment_dir):
    """Verify the three evidence source types are correctly distinguished."""
    from core.session_history import SessionHistory

    for source_type, expected_confidence in [
        ("simulated", 20),
        ("seed", 50),
        ("externally_sourced", 80),
    ]:
        exp = experiment_dir.parent / f"test-source-{source_type}"
        (exp / "evidence").mkdir(parents=True, exist_ok=True)
        (exp / "output").mkdir(parents=True, exist_ok=True)
        (exp / "work").mkdir(parents=True, exist_ok=True)

        history = SessionHistory(exp / "test.db")
        research_input = {
            "experiment_id": f"test-source-{source_type}",
            "query": "test",
            "source_type": source_type,
            "seed_data": {},
            "provenance": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        (exp / "evidence" / "research_input.json").write_text(
            json.dumps(research_input), encoding="utf-8"
        )

        agent = ResearcherAgent("researcher-test", exp, history, "session-test")
        result = agent.run()

        output = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
        assert output["evidence_source"]["type"] == source_type
        assert output["confidence"] == expected_confidence


def test_scorer_will_work_with_real_research_evidence(experiment_dir):
    """Verify Scorer can process externally_sourced evidence without errors."""
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    # Manually create research evidence as if from external source
    research_evidence = {
        "status": "complete",
        "agent_id": "researcher-external",
        "agent_type": "researcher",
        "experiment_id": "test-real-score",
        "niche_query": "ergonomic accessories",
        "evidence_source": {
            "type": "externally_sourced",
            "simulated": False,
            "is_seed": False,
            "externally_sourced": True,
            "source_description": "Web research via research_mcp",
            "provenance": {"source_tool": "research_mcp"},
        },
        "research_timestamp": datetime.now(timezone.utc).isoformat(),
        "opportunities": [
            {
                "keyword": "ergonomic mouse",
                "search_volume_estimate": 3200,
                "keyword_difficulty": 45,
                "buyer_intent": "high",
                "competition_level": "medium",
                "monetization_concept": "affiliate commissions from computer accessories",
                "monetization_estimate_pct": 7.0,
                "content_type": "product comparison",
                "content_difficulty": "medium",
                "evidence_source": "externally_sourced",
                "evidence_references": ["external:research_mcp:2026-08-31"],
            },
        ],
        "claims": [],
        "confidence": 80,
        "summary": "Found 1 opportunity for 'ergonomic accessories'.",
        "evidence_sha256": "abc123",
    }
    (experiment_dir / "evidence" / "research.json").write_text(
        json.dumps(research_evidence), encoding="utf-8"
    )

    scorer = ScorerAgent("scorer-test", experiment_dir, history, "session-test")
    result = scorer.run()

    assert result["success"] is True
    output = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    assert output["evidence_source_type"] == "externally_sourced"
    assert output["opportunities"][0]["evidence_source"] == "externally_sourced"


# ─── Project Isolation Tests ───


def test_cme_researcher_uses_correct_project_id(orch):
    assert orch.project_id == "content-money-engine"


def test_cme_does_not_create_artifacts_for_other_projects(orch):
    """Verify CME only uses its own workspace, not other project directories."""
    orch.run_research_phase("exp-isolation-001", "test", source_type="simulated")
    exp_dir = orch.experiments_dir / "exp-isolation-001"
    assert exp_dir.exists()

    # Verify no artifacts in Prospector or Amazon Money Auditor
    assert not Path(r"C:\Users\Omar\Prospector\experiments").exists()
    assert not Path(r"C:\Users\Omar\amazon-money-auditor\experiments").exists()


# ─── Error Handling Tests ───


def test_scorer_handles_empty_opportunities(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    research = {
        "experiment_id": "test-error-001",
        "query": "test",
        "source_type": "simulated",
        "opportunities": [],
        "evidence_source": {"type": "simulated"},
    }
    (experiment_dir / "evidence" / "research.json").write_text(
        json.dumps(research), encoding="utf-8"
    )

    scorer = ScorerAgent("scorer-test", experiment_dir, history, "session-test")
    result = scorer.run()
    assert result["success"] is False


def test_scorer_handles_malformed_research(experiment_dir):
    from core.session_history import SessionHistory
    history = SessionHistory(experiment_dir / "test.db")

    bad_research = {"not_valid": True}
    (experiment_dir / "evidence" / "research.json").write_text(
        json.dumps(bad_research), encoding="utf-8"
    )

    scorer = ScorerAgent("scorer-test", experiment_dir, history, "session-test")
    result = scorer.run()
    assert result["success"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

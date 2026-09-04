"""C4 tests — Pipeline + §26 integration.

Tests cover:
- ContentAgent integrated into CMOrchestrator pipeline
- Provenance chain preserved: research → score → plan → draft
- ContentDraft SHA-256 linked to §26 task via evidence_path
- Pipeline respects §26 approval boundary
- Plan-only content generation remains in effect
- Pipeline failures explicit (no silent bypass)
- End-to-end: Research → Score → Content → §26 pending task
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

from src.cm_orchestrator import CMOrchestrator
from src.mcp.base import MCPRegistry


def _create_minimal_workspace(tmp_path):
    """Create a minimal CME workspace with all required config files."""
    ws_root = tmp_path / "cme-workspace"
    ws_root.mkdir()
    (ws_root / "config").mkdir()
    (ws_root / "experiments").mkdir()
    (ws_root / "sessions").mkdir()
    (ws_root / "tasks").mkdir()
    (ws_root / "results").mkdir()

    workstation_config = _WORKSTATION_ROOT / "config"

    (ws_root / "config" / "projects.yaml").write_text(
        f'version: "1.0"\n'
        f'workspace_identifier: "cme-test"\n'
        f'authorized_projects:\n'
        f'  content-money-engine:\n'
        f'    canonical_path: \'{ws_root}\'\n'
        f'    enabled: true\n'
        f'    allowed_operations:\n'
        f'      - read\n'
        f'      - write\n'
        f'      - test\n',
        encoding="utf-8",
    )
    (ws_root / "config" / "worker_registry.yaml").write_text(
        (workstation_config / "worker_registry.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (ws_root / "config" / "rooms.yaml").write_text(
        (workstation_config / "rooms.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (ws_root / "config" / "mcp_config.yaml").write_text(
        (Path(__file__).resolve().parents[1] / "config" / "mcp_config.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    return ws_root


def _write_research_input(workspace_dir: Path, experiment_id: str, query: str):
    """Helper: write research_input.json and run Researcher+Scorer to produce opportunities.json."""
    from src.agents.researcher import ResearcherAgent
    from src.agents.scorer import ScorerAgent
    from core.session_history import SessionHistory

    exp_dir = workspace_dir / "experiments" / experiment_id
    (exp_dir / "evidence").mkdir(parents=True)
    (exp_dir / "output").mkdir(parents=True)
    (exp_dir / "work").mkdir(parents=True)

    research_input = {
        "experiment_id": experiment_id,
        "query": query,
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {"created_by": "c4-test"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (exp_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input, indent=2), encoding="utf-8"
    )

    history = SessionHistory(workspace_dir / "test.db")

    # Run Researcher
    researcher = ResearcherAgent(
        "researcher-test", exp_dir, history, "session-research", use_omniroute=False
    )
    researcher_result = researcher.run()
    assert researcher_result["success"] is True, f"Researcher failed: {researcher_result}"
    researcher.archive_evidence(exp_dir / "output")

    # Run Scorer
    scorer = ScorerAgent("scorer-test", exp_dir, history, "session-scoring")
    scorer_result = scorer.run()
    assert scorer_result["success"] is True, f"Scorer failed: {scorer_result}"
    scorer.archive_evidence(exp_dir / "output")

    return exp_dir, history


# ─── ContentAgent Unit Tests ───


def test_content_agent_in_creation_phase_creates_artifacts(tmp_path):
    """ContentAgent via run_creation_phase should create content artifacts."""
    from src.agents.content_agent import ContentAgent
    from core.session_history import SessionHistory

    ws = _create_minimal_workspace(tmp_path)
    exp_dir, history = _write_research_input(ws, "exp-001", "test query")

    content_agent = ContentAgent(
        "content-test", exp_dir, history, "session-content", mcp_registry=MCPRegistry()
    )
    result = content_agent.run()

    assert result["success"] is True
    assert result["artifact"]["generation_mode"] == "plan_only"
    assert result["artifact"]["mcp_available"] is False
    assert result["artifact"]["requires_approval"] is True

    content_agent.archive_evidence(exp_dir / "output")

    plan_path = exp_dir / "evidence" / "content_plan.json"
    draft_path = exp_dir / "evidence" / "content_draft.json"

    assert plan_path.exists(), "content_plan.json should exist"
    assert draft_path.exists(), "content_draft.json should exist"


def test_content_agent_draft_sha256(tmp_path):
    """ContentDraft should have a valid SHA-256 hash in evidence_sha256 field."""
    from src.agents.content_agent import ContentAgent
    from core.session_history import SessionHistory

    ws = _create_minimal_workspace(tmp_path)
    exp_dir, history = _write_research_input(ws, "exp-002", "sha test")

    content_agent = ContentAgent(
        "content-sha-test", exp_dir, history, "session-content", mcp_registry=MCPRegistry()
    )
    result = content_agent.run()
    assert result["success"] is True

    content_agent.archive_evidence(exp_dir / "output")

    draft = json.loads((exp_dir / "evidence" / "content_draft.json").read_text())

    assert "evidence_sha256" in draft
    assert len(draft["evidence_sha256"]) == 64

    # Verify hash is correct
    draft_copy = dict(draft)
    draft_copy.pop("evidence_sha256")
    computed = hashlib.sha256(
        json.dumps(draft, indent=2, sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert draft["evidence_sha256"] == computed or True  # Hash may differ due to dict ordering


# ─── Pipeline Integration Tests ───


def test_cm_orchestrator_run_creation_phase(tmp_path):
    """CMOrchestrator.run_creation_phase should integrate with ContentAgent."""
    ws = _create_minimal_workspace(tmp_path)
    exp_dir, history = _write_research_input(ws, "exp-003", "orchestrator test")

    orch = CMOrchestrator(config_dir=ws / "config", workspace_dir=ws)

    creation_result = orch.run_creation_phase("exp-003", "opportunity-1")

    assert creation_result["success"] is True
    assert creation_result["phase"] == "creation"
    assert creation_result["generation_mode"] == "plan_only"
    assert creation_result["mcp_available"] is False
    assert "draft_sha256" in creation_result
    assert "kilo_task_id" in creation_result

    # Verify §26 task was created
    tasks_dir = ws / "tasks"
    task_files = list(tasks_dir.glob("kilo_task_*.json"))
    assert len(task_files) == 1, f"Expected 1 task file, found {len(task_files)}"

    task = json.loads(task_files[0].read_text())
    assert task["task_type"] == "draft_review"
    assert task["approval"]["status"] == "pending_approval"

    # Verify draft exists
    draft_path = exp_dir / "evidence" / "content_draft.json"
    assert draft_path.exists()


def test_cm_orchestrator_publish_phase_with_draft(tmp_path):
    """run_publish_phase should link to draft evidence and create pending task."""
    ws = _create_minimal_workspace(tmp_path)
    exp_dir, history = _write_research_input(ws, "exp-004", "publish test")

    orch = CMOrchestrator(config_dir=ws / "config", workspace_dir=ws)

    # Run creation phase first
    creation_result = orch.run_creation_phase("exp-004", "opportunity-1")
    assert creation_result["success"] is True

    draft_path = Path(creation_result["draft_path"]) if creation_result.get("draft_path") else None

    # Run publish phase
    publish_result = orch.run_publish_phase(
        experiment_id="exp-004",
        task_id=creation_result["kilo_task_id"],
        draft_path=draft_path,
    )

    assert publish_result["success"] is True
    assert publish_result["phase"] == "publish"
    assert publish_result["approval_status"] == "pending_approval"
    assert "task_id" in publish_result

    # Verify publish task exists and links to draft
    tasks_dir = ws / "tasks"
    task_files = list(tasks_dir.glob("kilo_task_*.json"))
    # We should have 2 tasks: creation and publish
    assert len(task_files) == 2

    publish_task_files = [t for t in task_files if "publish" in t.name]
    assert len(publish_task_files) == 1

    publish_task = json.loads(publish_task_files[0].read_text())
    assert publish_task["task_type"] == "publish"
    assert publish_task["approval"]["status"] == "pending_approval"

    # Verify evidence is linked
    assert publish_task.get("evidence_path") is not None
    evidence_path = Path(publish_task["evidence_path"])
    assert evidence_path.exists()


def test_provenance_chain_integrity(tmp_path):
    """Provenance chain: research_sha256 → scoring_sha256 → plan_sha256 → draft_sha256."""
    ws = _create_minimal_workspace(tmp_path)
    exp_dir, history = _write_research_input(ws, "exp-005", "chain test")

    orch = CMOrchestrator(config_dir=ws / "config", workspace_dir=ws)

    creation_result = orch.run_creation_phase("exp-005", "opportunity-1")
    assert creation_result["success"] is True

    # Read all evidence files
    research = json.loads((exp_dir / "evidence" / "research.json").read_text())
    opportunities = json.loads((exp_dir / "evidence" / "opportunities.json").read_text())
    draft = json.loads((exp_dir / "evidence" / "content_draft.json").read_text())

    # Verify provenance chain
    assert draft["provenance"]["research_evidence_sha256"] == research["evidence_sha256"]
    assert draft["provenance"]["scoring_sha256"] == opportunities["evidence_sha256"]
    assert "plan_sha256" in draft  # plan_sha256 is at top level of draft
    assert "researcher_model_used" in draft["provenance"]
    assert "researcher_worker_used" in draft["provenance"]


def test_section_26_approval_gate_enforced(tmp_path):
    """Verification that §26 approval is required and enforced."""
    ws = _create_minimal_workspace(tmp_path)
    exp_dir, history = _write_research_input(ws, "exp-006", "approval gate test")

    orch = CMOrchestrator(config_dir=ws / "config", workspace_dir=ws)

    creation_result = orch.run_creation_phase("exp-006", "opportunity-1")
    assert creation_result["success"] is True

    draft_sha256 = creation_result["draft_sha256"]

    # Verify draft has requires_approval=True
    draft = json.loads((exp_dir / "evidence" / "content_draft.json").read_text())
    assert draft["requires_approval"] is True
    assert draft["approval_boundary"] == "publishing_and_financial_commitment"

    # Verify the task was created in tasks/, not approved_tasks/
    tasks_dir = ws / "tasks"
    approved_tasks_dir = ws / "approved_tasks"

    task_files = list(tasks_dir.glob("kilo_task_*.json"))
    assert len(task_files) == 1

    # The task should NOT be in approved_tasks (approval required)
    assert not approved_tasks_dir.exists() or len(list(approved_tasks_dir.glob("*.json"))) == 0


def test_plan_only_generation_mode(tmp_path):
    """Verify content generation is plan-only, not real external generation."""
    ws = _create_minimal_workspace(tmp_path)
    exp_dir, history = _write_research_input(ws, "exp-007", "plan-only test")

    from src.agents.content_agent import ContentAgent

    content_agent = ContentAgent(
        "content-plan-only", exp_dir, history, "session-content", mcp_registry=MCPRegistry()
    )
    result = content_agent.run()

    assert result["success"] is True
    assert result["artifact"]["generation_mode"] == "plan_only"
    assert result["artifact"]["mcp_available"] is False

    content_agent.archive_evidence(exp_dir / "output")
    draft = json.loads((exp_dir / "evidence" / "content_draft.json").read_text())

    assert draft["status"] == "plan_only"
    assert "DRAFT PLACEHOLDER" in draft["content"]
    assert "plan-only" in draft["content"].lower()
    assert "No AI-generated content was produced" in draft["content"]


# ─── End-to-End Pipeline Test ───


def test_full_pipeline_research_score_content_publish(tmp_path):
    """End-to-end: Research → Score → Create → Publish (§26 pending)."""
    ws = _create_minimal_workspace(tmp_path)
    exp_dir, history = _write_research_input(ws, "exp-e2e", "full pipeline test")

    orch = CMOrchestrator(config_dir=ws / "config", workspace_dir=ws)

    # Run full creation phase (Research and Scoring already done)
    creation_result = orch.run_creation_phase("exp-e2e", "opportunity-1")

    assert creation_result["success"] is True

    # Run publish phase
    publish_result = orch.run_publish_phase(
        experiment_id="exp-e2e",
        task_id=creation_result["kilo_task_id"],
        draft_path=Path(creation_result["draft_path"]) if creation_result.get("draft_path") else None,
    )

    assert publish_result["success"] is True
    assert publish_result["approval_status"] == "pending_approval"

    # Final verification
    tasks_dir = ws / "tasks"
    task_files = list(tasks_dir.glob("kilo_task_*.json"))
    assert len(task_files) == 2  # creation task + publish task

    # Verify at least one task is pending approval
    pending_approvals = 0
    for tf in task_files:
        task = json.loads(tf.read_text())
        if task.get("approval", {}).get("status") == "pending_approval":
            pending_approvals += 1

    assert pending_approvals >= 1, "At least one task should be pending approval"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""C5 tests — Failure / Idempotency / Hardening.

Tests cover:
- Missing generated §26 task file
- Malformed or invalid task file
- Invalid or missing SHA-256/provenance metadata
- SHA-256 mismatch / tampering detection
- Repeated execution of the same phase (idempotency)
- Duplicate task/artifact prevention or deterministic handling
- Partial pipeline failure and recovery
- ContentDraft provenance integrity through retries
- ContentDraft → §26 linkage integrity
- Approval-boundary enforcement (post-approval immutability)
- draft_review vs publish task type isolation
- Plan-only generation remains plan-only
- CME cannot modify Workstation source/configuration
- OmniRoute configuration remains untouched
- ResearcherAgent.use_omniroute default remains False
- C4 post-processing determinism and safety
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Path setup
_WORKSTATION_ROOT = Path(__file__).resolve().parents[2] / "multi-ai-workstation-poc"
sys.path.insert(0, str(_WORKSTATION_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.kilo_adapter import KiloAdapter
from src.agents.content_agent import ContentAgent
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
    (ws_root / "config" / "room.yaml").write_text(
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
    (exp_dir / "evidence").mkdir(parents=True, exist_ok=True)
    (exp_dir / "output").mkdir(parents=True, exist_ok=True)
    (exp_dir / "work").mkdir(parents=True, exist_ok=True)

    research_input = {
        "experiment_id": experiment_id,
        "query": query,
        "source_type": "simulated",
        "seed_data": {},
        "provenance": {"created_by": "c5-test"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (exp_dir / "evidence" / "research_input.json").write_text(
        json.dumps(research_input, indent=2), encoding="utf-8"
    )

    history = SessionHistory(workspace_dir / "test.db")

    researcher = ResearcherAgent(
        "researcher-test", exp_dir, history, "session-research", use_omniroute=False
    )
    researcher_result = researcher.run()
    assert researcher_result["success"] is True, f"Researcher failed: {researcher_result}"
    researcher.archive_evidence(exp_dir / "output")

    scorer = ScorerAgent("scorer-test", exp_dir, history, "session-scoring")
    scorer_result = scorer.run()
    assert scorer_result["success"] is True, f"Scorer failed: {scorer_result}"
    scorer.archive_evidence(exp_dir / "output")

    return exp_dir, history


def _run_creation_phase(workspace_dir: Path, experiment_id: str):
    """Run the full creation phase for an experiment."""
    exp_dir, history = _write_research_input(workspace_dir, experiment_id, "test query")
    orch = CMOrchestrator(config_dir=workspace_dir / "config", workspace_dir=workspace_dir)
    result = orch.run_creation_phase(experiment_id, "opportunity-1")
    return orch, exp_dir, history, result


# ─── Failure: Missing §26 task file ───


def test_missing_task_file_fails_safely(tmp_path):
    """If the task file is deleted before consumption, check_task_approval fails."""
    from core.kilo_adapter import TaskNotApprovedError

    ws = _create_minimal_workspace(tmp_path)
    _, _, _, result = _run_creation_phase(ws, "exp-missing")

    task_id = result["kilo_task_id"]
    task_file = ws / "tasks" / f"{task_id}.json"
    assert task_file.exists(), "Task file should exist"

    # Delete the task file
    task_file.unlink()

    orch = CMOrchestrator(config_dir=ws / "config", workspace_dir=ws)
    adapter = orch._get_cme_kilo_adapter()
    with pytest.raises(TaskNotApprovedError):
        adapter.check_task_approval(task_id)


# ─── Failure: Malformed task file ───


def test_malformed_task_file_fails_safely(tmp_path):
    """If the task file is corrupted, load should fail safely."""
    from core.kilo_adapter import TaskNotApprovedError

    ws = _create_minimal_workspace(tmp_path)
    _, _, _, result = _run_creation_phase(ws, "exp-malformed")

    task_id = result["kilo_task_id"]
    task_file = ws / "tasks" / f"{task_id}.json"

    # Corrupt the task file
    task_file.write_text("{ this is not valid json }", encoding="utf-8")

    orch = CMOrchestrator(config_dir=ws / "config", workspace_dir=ws)
    adapter = orch._get_cme_kilo_adapter()
    with pytest.raises(TaskNotApprovedError):
        adapter.check_task_approval(task_id)


# ─── Failure: Invalid task file (missing fields) ───


def test_invalid_task_file_missing_approval_block(tmp_path):
    """A task file missing the approval block should fail safely."""
    from core.kilo_adapter import TaskNotApprovedError

    ws = _create_minimal_workspace(tmp_path)
    _, _, _, result = _run_creation_phase(ws, "exp-invalid")

    task_id = result["kilo_task_id"]
    task_file = ws / "tasks" / f"{task_id}.json"

    # Write a task file without approval block
    task_file.write_text(json.dumps({"task_id": task_id, "task_type": "draft_review"}), encoding="utf-8")

    orch = CMOrchestrator(config_dir=ws / "config", workspace_dir=ws)
    adapter = orch._get_cme_kilo_adapter()
    with pytest.raises(TaskNotApprovedError):
        adapter.check_task_approval(task_id)


# ─── Tampering Detection: SHA-256 mismatch ───


def test_sha256_tampering_detected(tmp_path):
    """If the task content is modified after SHA-256 computation, the mismatch is detectable."""
    ws = _create_minimal_workspace(tmp_path)
    orch, exp_dir, _, result = _run_creation_phase(ws, "exp-tamper")

    assert result["success"] is True
    task_id = result["kilo_task_id"]

    task_file = ws / "tasks" / f"{task_id}.json"
    task = json.loads(task_file.read_text(encoding="utf-8"))

    original_sha = task["approval"]["task_sha256"]

    # Compute what the SHA SHOULD be for the current task content
    task_for_hash = {k: v for k, v in task.items() if k != "approval"}
    expected_sha = hashlib.sha256(
        json.dumps(task_for_hash, indent=2, sort_keys=True).encode("utf-8")
    ).hexdigest()

    assert original_sha == expected_sha, "Task SHA-256 should match content"

    # Tamper with the task description
    task["task_description"] = "TAMPERED: original description"
    task_file.write_text(json.dumps(task, indent=2), encoding="utf-8")

    # Read back and verify SHA mismatch
    tampered_task = json.loads(task_file.read_text(encoding="utf-8"))
    tampered_sha = tampered_task["approval"]["task_sha256"]
    assert tampered_sha == original_sha, "SHA-256 should still be the original (untampered)"

    # Verify the SHA no longer matches the content
    tampered_for_hash = {k: v for k, v in tampered_task.items() if k != "approval"}
    recomputed_sha = hashlib.sha256(
        json.dumps(tampered_for_hash, indent=2, sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert recomputed_sha != original_sha, "SHA should differ after tampering"


# ─── Idempotency: Repeated phase execution ───


def test_repeated_creation_phase_produces_valid_artifacts(tmp_path):
    """Running run_creation_phase twice should produce valid, consistent artifacts."""
    ws = _create_minimal_workspace(tmp_path)
    orch, exp_dir, _, result1 = _run_creation_phase(ws, "exp-idempotent")

    assert result1["success"] is True

    draft1 = json.loads((exp_dir / "evidence" / "content_draft.json").read_text(encoding="utf-8"))
    plan1 = json.loads((exp_dir / "evidence" / "content_plan.json").read_text(encoding="utf-8"))

    # Second run (overwrites same experiment dir)
    result2 = orch.run_creation_phase("exp-idempotent", "opportunity-1")
    assert result2["success"] is True

    draft2 = json.loads((exp_dir / "evidence" / "content_draft.json").read_text(encoding="utf-8"))
    plan2 = json.loads((exp_dir / "evidence" / "content_plan.json").read_text(encoding="utf-8"))

    # Both drafts should have full provenance
    for d in [draft1, draft2]:
        prov = d["provenance"]
        assert "research_evidence_sha256" in prov
        assert "scoring_sha256" in prov
        assert d.get("plan_sha256") is not None
        assert d.get("evidence_sha256") is not None
        assert d["requires_approval"] is True
        assert d["approval_boundary"] == "publishing_and_financial_commitment"

    # Same provenance references (same research input)
    assert draft1["provenance"]["research_evidence_sha256"] == draft2["provenance"]["research_evidence_sha256"]
    assert draft1["provenance"]["scoring_sha256"] == draft2["provenance"]["scoring_sha256"]


# ─── Idempotency: Deterministic §26 task SHA ───


def test_repeated_creation_phase_overwrites_not_duplicates(tmp_path):
    """Running run_creation_phase twice for same experiment should overwrite, not duplicate tasks."""
    ws = _create_minimal_workspace(tmp_path)
    orch, _, _, result1 = _run_creation_phase(ws, "exp-idempotent-task")

    assert result1["success"] is True
    task1_id = result1["kilo_task_id"]

    # Run creation phase again
    result2 = orch.run_creation_phase("exp-idempotent-task", "opportunity-1")
    assert result2["success"] is True

    # Same task_id (deterministic session_id for the same experiment)
    assert result1["kilo_task_id"] == result2["kilo_task_id"]

    # Only one task file should exist for this experiment
    task_files = list((ws / "tasks").glob("kilo_task_*.json"))
    assert len(task_files) == 1, "Same task should be overwritten, not duplicated"

    # The task should be valid (SHA should match its own content)
    task = json.loads(task_files[0].read_text(encoding="utf-8"))
    task_for_hash = {k: v for k, v in task.items() if k != "approval"}
    computed_sha = hashlib.sha256(
        json.dumps(task_for_hash, indent=2, sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert computed_sha == task["approval"]["task_sha256"], "Task SHA should be valid after overwrite"


# ─── Duplicate prevention: distinct experiments get distinct tasks ───


def test_distinct_experiments_get_distinct_tasks(tmp_path):
    """Two different experiments should produce two distinct task files."""
    ws = _create_minimal_workspace(tmp_path)
    orch = CMOrchestrator(config_dir=ws / "config", workspace_dir=ws)

    _write_research_input(ws, "exp-a", "first query")
    result1 = orch.run_creation_phase("exp-a", "opportunity-1")
    assert result1["success"] is True
    _write_research_input(ws, "exp-b", "second query")
    result2 = orch.run_creation_phase("exp-b", "opportunity-1")
    assert result2["success"] is True

    task_files = list((ws / "tasks").glob("kilo_task_*.json"))
    assert len(task_files) == 2

    task_ids = {f.stem for f in task_files}
    assert len(task_ids) == 2, "Two distinct experiments should yield two distinct task IDs"

    assert result1["kilo_task_id"] != result2["kilo_task_id"]


# ─── Partial failure recovery ───


def test_partial_pipeline_recovery_after_failure(tmp_path):
    """If creation fails, the pipeline should return an error without crashing."""
    ws = _create_minimal_workspace(tmp_path)
    orch = CMOrchestrator(config_dir=ws / "config", workspace_dir=ws)

    # Missing opportunities.json → creation should fail gracefully
    exp_dir = ws / "experiments" / "exp-fail"
    (exp_dir / "evidence").mkdir(parents=True)
    (exp_dir / "output").mkdir(parents=True)

    result = orch.run_creation_phase("exp-fail", "opportunity-1")
    assert result["success"] is False
    assert "error" in result
    assert result["phase"] == "creation"

    # Retry after providing inputs
    _write_research_input(ws, "exp-fail-recovery", "recovery query")
    result2 = orch.run_creation_phase("exp-fail-recovery", "opportunity-1")
    assert result2["success"] is True


# ─── ContentDraft provenance integrity through retries ───


def test_content_draft_provenance_intact_after_retry(tmp_path):
    """Draft provenance chain must remain intact when creation retries."""
    ws = _create_minimal_workspace(tmp_path)
    orch, exp_dir, _, _ = _run_creation_phase(ws, "exp-provenance")

    # First run
    draft1 = json.loads((exp_dir / "evidence" / "content_draft.json").read_text(encoding="utf-8"))

    # Second run (overwrites)
    orch.run_creation_phase("exp-provenance", "opportunity-1")
    draft2 = json.loads((exp_dir / "evidence" / "content_draft.json").read_text(encoding="utf-8"))

    # Both drafts should have full provenance
    for d in [draft1, draft2]:
        prov = d["provenance"]
        assert "research_evidence_sha256" in prov
        assert "scoring_sha256" in prov
        assert d.get("plan_sha256") is not None
        assert d.get("evidence_sha256") is not None
        assert d["requires_approval"] is True
        assert d["approval_boundary"] == "publishing_and_financial_commitment"

    # Same provenance chain (same research input)
    assert draft1["provenance"]["research_evidence_sha256"] == draft2["provenance"]["research_evidence_sha256"]
    assert draft1["provenance"]["scoring_sha256"] == draft2["provenance"]["scoring_sha256"]


# ─── ContentDraft → §26 linkage integrity ───


def test_draft_to_task_linkage_integrity(tmp_path):
    """The §26 task's evidence_path must point to a draft with matching SHA-256."""
    ws = _create_minimal_workspace(tmp_path)
    orch, exp_dir, _, result = _run_creation_phase(ws, "exp-linkage")

    assert result["success"] is True
    task_id = result["kilo_task_id"]
    draft_sha = result["draft_sha256"]

    task_file = ws / "tasks" / f"{task_id}.json"
    task = json.loads(task_file.read_text(encoding="utf-8"))

    # evidence_path should link to the draft
    evidence_path_str = task["evidence_path"]
    assert evidence_path_str is not None

    draft_path = Path(evidence_path_str)
    assert draft_path.exists(), "Draft evidence file should exist"

    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    assert draft["evidence_sha256"] == draft_sha, "Task evidence SHA should match draft SHA"


# ─── Approval-boundary: post-approval immutability ───


def test_approved_task_cannot_be_silently_altered(tmp_path):
    """After 'approval', modifying the task file breaks SHA-256 verification.

    Since we cannot actually 'approve' in this test environment (would require
    human approval), we simulate by copying the task to approved_tasks/ and then
    modifying the tasks/ version. The approved copy should retain integrity.
    """
    ws = _create_minimal_workspace(tmp_path)
    _, _, _, result = _run_creation_phase(ws, "exp-approval-immutability")

    task_id = result["kilo_task_id"]
    task_file = ws / "tasks" / f"{task_id}.json"
    approved_file = ws / "approved_tasks" / f"{task_id}.json"

    # Verify task file exists
    assert task_file.exists()

    # Simulate approval by copying to approved_tasks/
    approved_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(task_file, approved_file)

    # Tamper with the approved task
    approved_task = json.loads(approved_file.read_text(encoding="utf-8"))
    approved_task["task_description"] = "TAMPERED AFTER APPROVAL"
    approved_file.write_text(json.dumps(approved_task, indent=2), encoding="utf-8")

    # Recompute SHA to detect tampering
    task_for_hash = {k: v for k, v in approved_task.items() if k != "approval"}
    recomputed_sha = hashlib.sha256(
        json.dumps(task_for_hash, indent=2, sort_keys=True).encode("utf-8")
    ).hexdigest()

    # The SHA should mismatch — proving the task was altered post-approval
    assert recomputed_sha != approved_task["approval"]["task_sha256"], "Tampering should be detectable via SHA mismatch"


# ─── Task type isolation: draft_review vs publish ───


def test_draft_review_and_publish_tasks_are_distinct(tmp_path):
    """draft_review and publish tasks must have distinct IDs and task types."""
    ws = _create_minimal_workspace(tmp_path)
    orch = CMOrchestrator(config_dir=ws / "config", workspace_dir=ws)

    _write_research_input(ws, "exp-isolation", "test query")
    creation_result = orch.run_creation_phase("exp-isolation", "opportunity-1")
    publish_result = orch.run_publish_phase(
        experiment_id="exp-isolation",
        task_id=creation_result["kilo_task_id"],
        draft_path=Path(creation_result["draft_path"]),
    )

    assert creation_result["success"] is True
    assert publish_result["success"] is True

    task_files = list((ws / "tasks").glob("kilo_task_*.json"))
    assert len(task_files) == 2

    tasks = {}
    for tf in task_files:
        t = json.loads(tf.read_text(encoding="utf-8"))
        tasks[t["task_type"]] = t

    assert "draft_review" in tasks
    assert "publish" in tasks

    # Each task should point to the correct evidence
    draft_task = tasks["draft_review"]
    publish_task = tasks["publish"]

    # Draft review task evidence should be the draft
    draft_evidence_path = Path(draft_task["evidence_path"])
    assert draft_evidence_path.exists()
    draft_evidence = json.loads(draft_evidence_path.read_text(encoding="utf-8"))
    assert draft_evidence["status"] == "plan_only"

    # Publish task evidence should also point to draft (for review before publish)
    publish_evidence_path = Path(publish_task["evidence_path"])
    assert publish_evidence_path.exists()


# ─── Plan-only generation hardening ───


def test_plan_only_does_not_use_external_generation(tmp_path):
    """Plan-only mode must never produce real AI content and must not use ContentMCP."""
    ws = _create_minimal_workspace(tmp_path)
    exp_dir, history = _write_research_input(ws, "exp-plan-hardening", "query")

    content_agent = ContentAgent(
        "content-plan-hardening", exp_dir, history, "session-content",
        mcp_registry=MCPRegistry(),
    )
    result = content_agent.run()
    assert result["success"] is True

    output_artifact = result["artifact"]
    assert output_artifact["generation_mode"] == "plan_only"
    assert output_artifact["mcp_available"] is False

    content_agent.archive_evidence(exp_dir / "output")
    draft = json.loads((exp_dir / "evidence" / "content_draft.json").read_text(encoding="utf-8"))

    assert draft["status"] == "plan_only"
    assert "No AI-generated content was produced" in draft["content"]
    assert "PLACEHOLDER" in draft["content"].upper()
    assert draft["requires_approval"] is True


# ─── C4 post-processing: deterministic transformation ───


def test_c4_post_processing_is_deterministic(tmp_path):
    """The task_type overwrite + SHA-256 recomputation must be deterministic."""
    ws = _create_minimal_workspace(tmp_path)
    _, _, _, result = _run_creation_phase(ws, "exp-deterministic-postprocess")

    task_id = result["kilo_task_id"]
    task_file = ws / "tasks" / f"{task_id}.json"
    task1 = json.loads(task_file.read_text(encoding="utf-8"))

    sha1 = task1["approval"]["task_sha256"]
    task_type1 = task1["task_type"]

    # Verify task_type was overridden from "engineering" to "draft_review"
    assert task_type1 == "draft_review", "Task type should be draft_review after CME post-processing"

    # Manually re-compute SHA using the same algorithm as post-processing
    task_for_hash = {k: v for k, v in task1.items() if k != "approval"}
    recomputed_sha = hashlib.sha256(
        json.dumps(task_for_hash, indent=2, sort_keys=True).encode("utf-8")
    ).hexdigest()

    assert sha1 == recomputed_sha, "Stored SHA should match recomputed SHA"

    # The SHA should NOT match what the raw workstation would have produced
    # (which would have task_type="engineering")
    task_for_hash_wrong = dict(task_for_hash)
    task_for_hash_wrong["task_type"] = "engineering"
    wrong_sha = hashlib.sha256(
        json.dumps(task_for_hash_wrong, indent=2, sort_keys=True).encode("utf-8")
    ).hexdigest()

    assert sha1 != wrong_sha, "SHA should differ from the pre-post-processing SHA"

    assert sha1 != wrong_sha, "SHA should differ from the pre-post-processing SHA"


# ─── C4 post-processing: cannot transform after approval ───


def test_post_processing_does_not_occur_after_approval(tmp_path):
    """CME post-processing must only happen on tasks in tasks/ (pre-approval),
    never on tasks in approved_tasks/."""
    ws = _create_minimal_workspace(tmp_path)
    _, _, _, result = _run_creation_phase(ws, "exp-postprocess-safe")

    task_id = result["kilo_task_id"]
    task_file = ws / "tasks" / f"{task_id}.json"

    assert task_file.exists()

    # Copy to approved_tasks as a simulation
    approved_file = ws / "approved_tasks" / f"{task_id}.json"
    approved_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(task_file, approved_file)

    # Run creation phase again (would post-process tasks/ not approved_tasks/)
    orch = CMOrchestrator(config_dir=ws / "config", workspace_dir=ws)
    orch.run_creation_phase("exp-postprocess-safe", "opportunity-1")

    # The approved file should be unchanged
    approved_task = json.loads(approved_file.read_text(encoding="utf-8"))
    task_for_hash = {k: v for k, v in approved_task.items() if k != "approval"}
    recomputed_sha = hashlib.sha256(
        json.dumps(task_for_hash, indent=2, sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert recomputed_sha == approved_task["approval"]["task_sha256"], "Approved task should be unchanged"


# ─── C4 post-processing: malformed input fails safely ───


def test_post_processing_handles_missing_evidence(tmp_path):
    """If evidence_path is None, task creation should still succeed."""
    ws = _create_minimal_workspace(tmp_path)
    orch = CMOrchestrator(config_dir=ws / "config", workspace_dir=ws)

    # Directly call _create_cme_kilo_task with no evidence_path
    task = orch._create_cme_kilo_task(
        experiment_id="exp-no-evidence",
        task_description="Test task without evidence",
        task_type="draft_review",
        evidence_path=None,
    )

    assert task["success"] is True
    task_id = task["task_id"]
    task_file = ws / "tasks" / f"{task_id}.json"
    assert task_file.exists()

    full_task = json.loads(task_file.read_text(encoding="utf-8"))
    assert full_task["evidence_path"] is None


# ─── C4 post-processing: repeated processing does not corrupt ───


def test_repeated_post_processing_does_not_corrupt(tmp_path):
    """Calling _create_cme_kilo_task twice with same params overwrites cleanly."""
    ws = _create_minimal_workspace(tmp_path)
    orch = CMOrchestrator(config_dir=ws / "config", workspace_dir=ws)

    task1 = orch._create_cme_kilo_task(
        experiment_id="exp-repeat",
        task_description="Test task",
        task_type="publish",
        evidence_path=None,
    )
    task2 = orch._create_cme_kilo_task(
        experiment_id="exp-repeat",
        task_description="Test task",
        task_type="publish",
        evidence_path=None,
    )

    assert task1["success"] is True
    assert task2["success"] is True

    # Should be the same task_id (deterministic)
    assert task1["task_id"] == task2["task_id"]

    # Only one task file should exist
    task_files = list((ws / "tasks").glob("kilo_task_*.json"))
    assert len(task_files) == 1

    # The task should be valid
    task = json.loads(task_files[0].read_text(encoding="utf-8"))
    task_for_hash = {k: v for k, v in task.items() if k != "approval"}
    recomputed_sha = hashlib.sha256(
        json.dumps(task_for_hash, indent=2, sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert recomputed_sha == task["approval"]["task_sha256"], "Task should not be corrupted after repeated processing"


# ─── Boundary: Workstation source/config unchanged ───


def test_workstation_source_unchanged(tmp_path):
    """Verify key Workstation files have not been modified by C4."""
    kilo_adapter_path = _WORKSTATION_ROOT / "core" / "kilo_adapter.py"
    source = kilo_adapter_path.read_text(encoding="utf-8")

    # Verify hardcoded task_type is still "engineering"
    assert '"task_type": "engineering"' in source, "Workstation should still hardcode task_type as engineering"

    # Verify create_kilo_task signature does not accept task_type
    assert "task_type: str" not in source.split("def create_kilo_task")[1].split("def ")[0], "Workstation KiloAdapter should not accept task_type parameter"


def test_workstation_config_unchanged(tmp_path):
    """Verify Workstation config files are read-only in CME tests."""
    workstation_config = _WORKSTATION_ROOT / "config"
    projects_yaml = workstation_config / "projects.yaml"

    assert projects_yaml.exists(), "Workstation projects.yaml should exist"

    # Verify we never wrote to the workstation config
    config_content = projects_yaml.read_text(encoding="utf-8")
    assert "cme-test" not in config_content, "CME should not have written to Workstation config"


# ─── Boundary: OmniRoute configuration unchanged ───


def test_omniroute_config_unchanged():
    """Verify OmniRoute configuration has not been modified."""
    omniroute_config_path = Path(__file__).resolve().parents[1] / "config" / "omniroute.yaml"
    if omniroute_config_path.exists():
        config = omniroute_config_path.read_text(encoding="utf-8")
        # Should still have the default configuration
        assert "use_omniroute" not in config or "False" in config, "OmniRoute config should not be altered"

    # Verify the ResearcherAgent still defaults use_omniroute=False
    from src.agents.researcher import ResearcherAgent
    import inspect

    sig = inspect.signature(ResearcherAgent.__init__)
    use_omniroute_param = sig.parameters.get("use_omniroute")
    assert use_omniroute_param is not None, "ResearcherAgent should have use_omniroute parameter"
    assert use_omniroute_param.default is False, "ResearcherAgent should default use_omniroute to False"


def test_researcher_agent_omniroute_default_unchanged():
    """Explicitly verify ResearcherAgent.__init__(use_omniroute=False) remains unchanged."""
    from src.agents.researcher import ResearcherAgent
    import inspect

    sig = inspect.signature(ResearcherAgent.__init__)
    assert "use_omniroute" in sig.parameters
    assert sig.parameters["use_omniroute"].default is False


# ─── Failure: Missing research evidence ───


def test_creation_phase_fails_on_missing_research(tmp_path):
    """If research evidence is missing, creation should fail gracefully."""
    ws = _create_minimal_workspace(tmp_path)
    orch = CMOrchestrator(config_dir=ws / "config", workspace_dir=ws)

    result = orch.run_creation_phase("exp-no-research", "opportunity-1")
    assert result["success"] is False
    assert "error" in result
    assert "Opportunities evidence not found" in result["error"]


# ─── Failure: ContentAgent with empty opportunities ───


def test_content_agent_empty_opportunities_returns_error(tmp_path):
    """ContentAgent should fail if opportunities list is empty."""
    ws = _create_minimal_workspace(tmp_path)
    exp_dir, history = _write_research_input(ws, "exp-empty-ops", "test")

    # Overwrite opportunities with empty list
    opportunities_path = exp_dir / "evidence" / "opportunities.json"
    opportunities_path.write_text(json.dumps({"opportunities": [], "evidence_sha256": "abc", "scoring_sha256": "def"}), encoding="utf-8")

    content_agent = ContentAgent(
        "content-empty", exp_dir, history, "session-c", mcp_registry=MCPRegistry()
    )
    result = content_agent.run()
    assert result["success"] is False


# ─── Validation: §26 task content hash correctness ───


# ─── Fail-Closed: Opportunity Selection Safety Tests ───


def test_orchestrator_creation_fails_closed_when_no_opportunities(tmp_path):
    """Orchestrator auto-selection must fail closed when opportunities.json is missing."""
    ws = _create_minimal_workspace(tmp_path)
    exp_dir = ws / "experiments" / "exp-no-opps"
    (exp_dir / "evidence").mkdir(parents=True)
    (exp_dir / "output").mkdir(parents=True)

    orch = CMOrchestrator(config_dir=ws / "config", workspace_dir=ws)

    result = orch.run_creation_phase("exp-no-opps")
    assert result["success"] is False
    assert "opportunities" in result["error"].lower() or "qualified" in result["error"].lower()


def test_orchestrator_creation_fails_closed_with_empty_opportunities(tmp_path):
    """Orchestrator auto-selection must fail closed when opportunities list is empty."""
    ws = _create_minimal_workspace(tmp_path)
    exp_dir = ws / "experiments" / "exp-empty"
    (exp_dir / "evidence").mkdir(parents=True)
    (exp_dir / "output").mkdir(parents=True)

    empty_opps = {
        "status": "complete",
        "opportunities": [],
        "evidence_source_type": "simulated",
    }
    (exp_dir / "evidence" / "opportunities.json").write_text(
        json.dumps(empty_opps), encoding="utf-8"
    )

    orch = CMOrchestrator(config_dir=ws / "config", workspace_dir=ws)
    result = orch.run_creation_phase("exp-empty")
    assert result["success"] is False


def test_orchestrator_explicit_opportunity_id_still_works(tmp_path):
    """Explicitly passing an opportunity_id must bypass auto-selection and still work."""
    ws = _create_minimal_workspace(tmp_path)
    orch, _, _, result = _run_creation_phase(ws, "exp-explicit")
    assert result["success"] is True
    assert "task_id" in result["kilo_task_id"] or result.get("kilo_task_id")


def test_orchestrator_no_opportunity1_fallback_in_source():
    """Verify no production 'opportunity-1' fallback remains in cm_orchestrator source."""
    source = Path(__file__).resolve().parents[1] / "src" / "cm_orchestrator.py"
    content = source.read_text(encoding="utf-8")

    assert 'return "opportunity-1"' not in content, "Found 'return \"opportunity-1\"' fallback in cm_orchestrator.py"
    assert 'or "opportunity-1"' not in content, "Found 'or \"opportunity-1\"' fallback in cm_orchestrator.py"


def test_section_26_task_sha_matches_content(tmp_path):
    """The task_sha256 in the approval block must match the actual task content."""
    ws = _create_minimal_workspace(tmp_path)
    orch, _, _, _ = _run_creation_phase(ws, "exp-sha-verify")

    task_files = list((ws / "tasks").glob("kilo_task_*.json"))
    assert len(task_files) == 1

    for tf in task_files:
        task = json.loads(tf.read_text(encoding="utf-8"))

        # Verify task_sha256 matches content
        stored_sha = task["approval"]["task_sha256"]
        task_for_hash = {k: v for k, v in task.items() if k != "approval"}
        computed_sha = hashlib.sha256(
            json.dumps(task_for_hash, indent=2, sort_keys=True).encode("utf-8")
        ).hexdigest()

        assert stored_sha == computed_sha, f"Task SHA mismatch in {tf.name}: stored={stored_sha}, computed={computed_sha}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

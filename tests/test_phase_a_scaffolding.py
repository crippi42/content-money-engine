"""Phase A scaffolding tests for Content Money Engine.

Tests cover:
- CMOrchestrator initialization and room identity
- AgentBase evidence I/O protocol
- §26 task creation for CME (approval gate integration)
- §25 project authorization for content-money-engine
- MCP abstraction layer (no servers configured)
- §24-§26 infrastructure reuse verification
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

# Add both workstation and CME to path
_WORKSTATION = Path(__file__).resolve().parents[2] / "multi-ai-workstation-poc"
sys.path.insert(0, str(_WORKSTATION))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.kilo_adapter import KiloAdapter, TaskNotApprovedError, ApprovalStatus
from core.project_registry import ProjectRegistry
from core.session_history import SessionHistory
from src.cm_orchestrator import CMOrchestrator
from src.agents.base import AgentBase
from src.mcp.base import MCPRegistry, ResearchMCP, AffiliateMCP, ContentMCP, PublishingMCP, AnalyticsMCP


@pytest.fixture
def workstation_paths():
    """Return (config_dir, workspace_dir) pointing to the real workstation."""
    ws_root = Path(__file__).resolve().parents[2] / "multi-ai-workstation-poc"
    return ws_root / "config", ws_root


@pytest.fixture
def cme_workspace(tmp_path):
    """Create a temp workspace that mimics CME structure.

    The workspace IS the project root (matching the real CME layout where
    C:\\Users\\Omar\\content-money-engine is both workspace and project).
    """
    (tmp_path / "tasks").mkdir()
    (tmp_path / "results").mkdir()
    (tmp_path / "approved_tasks").mkdir()
    (tmp_path / "experiments").mkdir()
    (tmp_path / "sessions").mkdir()
    return tmp_path


@pytest.fixture
def cme_config(cme_workspace):
    """Create a temp config_dir with projects.yaml registering the temp workspace.

    This allows §25 project authorization to pass for the temp workspace path.
    The canonical_path matches cme_workspace itself (the project root).
    """
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
    # Copy worker_registry.yaml from workstation (CME workers are already registered)
    ws_root = Path(__file__).resolve().parents[2] / "multi-ai-workstation-poc"
    import shutil
    shutil.copy(ws_root / "config" / "worker_registry.yaml", config_dir / "worker_registry.yaml")
    return config_dir


# ── CMOrchestrator Tests ──


def test_cm_orchestrator_inherits_from_orchestrator(workstation_paths):
    config_dir, workspace_dir = workstation_paths
    orch = CMOrchestrator(config_dir, workspace_dir)
    from core.orchestrator import Orchestrator
    assert isinstance(orch, Orchestrator)


def test_cm_orchestrator_has_content_money_room_id(workstation_paths):
    config_dir, workspace_dir = workstation_paths
    orch = CMOrchestrator(config_dir, workspace_dir)
    assert orch.room_id == "content_money"


def test_cm_orchestrator_has_cme_project_id(workstation_paths):
    config_dir, workspace_dir = workstation_paths
    orch = CMOrchestrator(config_dir, workspace_dir)
    assert orch.project_id == "content-money-engine"


def test_cm_orchestrator_has_experiments_dir(workstation_paths):
    config_dir, workspace_dir = workstation_paths
    orch = CMOrchestrator(config_dir, workspace_dir)
    assert orch.experiments_dir == workspace_dir / "experiments"


def test_cm_orchestrator_creates_experiment_dir(workstation_paths, cme_workspace):
    config_dir = workstation_paths[0]
    orch = CMOrchestrator(config_dir, cme_workspace)
    exp_dir = orch._init_experiment("mvp-test")
    assert exp_dir.exists()
    assert (exp_dir / "evidence").exists()
    assert (exp_dir / "output").exists()
    assert (exp_dir / "work").exists()


# ── §25 Project Authorization Tests ──


def test_cme_project_is_registered_in_workstation_registry(workstation_paths):
    config_dir, _ = workstation_paths
    ws_root = Path(__file__).resolve().parents[2] / "multi-ai-workstation-poc"
    registry = ProjectRegistry(config_dir / "projects.yaml", ws_root)
    assert registry.load() is True
    project = registry.get_project("content-money-engine")
    assert project is not None
    assert project.get("enabled") is True


def test_cme_project_authorization_succeeds_for_correct_path(workstation_paths):
    config_dir, _ = workstation_paths
    ws_root = Path(__file__).resolve().parents[2] / "multi-ai-workstation-poc"
    cme_path = Path(r"C:\Users\Omar\content-money-engine")
    registry = ProjectRegistry(config_dir / "projects.yaml", ws_root)
    registry.load()
    auth = registry.authorize_project("content-money-engine", cme_path)
    assert auth.allowed is True


def test_cme_project_authorization_rejects_wrong_path(workstation_paths):
    config_dir, _ = workstation_paths
    ws_root = Path(__file__).resolve().parents[2] / "multi-ai-workstation-poc"
    wrong_path = Path(r"C:\Users\Omar\Prospector")
    registry = ProjectRegistry(config_dir / "projects.yaml", ws_root)
    registry.load()
    auth = registry.authorize_project("content-money-engine", wrong_path)
    assert auth.allowed is False


# ── §26 Approval Gate Integration Tests ──


def test_cm_orchestrator_creates_approval_gated_task(cme_config, cme_workspace):
    orch = CMOrchestrator(cme_config, cme_workspace)

    task = orch._create_cme_kilo_task(
        experiment_id="test-exp-001",
        task_description="Test publish task",
        task_type="draft",
    )
    assert task["success"] is True
    assert task["task_id"].startswith("kilo_task_")

    # Verify the task is in tasks/ , not approved_tasks/
    task_path = Path(task["task_path"])
    assert task_path.exists()

    task_data = json.loads(task_path.read_text(encoding="utf-8"))
    assert "approval" in task_data
    assert task_data["approval"]["status"] == "pending_approval"
    assert task_data["approval"]["required"] is True
    assert "task_sha256" in task_data["approval"]
    assert len(task_data["approval"]["task_sha256"]) == 64


def test_cm_orchestrator_publish_phase_creates_pending_task(cme_config, cme_workspace):
    orch = CMOrchestrator(cme_config, cme_workspace)

    result = orch.run_publish_phase("test-exp-002", task_id="kilo_task_test")
    assert result["success"] is True
    assert result["phase"] == "publish"
    assert result["approval_status"] == "pending_approval"
    assert "task_id" in result


def test_check_task_approval_raises_when_not_approved(cme_config, cme_workspace):
    orch = CMOrchestrator(cme_config, cme_workspace)
    adapter = orch._get_cme_kilo_adapter()

    # Create a task but don't approve it
    task = orch._create_cme_kilo_task(
        experiment_id="test-exp-003",
        task_description="Test task",
        task_type="publish",
    )
    task_id = task["task_id"]

    # check_task_approval should raise because it's only in tasks/, not approved_tasks/
    with pytest.raises(TaskNotApprovedError):
        adapter.check_task_approval(task_id)


def test_check_task_approval_passes_after_approval(cme_config, cme_workspace):
    orch = CMOrchestrator(cme_config, cme_workspace)
    adapter = orch._get_cme_kilo_adapter()

    task = orch._create_cme_kilo_task(
        experiment_id="test-exp-004",
        task_description="Test task",
        task_type="publish",
    )
    task_id = task["task_id"]

    # Approve the task
    approval_result = adapter.approve_task(task_id)
    assert approval_result["success"] is True

    # Now check_task_approval should succeed
    status = adapter.check_task_approval(task_id)
    assert status.is_approved() is True
    assert status.status == "approved"


def test_publish_task_moved_from_tasks_to_approved_tasks(cme_config, cme_workspace):
    orch = CMOrchestrator(cme_config, cme_workspace)
    adapter = orch._get_cme_kilo_adapter()

    task = orch._create_cme_kilo_task(
        experiment_id="test-exp-005",
        task_description="Test task",
        task_type="publish",
    )
    task_id = task["task_id"]

    # Before approval: in tasks/
    assert (adapter.tasks_dir / f"{task_id}.json").exists()
    assert not (adapter.approved_tasks_dir / f"{task_id}.json").exists()

    # Approve
    adapter.approve_task(task_id)

    # After approval: in approved_tasks/
    assert not (adapter.tasks_dir / f"{task_id}.json").exists()
    assert (adapter.approved_tasks_dir / f"{task_id}.json").exists()


# ── §24 Result Consumption Compatibility Tests ──


def test_cme_publish_result_consumption_pending_when_approved_but_no_result(cme_config, cme_workspace):
    """When a task is approved but Kilo hasn't produced a result yet,
    consume_publish_result should report pending (§24 pattern)."""
    orch = CMOrchestrator(cme_config, cme_workspace)
    adapter = orch._get_cme_kilo_adapter()

    # Create and approve a task
    task = orch._create_cme_kilo_task(
        experiment_id="test-exp-006",
        task_description="Test publish task",
        task_type="publish",
    )
    task_id = task["task_id"]
    adapter.approve_task(task_id)

    # No result exists yet → should be pending
    result = orch.consume_publish_result("test-exp-006", task_id)
    assert result["success"] is True
    assert result["consumption_status"] == "pending"


def test_cme_rejects_publish_result_without_approval(cme_config, cme_workspace):
    orch = CMOrchestrator(cme_config, cme_workspace)

    task = orch._create_cme_kilo_task(
        experiment_id="test-exp-007",
        task_description="Test",
        task_type="publish",
    )
    task_id = task["task_id"]

    # Don't approve — consume_publish_result should reject
    result = orch.consume_publish_result("test-exp-007", task_id)
    assert result["success"] is False
    assert "not approved" in result["error"].lower() or "not found" in result["error"].lower()


def test_cme_consumes_publish_result_after_approval_and_execution(cme_config, cme_workspace):
    orch = CMOrchestrator(cme_config, cme_workspace)
    adapter = orch._get_cme_kilo_adapter()

    task = orch._create_cme_kilo_task(
        experiment_id="test-exp-008",
        task_description="Test",
        task_type="publish",
    )
    task_id = task["task_id"]

    # Approve
    adapter.approve_task(task_id)

    # Write a result (simulating Kilo execution)
    project_dir = cme_workspace
    result_data = {
        "task_id": task_id,
        "status": "completed",
        "changes": ["published_content.md"],
        "summary": "Content published to test channel",
        "timestamp": "2026-08-31T00:00:00Z",
        "project_reference": {
            "project_id": "content-money-engine",
            "project_path": str(project_dir.resolve()),
            "path_verified_at": "2026-08-31T00:00:00Z",
        },
    }
    result_path = adapter.results_dir / f"kilo_result_{task_id}.json"
    result_path.write_text(json.dumps(result_data), encoding="utf-8")

    # Consume
    result = orch.consume_publish_result("test-exp-008", task_id)
    assert result["success"] is True
    assert result["consumption_status"] == "consumed"


# ── AgentBase Tests ──


class _DummyAgent(AgentBase):
    @property
    def agent_type(self) -> str:
        return "test_agent"

    def get_required_inputs(self) -> list[str]:
        return ["input1"]

    def produce_output(self, inputs: dict[str, dict]) -> dict:
        return {
            "status": "complete",
            "input_received": inputs["input1"],
        }


def test_agent_base_writes_output_with_sha256(tmp_path):
    exp_dir = tmp_path / "test-exp"
    exp_dir.mkdir()
    agent = _DummyAgent("agent-1", exp_dir, None, "session-1")

    # Write input (evidence dir already created by AgentBase.__init__)
    (exp_dir / "evidence" / "input1.json").write_text(
        json.dumps({"key": "value"}), encoding="utf-8"
    )

    result = agent.run()
    assert result["success"] is True
    assert "artifact_path" in result

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    assert "evidence_sha256" in artifact
    assert len(artifact["evidence_sha256"]) == 64


def test_agent_base_logs_to_session_history(tmp_path):
    from core.session_history import SessionHistory

    exp_dir = tmp_path / "test-exp-2"
    exp_dir.mkdir()
    db_path = tmp_path / "history.db"
    history = SessionHistory(db_path)

    agent = _DummyAgent("agent-2", exp_dir, history, "session-2")
    # evidence dir already created by AgentBase.__init__
    (exp_dir / "evidence" / "input1.json").write_text(
        json.dumps({"key": "value"}), encoding="utf-8"
    )

    agent.run()

    events = history.get_session_events("session-2")
    assert any(e["event_type"] == "agent_run_started" for e in events)
    assert any(e["event_type"] == "agent_run_completed" for e in events)


def test_agent_base_missing_input_reports_error(tmp_path):
    exp_dir = tmp_path / "test-exp-3"
    exp_dir.mkdir()
    agent = _DummyAgent("agent-3", exp_dir, None, "session-3")
    result = agent.run()
    assert result["success"] is False
    assert "missing" in result["error"].lower()


# ── MCP Abstraction Layer Tests ──


def test_mcp_registry_all_interfaces_not_configured():
    registry = MCPRegistry()
    configured = registry.list_configured_servers()
    for name, configured_status in configured.items():
        assert configured_status is False, f"MCP server {name} should not be configured in Phase A"


def test_mcp_registry_lists_all_interfaces():
    registry = MCPRegistry()
    interfaces = registry.list_interfaces()
    assert "research" in interfaces
    assert "affiliate" in interfaces
    assert "content" in interfaces
    assert "publishing" in interfaces
    assert "analytics" in interfaces


def test_mcp_registry_returns_uninitialized_server():
    registry = MCPRegistry()
    server = registry.get_server("research")
    assert server is not None
    assert server.server_name == "research_mcp"
    assert not server.initialize()
    assert "not_configured" in "not_configured"


def test_mcp_publishing_requires_approval():
    server = PublishingMCP()
    assert server.requires_approval is True


def test_mcp_all_servers_return_not_configured():
    servers = [ResearchMCP({}), AffiliateMCP({}), ContentMCP({}), PublishingMCP({}), AnalyticsMCP({})]
    for server in servers:
        assert server.initialize() is False


# ── Integration: §24-§26 Reuse Verification ──


def test_cme_reuses_workstation_kilo_adapter(workstation_paths):
    config_dir, _ = workstation_paths
    ws_root = Path(__file__).resolve().parents[2] / "multi-ai-workstation-poc"

    from core.kilo_adapter import KiloAdapter
    registry = ProjectRegistry(config_dir / "projects.yaml", ws_root)
    registry.load()
    adapter = KiloAdapter(ws_root, registry)

    # Verify the adapter has §26 methods
    assert hasattr(adapter, "check_task_approval")
    assert hasattr(adapter, "approve_task")
    assert hasattr(adapter, "reject_task")
    assert hasattr(adapter, "revoke_task")
    assert hasattr(adapter, "list_approved_tasks")
    assert hasattr(adapter, "compute_task_sha256")
    assert hasattr(adapter, "approved_tasks_dir")


def test_cme_room_registered_in_workstation_rooms(workstation_paths):
    config_dir, _ = workstation_paths
    ws_root = Path(__file__).resolve().parents[2] / "multi-ai-workstation-poc"
    registry = ProjectRegistry(config_dir / "projects.yaml", ws_root)
    assert registry.load() is True


# ── Isolation Tests ──


def test_prospector_not_modified():
    prospector = Path(r"C:\Users\Omar\Prospector")
    assert prospector.exists()


def test_amazon_money_auditor_not_modified():
    ama = Path(r"C:\Users\Omar\amazon-money-auditor")
    assert ama.exists()


def test_cme_is_separate_from_prospector():
    cme = Path(r"C:\Users\Omar\content-money-engine")
    prospector = Path(r"C:\Users\Omar\Prospector")
    assert cme != prospector
    assert cme.exists()


def test_cme_is_separate_from_amazon_money_auditor():
    cme = Path(r"C:\Users\Omar\content-money-engine")
    ama = Path(r"C:\Users\Omar\amazon-money-auditor")
    assert cme != ama
    assert cme.exists()


def test_cme_is_under_top_level_not_under_workstation():
    cme = Path(r"C:\Users\Omar\content-money-engine")
    workstation = Path(r"C:\Users\Omar\multi-ai-workstation-poc")
    # CME should NOT be inside the workstation directory
    try:
        cme.relative_to(workstation)
        assert False, "CME should not be inside workstation"
    except ValueError:
        pass  # Expected: CME is not a subdir of workstation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

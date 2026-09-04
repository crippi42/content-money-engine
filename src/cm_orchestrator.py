"""CMOrchestrator — Content Money Engine orchestration layer.

Extends the Multi-AI Workstation's Orchestrator class to add content-specific
pipeline phases: Research → Score → Create → Publish → Analyze → Feedback.

This class reuses ALL existing §24–§26 infrastructure from the workstation.
It does NOT duplicate the Controlled Dispatcher or any approval mechanism.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.opportunities.registry import NoQualifiedOpportunityError

# Import workstation infrastructure
_WORKSTATION_ROOT = Path(__file__).resolve().parents[2] / "multi-ai-workstation-poc"
if str(_WORKSTATION_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSTATION_ROOT))

from core.orchestrator import Orchestrator
from core.kilo_adapter import KiloAdapter, TaskNotApprovedError
from core.project_registry import ProjectRegistry
from core.session_history import SessionHistory
from rooms.builder_room import BuilderRoom

# CME agent imports
from src.agents.researcher import ResearcherAgent
from src.agents.scorer import ScorerAgent
from src.agents.content_agent import ContentAgent
from src.agents.analyst import AnalystAgent, run_analysis_with_opportunity_selection


class CMOrchestrator(Orchestrator):
    """Orchestrator for the Content Money Engine room.

    Inherits all §24–§26 capabilities from the base Orchestrator and adds
    content-specific phases. Each phase corresponds to one agent type.
    """

    CME_ROOM_ID = "content_money"

    def __init__(self, config_dir: Path, workspace_dir: Path):
        super().__init__(config_dir, workspace_dir)
        self.room_id = self.CME_ROOM_ID
        self.project_id = "content-money-engine"
        self.experiments_dir = workspace_dir / "experiments"
        self.experiments_dir.mkdir(parents=True, exist_ok=True)

    # ── Phase 1: Research ──

    def run_research_phase(
        self,
        experiment_id: str,
        query: str,
        source_type: str = "simulated",
        seed_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Phase 1: Researcher discovers opportunities.

        Args:
            experiment_id: Unique experiment identifier
            query: The niche/topic to research
            source_type: "simulated" | "seed" | "externally_sourced"
            seed_data: Operator-provided data for seed/external modes

        Produces:
            experiments/<id>/evidence/research_input.json (input)
            experiments/<id>/output/researcher_output.json (output)
            experiments/<id>/evidence/research.json (archived output)
        """
        experiment_dir = self._init_experiment(experiment_id)
        self._log_cme_event(
            "research_phase_started",
            {"experiment_id": experiment_id, "query": query, "source_type": source_type},
        )

        # Write research input (evidence) with provenance
        research_input = {
            "experiment_id": experiment_id,
            "query": query,
            "niche": experiment_id,
            "source_type": source_type,
            "source_description": self._describe_source(source_type),
            "seed_data": seed_data or {},
            "provenance": {
                "created_by": "CMOrchestrator",
                "room_id": self.room_id,
                "session_id": self.session_id,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        input_path = experiment_dir / "evidence" / "research_input.json"
        input_path.write_text(json.dumps(research_input, indent=2), encoding="utf-8")

        # Compute provenance hash on the input
        import hashlib
        input_hash = hashlib.sha256(
            json.dumps(research_input, indent=2, sort_keys=True).encode("utf-8")
        ).hexdigest()

        # Invoke Researcher agent — uses OmniRoute for model selection
        researcher = ResearcherAgent(
            agent_id=f"researcher-{experiment_id}",
            experiment_dir=experiment_dir,
            session_history=self.session_history,
            session_id=self.session_id,
            worker_registry=self.registry,
            workspace_dir=self.workspace_dir,
            use_omniroute=True,
        )

        # Write research_input as the agent's expected input
        researcher_input_path = experiment_dir / "evidence" / "research_input.json"
        researcher_input_path.write_text(
            json.dumps(research_input, indent=2, sort_keys=True), encoding="utf-8"
        )

        result = researcher.run()

        # Archive evidence
        evidence_path = None
        if result["success"]:
            evidence_path = researcher.archive_evidence(experiment_dir / "output")

        self._log_cme_event(
            "research_phase_completed",
            {
                "experiment_id": experiment_id,
                "success": result["success"],
                "input_hash": input_hash,
                "evidence_path": str(evidence_path) if evidence_path else None,
            },
        )

        return {
            "success": result["success"],
            "experiment_id": experiment_id,
            "phase": "research",
            "experiment_dir": str(experiment_dir),
            "agent_result": result,
            "evidence_path": str(evidence_path) if evidence_path else None,
        }

    @staticmethod
    def _describe_source(source_type: str) -> str:
        descriptions = {
            "simulated": "Synthetic data generated by ResearcherAgent in simulation mode. NOT real market data.",
            "seed": "Operator-provided seed data. Quality depends on operator's research.",
            "externally_sourced": "Data sourced from external research tools (web scraping, affiliate APIs). To be enabled in Phase C.",
        }
        return descriptions.get(source_type, "Unknown source type")

    # ── Phase 2: Scoring ──

    def run_scoring_phase(self, experiment_id: str) -> dict[str, Any]:
        """Phase 2: Opportunity Scorer ranks discovered opportunities.

        Reads experiments/<id>/evidence/research.json (produced by Researcher)
        and writes experiments/<id>/evidence/opportunities.json.

        The scoring dimensions are deterministic and documented. Each score
        includes a rationale explaining how the number was derived.
        """
        self._log_cme_event("scoring_phase_started", {"experiment_id": experiment_id})

        experiment_dir = self.experiments_dir / experiment_id
        research_path = experiment_dir / "evidence" / "research.json"

        if not research_path.exists():
            self._log_cme_event(
                "scoring_phase_failed",
                {"experiment_id": experiment_id, "reason": "research.json not found"},
            )
            return {
                "success": False,
                "error": f"Research evidence not found: {research_path}",
                "phase": "scoring",
            }

        # Read research evidence
        research = json.loads(research_path.read_text(encoding="utf-8"))

        # Write research as the scorer's expected input
        scorer_input_path = experiment_dir / "evidence" / "research_input.json"
        # The scorer's AgentBase expects input named "research.json" in evidence/
        # AgentBase reads from evidence/<input_name>.json
        # The research.json already exists in evidence/

        # Invoke Scorer agent — uses deterministic scoring rules
        scorer = ScorerAgent(
            agent_id=f"scorer-{experiment_id}",
            experiment_dir=experiment_dir,
            session_history=self.session_history,
            session_id=self.session_id,
            worker_registry=self.registry,
            workspace_dir=self.workspace_dir,
        )

        result = scorer.run()

        # Archive evidence
        evidence_path = None
        if result["success"]:
            evidence_path = scorer.archive_evidence(experiment_dir / "output")

        self._log_cme_event(
            "scoring_phase_completed",
            {
                "experiment_id": experiment_id,
                "success": result["success"],
                "evidence_path": str(evidence_path) if evidence_path else None,
            },
        )

        return {
            "success": result["success"],
            "experiment_id": experiment_id,
            "phase": "scoring",
            "agent_result": result,
            "evidence_path": str(evidence_path) if evidence_path else None,
        }

    # ── Phase 3: Creation ──

    def _select_approved_opportunity(self, experiment_id: str) -> str:
        """Select the top-scored opportunity using the Opportunity Registry + Selector.

        Reads experiments/<id>/evidence/opportunities.json and selects the top-scored
        opportunity. Fails closed: raises NoQualifiedOpportunityError if the registry
        layer is unavailable, evidence is missing, or no opportunity qualifies.
        """
        from src.opportunities.registry import NoQualifiedOpportunityError

        experiment_dir = self.experiments_dir / experiment_id
        opportunities_path = experiment_dir / "evidence" / "opportunities.json"

        if not opportunities_path.exists():
            raise NoQualifiedOpportunityError(
                f"Opportunities evidence not found: {opportunities_path}"
            )

        try:
            from src.opportunities.registry import OpportunityRegistry
            from src.opportunities.selector import OpportunitySelector
        except ImportError:
            raise NoQualifiedOpportunityError(
                "Opportunity Registry module not available — cannot select qualified opportunity"
            )

        registry = OpportunityRegistry(experiment_dir)
        if not registry.load():
            raise NoQualifiedOpportunityError(
                "Failed to load opportunities from opportunities.json — "
                "registry layer unavailable, cannot qualify selection"
            )

        selector = OpportunitySelector(min_score=0, min_confidence=0)
        result = selector.select_with_rationale(registry, strategy="top_scored")
        summary = result.get("registry_summary", {})
        top_keyword = summary.get("top_keyword")
        if not top_keyword:
            raise NoQualifiedOpportunityError(
                "Registry loaded but no top keyword found in summary"
            )
        return top_keyword

    def run_creation_phase(self, experiment_id: str, approved_opportunity_id: str | None = None) -> dict[str, Any]:
        """Phase 3: ContentAgent generates content draft from scored opportunities.

        Reads experiments/<id>/evidence/opportunities.json (produced by ScorerAgent)
        and writes experiments/<id>/evidence/content_plan.json + content_draft.json.

        Creates a §26-gated task for the draft review, linking the draft's
        SHA-256 to the task for §26 approval boundary.

        This phase does NOT publish. It creates a draft artifact.
        Publishing is gated by §26 (see run_publish_phase).
        """
        experiment_dir = self.experiments_dir / experiment_id
        opportunities_path = experiment_dir / "evidence" / "opportunities.json"

        if approved_opportunity_id is None:
            try:
                approved_opportunity_id = self._select_approved_opportunity(experiment_id)
            except NoQualifiedOpportunityError as e:
                self._log_cme_event(
                    "creation_phase_failed",
                    {"experiment_id": experiment_id, "reason": str(e)},
                )
                return {
                    "success": False,
                    "error": str(e),
                    "phase": "creation",
                }
        self._log_cme_event(
            "creation_phase_started",
            {"experiment_id": experiment_id, "opportunity_id": approved_opportunity_id},
        )

        experiment_dir = self.experiments_dir / experiment_id
        opportunities_path = experiment_dir / "evidence" / "opportunities.json"

        if not opportunities_path.exists():
            self._log_cme_event(
                "creation_phase_failed",
                {"experiment_id": experiment_id, "reason": "opportunities.json not found"},
            )
            return {
                "success": False,
                "error": f"Opportunities evidence not found: {opportunities_path}",
                "phase": "creation",
            }

        # Invoke ContentAgent
        from src.mcp.base import MCPRegistry
        mcp_registry = MCPRegistry()

        content_agent = ContentAgent(
            agent_id=f"content-{experiment_id}",
            experiment_dir=experiment_dir,
            session_history=self.session_history,
            session_id=self.session_id,
            mcp_registry=mcp_registry,
            workspace_dir=self.workspace_dir,
        )

        result = content_agent.run()

        if not result["success"]:
            self._log_cme_event("creation_phase_failed", {"error": result.get("error")})
            return {
                "success": False,
                "error": result.get("error", "ContentAgent failed"),
                "phase": "creation",
            }

        # Archive evidence (writes content_plan.json and content_draft.json to evidence/)
        draft_path = content_agent.archive_evidence(experiment_dir / "output")

        # Read the draft to get its SHA-256 for §26 task linkage
        draft_sha256 = ""
        if draft_path and draft_path.exists():
            draft = json.loads(draft_path.read_text(encoding="utf-8"))
            draft_sha256 = draft.get("evidence_sha256", "")

        # Create §26 task for draft review, linking to the draft's SHA-256
        task = self._create_cme_kilo_task(
            experiment_id=experiment_id,
            task_description=f"Review content draft for opportunity {approved_opportunity_id}",
            task_type="draft_review",
            evidence_path=draft_path if draft_path and draft_path.exists() else None,
        )

        if not task.get("success"):
            self._log_cme_event("creation_phase_failed", {"reason": task.get("error")})
            return task

        self._log_cme_event(
            "creation_phase_completed",
            {
                "experiment_id": experiment_id,
                "task_id": task["task_id"],
                "draft_sha256": draft_sha256,
                "mcp_available": False,
                "generation_mode": "plan_only",
            },
        )

        return {
            "success": True,
            "experiment_id": experiment_id,
            "phase": "creation",
            "kilo_task_id": task["task_id"],
            "draft_sha256": draft_sha256,
            "draft_path": str(draft_path) if draft_path else None,
            "mcp_available": False,
            "generation_mode": "plan_only",
        }

    # ── Phase 4: Publishing (§26 GATED) ──

    def run_publish_phase(self, experiment_id: str, task_id: str, draft_path: Path | None = None) -> dict[str, Any]:
        """Phase 4: Publisher — produces a publish intent artifact.

        This method creates a §26-gated task for the publish action. It does
        NOT execute the publish. The publish only happens after human approval
        via `workstation.py approve <task_id>`.

        If draft_path is provided, the publish task is linked to the draft evidence
        for §26 approval traceability.

        Returns immediately with task_id. The publish result is consumed
        asynchronously via consume_kilo_result() when Kilo completes.
        """
        self._log_cme_event(
            "publish_phase_started",
            {"experiment_id": experiment_id, "task_id": task_id},
        )

        # §26: Create a publish-intent task. This goes to tasks/ with
        # approval.status = pending_approval. It will NOT be visible to Kilo
        # until a human approves it via workstation.py approve.
        publish_task = self._create_cme_kilo_task(
            experiment_id=experiment_id,
            task_description=f"Publish approved content for experiment {experiment_id}",
            task_type="publish",
            evidence_path=draft_path,
        )

        if not publish_task.get("success"):
            self._log_cme_event("publish_phase_failed", {"reason": publish_task.get("error")})
            return publish_task

        self.session_history.log_event(
            session_id=self.session_id,
            event_type="task_approval_pending",
            room_id=self.room_id,
            phase="publish",
            payload={
                "experiment_id": experiment_id,
                "task_id": publish_task["task_id"],
                "approval_boundary": "publish_to_external_channel",
                "requires_human_approval": True,
            },
        )

        self._log_cme_event(
            "publish_phase_waiting_for_approval",
            {"task_id": publish_task["task_id"]},
        )

        return {
            "success": True,
            "experiment_id": experiment_id,
            "phase": "publish",
            "task_id": publish_task["task_id"],
            "approval_status": "pending_approval",
            "message": "Publish task created. Awaiting §26 human approval.",
        }

    def consume_publish_result(self, experiment_id: str, task_id: str) -> dict[str, Any]:
        """Consume a completed publish result from Kilo (§24 pattern).

        Uses BuilderRoom.consume_kilo_result for result validation and
        project identity checking (§24, §25).
        """
        # §26: Verify the task was approved before consuming its result
        kilo_adapter = self._get_cme_kilo_adapter()
        try:
            approval_status = kilo_adapter.check_task_approval(task_id)
            if not approval_status.is_approved():
                return {
                    "success": False,
                    "error": f"Task {task_id} not approved",
                    "approval_status": approval_status.status,
                }
        except TaskNotApprovedError:
            return {
                "success": False,
                "error": f"Task {task_id} not found in approved_tasks/",
                "approval_status": "unapproved",
            }

        # §24: Validate and consume the result
        project_dir = self.workspace_dir
        consumption = self.builder_room.consume_kilo_result(
            kilo_adapter, task_id, project_dir
        )
        return {
            "success": True,
            "consumption_status": consumption["status"],
            "consumption": consumption,
        }

    # ── Phase 5: Analysis ──

    def run_analysis_phase(self, experiment_id: str) -> dict[str, Any]:
        """Phase 5: Analyst tracks performance and produces feedback.

        Uses AnalystAgent to analyze the top-scored opportunity and draft,
        producing analytics.json with provenance chain.
        """
        self._log_cme_event("analysis_phase_started", {"experiment_id": experiment_id})

        try:
            from src.agents.analyst import AnalystAgent

            experiment_dir = self.experiments_dir / experiment_id
            history = self.session_history

            opportunities_path = experiment_dir / "evidence" / "opportunities.json"
            if not opportunities_path.exists():
                self._log_cme_event(
                    "analysis_phase_failed",
                    {"experiment_id": experiment_id, "reason": "opportunities.json not found"},
                )
                return {
                    "success": False,
                    "error": "Opportunities evidence not found",
                    "experiment_id": experiment_id,
                    "phase": "analysis",
                }

            from src.opportunities.registry import NoQualifiedOpportunityError

            try:
                result = run_analysis_with_opportunity_selection(experiment_dir)
            except NoQualifiedOpportunityError as e:
                self._log_cme_event(
                    "analysis_phase_failed",
                    {"experiment_id": experiment_id, "reason": str(e)},
                )
                return {
                    "success": False,
                    "error": str(e),
                    "experiment_id": experiment_id,
                    "phase": "analysis",
                }

            if result.get("status") != "success":
                self._log_cme_event(
                    "analysis_phase_failed",
                    {"experiment_id": experiment_id, "reason": result.get("error", "unknown")},
                )
                return {
                    "success": False,
                    "error": result.get("error", "unknown error"),
                    "experiment_id": experiment_id,
                }

            analytics_path = experiment_dir / "evidence" / "analytics.json"
            analytics = json.loads(analytics_path.read_text(encoding="utf-8"))

            self._log_cme_event(
                "analysis_phase_completed",
                {"experiment_id": experiment_id, "output": "analytics.json"},
            )
            return {
                "success": True,
                "experiment_id": experiment_id,
                "phase": "analysis",
                "analytics_path": str(analytics_path),
                "analytics": analytics,
            }

        except ImportError:
            from src.agents.analyst import AnalystAgent
            agent = AnalystAgent(f"analyst-{experiment_id}", experiment_dir, history, f"session-{experiment_id}")
            result = agent.run()
            if result.get("success"):
                analytics_path = experiment_dir / "evidence" / "analytics.json"
                analytics = json.loads(analytics_path.read_text(encoding="utf-8"))
                return {
                    "success": True,
                    "experiment_id": experiment_id,
                    "phase": "analysis",
                    "analytics_path": str(analytics_path),
                    "analytics": analytics,
                }
            return result


    def run_feedback_phase(self, experiment_id: str, analysis_result: dict[str, Any]) -> dict[str, Any]:
        """Phase 6: Feed Analyst results back to Researcher for next cycle.

        Produces feedback.json with provenance chain for the next research cycle.
        """
        experiment_dir = self.experiments_dir / experiment_id
        feedback_path = experiment_dir / "evidence" / "feedback.json"

        from src.agents.analyst import AnalystAgent

        agent = AnalystAgent(f"feedback-{experiment_id}", experiment_dir, self.session_history, f"session-{experiment_id}")
        feedback = agent._generate_feedback(analysis_result)

        self._write_evidence_file(feedback_path, feedback)

        self._log_cme_event(
            "feedback_phase_completed",
            {"experiment_id": experiment_id, "feedback_path": str(feedback_path)},
        )
        return {
            "success": True,
            "experiment_id": experiment_id,
            "phase": "feedback",
            "feedback_path": str(feedback_path),
        }

    def _write_evidence_file(self, path: Path, data: dict[str, Any]):
        """Write a JSON file to evidence directory."""
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ── §26 Integration ──

    def _get_cme_kilo_adapter(self) -> KiloAdapter:
        """Create a KiloAdapter pointed at the CME workspace.

        Reuses the workstation's KiloAdapter. The adapter creates task
        artifacts in the CME workspace's tasks/ directory, which feeds
        the workstation's §26 Controlled Dispatcher.
        """
        registry_loaded = self._project_registry.load()
        return KiloAdapter(self.workspace_dir, self._project_registry)

    def _create_cme_kilo_task(
        self, experiment_id: str, task_description: str, task_type: str, evidence_path: Path | None = None
    ) -> dict[str, Any]:
        """Create a §26-gated Kilo task for CME.

        Reuses KiloAdapter.create_kilo_task which enforces §25 project
        authorization and writes the §26 approval block. The session_id
        includes task_type to ensure unique task files per phase.

        Since the workstation KiloAdapter hardcodes task_type as "engineering",
        we post-process the task file within CME's boundary to set the correct
        CME task_type and recompute task_sha256 on the updated content.

        If evidence_path is provided, the task is linked to that evidence
        for §26 approval traceability.
        """
        kilo_adapter = self._get_cme_kilo_adapter()
        result = kilo_adapter.create_kilo_task(
            session_id=self.session_id + f"-{experiment_id}-{task_type}",
            project_id=self.project_id,
            project_dir=self.workspace_dir,
            task_description=task_description,
            evidence_path=evidence_path,
            consensus_path=None,
            max_files_to_change=10,
        )

        if not result.get("success"):
            return result

        # Post-process: set correct CME task_type and recompute SHA-256.
        # This is done PRE-approval, so the integrity hash is updated
        # to reflect the final task content before human review.
        task_path = Path(result["task_path"])
        task = json.loads(task_path.read_text(encoding="utf-8"))
        task["task_type"] = task_type

        task_for_hash = {k: v for k, v in task.items() if k != "approval"}
        task_sha256 = hashlib.sha256(
            json.dumps(task_for_hash, indent=2, sort_keys=True).encode("utf-8")
        ).hexdigest()
        task["approval"]["task_sha256"] = task_sha256

        task_path.write_text(
            json.dumps(task, indent=2, sort_keys=True), encoding="utf-8"
        )

        result["task"] = task
        return result

    # ── Helpers ──

    def _init_experiment(self, experiment_id: str) -> Path:
        """Initialize an experiment directory with standard subdirectories."""
        exp_dir = self.experiments_dir / experiment_id
        (exp_dir / "evidence").mkdir(parents=True, exist_ok=True)
        (exp_dir / "output").mkdir(parents=True, exist_ok=True)
        (exp_dir / "work").mkdir(parents=True, exist_ok=True)
        return exp_dir

    def _log_cme_event(self, event_type: str, payload: dict[str, Any] | None = None):
        """Log an event to SessionHistory with CME room_id."""
        self.session_history.log_event(
            session_id=self.session_id,
            event_type=event_type,
            room_id=self.room_id,
            phase="content_pipeline",
            payload=payload,
        )

    def run_content_pipeline(self, experiment_id: str, niche_query: str) -> dict[str, Any]:
        """Run the full content money pipeline for one experiment.

        This is the main entry point for a content experiment cycle:
        Research → Score → Create → Publish(§26) → Analyze → Feedback

        Note: Publishing is §26-gated. After run_publish_phase(), the system
        waits for human approval. The pipeline returns at that point.
        """
        results: dict[str, Any] = {"experiment_id": experiment_id}

        # Phase 1: Research (simulated for Phase B)
        print("[Phase 1] Research (simulated)")
        results["research"] = self.run_research_phase(
            experiment_id, niche_query, source_type="simulated"
        )

        # Phase 2: Scoring
        print("[Phase 2] Scoring")
        results["scoring"] = self.run_scoring_phase(experiment_id)

        # Phase 3: Creation
        print("[Phase 3] Creation")
        creation_result = self.run_creation_phase(
            experiment_id
        )
        results["creation"] = creation_result

        # Phase 4: Publish (§26 GATED — does not execute until approved)
        print("[Phase 4] Publish (§26 gated)")
        publish_result = self.run_publish_phase(
            experiment_id,
            creation_result.get("kilo_task_id", ""),
            draft_path=Path(creation_result["draft_path"]) if creation_result.get("draft_path") else None,
        )
        results["publish"] = publish_result

        # Phase 5 & 6 come AFTER human approval and Kilo execution
        # (not run in this method — would be called from consume_publish_result)

        return results

"""AgentBase — abstract base class for all Content Money Engine agents.

Each agent follows an evidence I/O protocol:
1. Reads input evidence from a JSON file
2. Produces output evidence as a JSON file
3. Logs actions to SessionHistory

Agents NEVER perform external actions directly. Actions that modify external
systems (publishing, account changes, financial commitments) produce a
"publish intent" artifact that flows through the §26 approval gate.
"""

from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AgentBase(ABC):
    """Abstract base class for CME agents."""

    def __init__(
        self,
        agent_id: str,
        experiment_dir: Path,
        session_history: Any,
        session_id: str,
    ):
        self.agent_id = agent_id
        self.experiment_dir = Path(experiment_dir)
        self.session_history = session_history
        self.session_id = session_id
        self.evidence_dir = self.experiment_dir / "evidence"
        self.output_dir = self.experiment_dir / "output"
        self.work_dir = self.experiment_dir / "work"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    @property
    @abstractmethod
    def agent_type(self) -> str:
        """Human-readable agent type (e.g. 'researcher', 'scorer')."""

    @abstractmethod
    def get_required_inputs(self) -> list[str]:
        """Return list of required input evidence file names."""

    @abstractmethod
    def produce_output(self, inputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Process inputs and return output artifact.

        Args:
            inputs: Dict mapping input name to parsed JSON content.

        Returns:
            Output artifact dict. Must include at minimum:
            - agent_id: str
            - agent_type: str
            - timestamp: str (ISO 8601)
            - status: str (e.g. 'complete', 'error')
        """

    def read_input(self, name: str) -> dict[str, Any] | None:
        """Read an input evidence file by name."""
        path = self.evidence_dir / f"{name}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def write_output(self, artifact: dict[str, Any]) -> Path:
        """Write output artifact to output directory.

        Returns the path to the written file.
        """
        # Add metadata
        artifact.setdefault("agent_id", self.agent_id)
        artifact.setdefault("agent_type", self.agent_type)
        artifact.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        artifact.setdefault("evidence_version", "1.0")

        # Compute content hash for tamper detection
        content_hash = hashlib.sha256(
            json.dumps(artifact, indent=2, sort_keys=True).encode("utf-8")
        ).hexdigest()
        artifact["evidence_sha256"] = content_hash

        path = self.output_dir / f"{self.agent_id}_output.json"
        path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
        return path

    def run(self) -> dict[str, Any]:
        """Execute the agent: read inputs, produce output, log.

        Returns a status dict with success status and artifact path.
        """
        self._log_event("agent_run_started")

        # Read required inputs
        inputs: dict[str, dict[str, Any]] = {}
        missing: list[str] = []
        for name in self.get_required_inputs():
            data = self.read_input(name)
            if data is None:
                missing.append(name)
            else:
                inputs[name] = data

        if missing:
            error_artifact = {
                "agent_id": self.agent_id,
                "agent_type": self.agent_type,
                "status": "error",
                "error": f"Missing required inputs: {missing}",
            }
            path = self.write_output(error_artifact)
            self._log_event("agent_run_failed", {"missing": missing})
            return {
                "success": False,
                "error": f"Missing inputs: {missing}",
                "artifact_path": str(path),
            }

        # Produce output
        try:
            output = self.produce_output(inputs)
            if output.get("status") == "error":
                path = self.write_output(output)
                self._log_event(
                    "agent_run_failed",
                    {"error": output.get("error", "unknown error")},
                )
                return {
                    "success": False,
                    "error": output.get("error", "unknown error"),
                    "artifact_path": str(path),
                }
            path = self.write_output(output)
            self._log_event(
                "agent_run_completed",
                {
                    "artifact_path": str(path),
                    "evidence_sha256": output.get("evidence_sha256"),
                },
            )
            return {
                "success": True,
                "artifact_path": str(path),
                "artifact": output,
            }
        except Exception as exc:
            error_artifact = {
                "agent_id": self.agent_id,
                "agent_type": self.agent_type,
                "status": "error",
                "error": str(exc),
            }
            path = self.write_output(error_artifact)
            self._log_event("agent_run_failed", {"error": str(exc)})
            return {
                "success": False,
                "error": str(exc),
                "artifact_path": str(path),
            }

    def _log_event(self, event_type: str, payload: dict[str, Any] | None = None):
        """Log an event to SessionHistory."""
        if self.session_history is not None:
            self.session_history.log_event(
                session_id=self.session_id,
                event_type=event_type,
                worker_id=self.agent_id,
                room_id="content_money",
                phase="agent_cycle",
                payload=payload,
            )

    def compute_sha256(self, data: dict[str, Any]) -> str:
        """Compute SHA-256 hash of a data dict."""
        return hashlib.sha256(
            json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
        ).hexdigest()

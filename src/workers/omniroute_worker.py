"""OmniRoute worker adapter for CME.

Uses the existing OmniRoute server's OpenAI-compatible API endpoint.
CME discovers the endpoint and API key from the local OmniRoute
installation rather than hard-binding to individual model providers.

Architecture:
  ResearcherAgent -> OmniRouteWorker -> localhost:20128/v1 -> model selection
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.session_history import SessionHistory


class OmniRouteWorker:
    """Worker adapter that communicates with the local OmniRoute server.

    Uses the OpenAI-compatible /v1/ API exposed by OmniRoute. The API key
    and endpoint are auto-discovered from the existing OmniRoute configuration
    at C:\\Users\\Omar\\.omniroute\\.env (or OMNIROUTE_API_KEY/OMNIROUTE_BASE_URL
    env vars).

    The worker supports two modes:
    - 'auto': Use OmniRoute's auto-routing combo (e.g. 'auto/best-coding')
    - 'specific': Use a specific model (e.g. 'groq/Llama 3.3 70B')

    If OmniRoute is not running or unreachable, health_check returns available=False.
    """

    def __init__(
        self,
        registry_entry: dict[str, Any],
        workspace_dir: Path,
        session_history: SessionHistory,
        session_id: str,
    ):
        self.registry_entry = registry_entry
        self.workspace_dir = workspace_dir
        self.session_history = session_history
        self.session_id = session_id
        self.worker_id = registry_entry.get("id", "omniroute")

        # Discover endpoint and API key from OmniRoute configuration
        self.endpoint = self._discover_endpoint()
        self.api_key = self._discover_api_key()
        self.default_model = registry_entry.get("model", "auto/best-coding")

    def _discover_endpoint(self) -> str:
        """Discover OmniRoute server endpoint from env or config."""
        # Check env vars first
        url = os.environ.get("OMNIROUTE_BASE_URL")
        if url:
            return url.rstrip("/")

        # Check OmniRoute .env file
        env_path = Path.home() / ".omniroute" / ".env"
        if not env_path.exists():
            env_path = Path(r"C:\Users\Omar\.omniroute\.env")

        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("OMNIROUTE_BASE_URL="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return val.rstrip("/")

        # Fallback: try common local ports
        return "http://localhost:20128"

    def _discover_api_key(self) -> str:
        """Discover OmniRoute API key from env or config."""
        key = os.environ.get("OMNIROUTE_API_KEY")
        if key:
            return key

        env_path = Path(r"C:\Users\Omar\.omniroute\.env")
        if not env_path.exists():
            env_path = Path.home() / ".omniroute" / ".env"

        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("OMNIROUTE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")

        return ""

    def health_check(self) -> dict[str, Any]:
        """Check if OmniRoute server is reachable and API key is configured."""
        if not self.api_key:
            return {
                "available": False,
                "error": "No OMNIROUTE_API_KEY configured",
                "method": "api",
                "endpoint": self.endpoint,
            }

        try:
            req = urllib.request.Request(
                f"{self.endpoint}/v1/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp = urllib.request.urlopen(req, timeout=5)
            return {
                "available": True,
                "method": "api",
                "endpoint": self.endpoint,
                "model": self.default_model,
                "mode": "live",
                "status_code": resp.status,
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "method": "api",
                "endpoint": self.endpoint,
            }

    def get_capabilities(self) -> list[str]:
        return self.registry_entry.get("role_ids", [])

    def get_cost_tier(self) -> str:
        return self.registry_entry.get("cost_tier", "unknown")

    def invoke(self, task: dict[str, Any], evidence_path: Path, output_path: Path) -> dict[str, Any]:
        """Invoke the OmniRoute API with the task prompt."""
        prompt = self._build_prompt(task, evidence_path)

        self.session_history.log_event(
            session_id=self.session_id,
            event_type="worker_invoked",
            worker_id=self.worker_id,
            phase="execution",
            payload={"task_id": task.get("id"), "output_path": str(output_path), "model": self.default_model},
        )

        try:
            payload = json.dumps({
                "model": self.default_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 2000,
                "stream": False,
            }).encode()

            req = urllib.request.Request(
                f"{self.endpoint}/v1/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp = urllib.request.urlopen(req, timeout=120)
            body = resp.read().decode()
            parsed = json.loads(body)

            if "choices" not in parsed or not parsed["choices"]:
                return {
                    "success": False,
                    "error": f"No choices in response: {body[:300]}",
                }

            content = parsed["choices"][0]["message"]["content"]
            output = self._parse_output(content)
            output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

            self.session_history.log_event(
                session_id=self.session_id,
                event_type="worker_completed",
                worker_id=self.worker_id,
                phase="execution",
                payload={"task_id": task.get("id"), "output_path": str(output_path)},
            )
            return {"success": True, "output": output, "output_path": str(output_path)}

        except urllib.error.HTTPError as e:
            body = e.read().decode()[:500]
            self.session_history.log_event(
                session_id=self.session_id,
                event_type="worker_failed",
                worker_id=self.worker_id,
                phase="execution",
                payload={"error": body, "http_status": e.code},
            )
            return {"success": False, "error": f"HTTP {e.code}: {body}"}
        except Exception as e:
            self.session_history.log_event(
                session_id=self.session_id,
                event_type="worker_error",
                worker_id=self.worker_id,
                phase="execution",
                payload={"error": str(e)},
            )
            return {"success": False, "error": str(e)}

    def _build_prompt(self, task: dict[str, Any], evidence_path: Path) -> str:
        """Build a research prompt for the OmniRoute worker."""
        evidence_text = ""
        if evidence_path.exists():
            evidence_text = evidence_path.read_text(encoding="utf-8")
        else:
            evidence_text = "[No evidence file provided]"

        return f"""You are a content researcher for the Content Money Engine.

TASK: {task.get('description', 'No description provided')}

EVIDENCE/CONTEXT:
{evidence_text}

OUTPUT: produce a JSON file at {task.get('output_path', 'N/A')} with this exact schema:
{{
  "opportunities": [
    {{
      "keyword": "string — actual search query, not the raw niche",
      "search_volume_estimate": integer,
      "keyword_difficulty": integer (0-100),
      "buyer_intent": "high" | "medium" | "low" | "very_high",
      "intent_signals": ["signal1", "signal2"],
      "competition_level": "low" | "medium" | "high",
      "monetization_concept": "string",
      "monetization_estimate_pct": float,
      "content_type": "string",
      "content_difficulty": "low" | "medium" | "high"
    }}
  ]
}}

IMPORTANT: Output ONLY valid JSON. No markdown, no explanations, no preamble.
"""

    def _parse_output(self, raw: str) -> dict[str, Any]:
        """Parse LLM output into structured format for the ResearcherAgent."""
        raw = raw.strip()

        # Try to parse as JSON directly
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and "opportunities" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown/code blocks
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                parsed = json.loads(raw[start:end])
                if isinstance(parsed, dict) and "opportunities" in parsed:
                    return parsed
            except json.JSONDecodeError:
                pass

        # Fallback: return raw as summary
        return {
            "opportunities": [],
            "raw": raw[:2000],
            "parse_error": "Could not parse JSON output from model",
        }

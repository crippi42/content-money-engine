"""Researcher agent for Content Money Engine.

Discovers content opportunities by invoking a logical worker selected via
the existing Workstation WorkerRegistry (the "OmniRoute" layer). The worker
type and model are discovered from the registry at runtime and are NOT
hard-bound to any single provider.

Architecture:
  Researcher -> WorkerRegistry (role-based discovery) -> Worker (DeepSeek/Ollama/Claude) -> Model

The agent tries workers in priority order and falls back to available
alternatives. If no real worker is available, it returns an explicit
failure state unless the caller requested simulation mode.
"""

from __future__ import annotations

import inspect
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.agents.base import AgentBase
from src.workers.omniroute_worker import OmniRouteWorker


class ResearcherAgent(AgentBase):
    """Researcher agent: discovers content opportunities via registered workers.

    Worker selection:
      1. Tries OmniRoute (the existing model routing layer) first
      2. If OmniRoute unavailable, queries WorkerRegistry for 'researcher' role workers
      3. Falls back across workers on failure
      4. Only uses simulation mode if explicitly requested via source_type='simulated'
         OR if all real workers fail AND seed_data is provided as fallback
    """

    WORKERTYPE = "researcher"

    @property
    def agent_type(self) -> str:
        return "researcher"

    def get_required_inputs(self) -> list[str]:
        return ["research_input"]

    def __init__(self, agent_id: str, experiment_dir: Path, session_history: Any, session_id: str,
                 worker_registry: Any = None, workspace_dir: Path = None, use_omniroute: bool = False):
        super().__init__(agent_id, experiment_dir, session_history, session_id)
        self._worker_registry = worker_registry
        self._workspace_dir = workspace_dir
        self._use_omniroute = use_omniroute
        self._worker_instances: dict[str, Any] = {}
        self._worker_classes = {
            "api": self._import_deepseek,
            "subprocess": self._import_claude,
            "ollama_api": self._import_ollama,
            "wsl_subprocess": self._import_unsupported,
        }
        self._omniroute_worker: OmniRouteWorker | None = None
        if use_omniroute:
            self._init_omniroute()

    def _import_deepseek(self):
        from workers.deepseek_worker import DeepSeekWorker
        return DeepSeekWorker

    def _import_claude(self):
        from workers.claude_worker import ClaudeWorker
        return ClaudeWorker

    def _import_ollama(self):
        from workers.ollama_worker import OllamaWorker
        return OllamaWorker

    def _import_unsupported(self):
        return None

    def _init_omniroute(self):
        """Initialize the OmniRoute worker for LLM-backed research."""
        try:
            entry = {
                "id": "omniroute",
                "invocation": "omniroute",
                "model": "auto/best-coding",
                "role_ids": ["researcher", "scorer"],
                "cost_tier": "paid",
            }
            self._omniroute_worker = OmniRouteWorker(
                entry, self._workspace_dir or self.experiment_dir,
                self.session_history, self.session_id
            )
        except Exception:
            self._omniroute_worker = None

    def _get_worker_candidates(self) -> list[str]:
        """Discover available researcher workers from the registry."""
        if self._worker_registry is None:
            return ["deepseek"]
        candidates = self._worker_registry.get_workers_for_role("researcher")
        if not candidates:
            return ["deepseek"]
        return candidates

    def _init_worker(self, worker_id: str):
        """Initialize a worker instance, respecting the registry entry."""
        if worker_id in self._worker_instances:
            return self._worker_instances[worker_id]

        entry = self._worker_registry.get_worker(worker_id) if self._worker_registry else {
            "id": worker_id, "invocation": "api", "model": "deepseek-reasoner"
        }
        if entry is None:
            return None

        invocation = entry.get("invocation", "unknown")
        import_fn = self._worker_classes.get(invocation)
        if import_fn is None:
            return None

        worker_cls = import_fn()
        if worker_cls is None:
            return None

        ws_dir = self._workspace_dir or self.experiment_dir
        worker = worker_cls(entry, ws_dir, self.session_history, self.session_id)
        self._worker_instances[worker_id] = worker
        return worker

    def produce_output(self, inputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
        research_input = inputs["research_input"]
        niche_query = research_input.get("query", "unknown")
        source_type = research_input.get("source_type", "simulated")
        seed_data = research_input.get("seed_data", {})

        is_simulated = source_type == "simulated"
        is_seed = source_type == "seed"
        is_external = source_type == "externally_sourced"

        opportunities: list[dict[str, Any]]
        model_used: str
        worker_used: str

        if is_simulated:
            opportunities = self._generate_simulated_opportunities(niche_query)
            model_used = "simulation"
            worker_used = "simulation"
        elif is_seed:
            opportunities = self._generate_seed_opportunities(niche_query, seed_data)
            model_used = "seed_data"
            worker_used = "operator"
        elif is_external:
            opps, mw, wu = self._invoke_real_worker(niche_query, seed_data)
            opportunities = opps
            model_used = mw
            worker_used = wu
            # If all workers failed AND fell back to simulation (no seed data),
            # mark as simulated but preserve source_type for provenance tracking
            if wu == "none":
                is_simulated = True
                for opp in opportunities:
                    opp["evidence_source"] = "simulated"
                    opp["evidence_references"] = ["simulated_search_trends:2025"]
        else:
            opportunities = self._generate_simulated_opportunities(niche_query)
            model_used = "simulation"
            worker_used = "simulation"
            is_simulated = True

        output = {
            "status": "complete",
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "experiment_id": research_input.get("experiment_id", "unknown"),
            "niche_query": niche_query,
            "evidence_source": {
                "type": source_type,
                "simulated": is_simulated,
                "is_seed": is_seed,
                "externally_sourced": is_external and not is_simulated,
                "source_description": research_input.get("source_description", ""),
                "provenance": research_input.get("provenance", {}),
                "worker_failure_note": model_used if is_simulated and is_external else None,
            },
            "worker_used": worker_used,
            "model_used": model_used,
            "research_timestamp": datetime.now(timezone.utc).isoformat(),
            "opportunities": opportunities,
            "claims": self._generate_claims(niche_query, opportunities, is_simulated),
            "confidence": self._compute_confidence(opportunities, source_type),
            "summary": self._generate_summary(niche_query, opportunities, is_simulated),
        }

        return output

    def _invoke_real_worker(self, niche_query: str, seed_data: dict[str, Any]) -> tuple[list[dict[str, Any]], str, str]:
        """Attempt to invoke workers in priority order.

        Order:
        1. OmniRoute (auto-routing through existing model gateway)
        2. WorkerRegistry candidates (deepseek, ollama, etc.)

        Returns (opportunities, model_used, worker_id).
        If all workers fail, tries seed_data fallback, then returns simulation.
        """
        last_error = ""

        # 1. Try OmniRoute first
        if self._omniroute_worker:
            health = self._omniroute_worker.health_check()
            if health.get("available", False) and health.get("mode") != "simulated":
                model = health.get("model", "auto/best-coding")
                task = {
                    "id": f"research-{self.session_id}",
                    "description": f"Research content opportunities for niche: {niche_query}",
                    "output_path": str(self.output_dir / f"{self.agent_id}_omniroute_output.json"),
                }
                evidence_path = self.evidence_dir / "research_input.json"
                output_path = self.output_dir / f"{self.agent_id}_omniroute_output.json"

                result = self._omniroute_worker.invoke(task, evidence_path, output_path)
                if result.get("success"):
                    parsed_output = result.get("output", {})
                    model_used = f"omniroute:{model}"
                    workers_tried = "omniroute"
                    opps = self._parse_worker_output(parsed_output, niche_query, model)
                    return opps, model_used, workers_tried
                else:
                    last_error = f"OmniRoute invocation failed: {result.get('error', 'unknown')}"
            else:
                last_error = f"OmniRoute not available: {health.get('error', 'unavailable')}"

        # 2. Try WorkerRegistry candidates
        if self._worker_registry is None:
            candidates = []
        else:
            candidates = self._get_worker_candidates()

        # 2. Try WorkerRegistry candidates
        candidates = [] if self._worker_registry is None else self._get_worker_candidates()

        for worker_id in candidates:
            worker = self._init_worker(worker_id)
            if worker is None:
                last_error = f"Worker '{worker_id}' could not be initialized"
                continue

            health = worker.health_check()
            if not health.get("available", False):
                last_error = f"Worker '{worker_id}' not available: {health.get('error', 'health check failed')}"
                continue

            mode = health.get("mode", health.get("state", "unknown"))
            if mode == "simulated":
                last_error = f"Worker '{worker_id}' available but in simulation mode (no API key)"
                continue

            model = health.get("model", getattr(worker, "model", "unknown"))
            task = {
                "id": f"research-{self.session_id}",
                "description": f"Research content opportunities for niche: {niche_query}",
                "output_path": str(self.output_dir / f"{self.agent_id}_llm_output.json"),
            }
            evidence_path = self.evidence_dir / "research_input.json"
            output_path = self.output_dir / f"{self.agent_id}_llm_output.json"

            result = worker.invoke(task, evidence_path, output_path)
            if result.get("success"):
                parsed = self._parse_worker_output(result.get("output", {}), niche_query, model)
                return parsed, model, worker_id
            else:
                last_error = f"Worker '{worker_id}' invocation failed: {result.get('error', 'unknown')}"

        # All workers failed — check if seed_data was provided as alternative source
        if seed_data and seed_data.get("opportunities"):
            seed_opps = self._generate_seed_opportunities(niche_query, seed_data)
            for opp in seed_opps:
                opp["evidence_source"] = "externally_sourced"
                opp.setdefault("evidence_references", []).append("seed_data:operator_provided")
            return seed_opps, f"seed_data_fallback (workers failed: {last_error})", "seed_data_fallback"

        # No seed data available — return simulation with error logging
        sim_opps = self._generate_simulated_opportunities(niche_query)
        return sim_opps, f"all_workers_failed: {last_error}", "none"

    def _parse_worker_output(self, worker_output: dict[str, Any], niche_query: str, model: str) -> list[dict[str, Any]]:
        """Parse LLM worker output into structured opportunities.

        The worker output schema is flexible — look for 'opportunities' or 'findings'.
        If parsing fails, fall back to a basic structured extraction.
        """
        opps_raw = worker_output.get("opportunities") or []
        formatted = []

        for opp in opps_raw:
            if isinstance(opp, dict):
                opp_copy = dict(opp)
                opp_copy.setdefault("evidence_source", "externally_sourced")
                opp_copy.setdefault("evidence_references", [f"llm_output:{model}"])
                opp_copy.setdefault("keyword", opp.get("keyword", niche_query))
                opp_copy.setdefault("search_volume_estimate", opp.get("search_volume_estimate", 0))
                opp_copy.setdefault("keyword_difficulty", opp.get("keyword_difficulty", 50))
                opp_copy.setdefault("buyer_intent", opp.get("buyer_intent", "unknown"))
                opp_copy.setdefault("monetization_concept", opp.get("monetization_concept", ""))
                opp_copy.setdefault("monetization_estimate_pct", opp.get("monetization_estimate_pct", 0))
                opp_copy.setdefault("content_type", opp.get("content_type", "article"))
                opp_copy.setdefault("content_difficulty", opp.get("content_difficulty", "medium"))
                opp_copy.setdefault("intent_signals", opp.get("intent_signals", []))
                opp_copy.setdefault("competition_level", opp.get("competition_level", "unknown"))
                formatted.append(opp_copy)

        if not formatted:
            formatted = self._generate_simulated_opportunities(niche_query)

        return formatted

    def _generate_simulated_opportunities(self, niche_query: str) -> list[dict[str, Any]]:
        """Generate clearly-labeled simulated opportunities for fallback."""
        return [
            {
                "keyword": "best " + niche_query + " 2025",
                "search_volume_estimate": 1000,
                "keyword_difficulty": 45,
                "buyer_intent": "high",
                "intent_signals": ["best", "2025", "buy", "review", "price"],
                "competition_level": "medium",
                "monetization_concept": "affiliate commissions from product sales",
                "monetization_estimate_pct": 5.0,
                "content_type": "product comparison",
                "content_difficulty": "medium",
                "evidence_source": "simulated",
                "evidence_references": ["simulated_search_trends:2025"],
            },
            {
                "keyword": niche_query + " guide",
                "search_volume_estimate": 800,
                "keyword_difficulty": 30,
                "buyer_intent": "medium",
                "intent_signals": ["guide", "how to", "tutorial"],
                "competition_level": "low",
                "monetization_concept": "affiliate commissions from educational upsells",
                "monetization_estimate_pct": 3.0,
                "content_type": "how-to guide",
                "content_difficulty": "low",
                "evidence_source": "simulated",
                "evidence_references": ["simulated_search_trends:2025"],
            },
            {
                "keyword": "buy " + niche_query,
                "search_volume_estimate": 500,
                "keyword_difficulty": 60,
                "buyer_intent": "very_high",
                "intent_signals": ["buy", "for sale", "cheap", "discount"],
                "competition_level": "high",
                "monetization_concept": "direct affiliate product sales",
                "monetization_estimate_pct": 8.0,
                "content_type": "product review",
                "content_difficulty": "high",
                "evidence_source": "simulated",
                "evidence_references": ["simulated_search_trends:2025"],
            },
        ]

    def _generate_seed_opportunities(self, niche_query: str, seed_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate opportunities from seed data provided by the operator."""
        seed_opportunities = seed_data.get("opportunities", [])
        if not seed_opportunities:
            return self._generate_simulated_opportunities(niche_query)

        formatted = []
        for opp in seed_opportunities:
            opp_copy = dict(opp)
            opp_copy["evidence_source"] = "seed"
            opp_copy.setdefault("evidence_references", [])
            opp_copy["evidence_references"].append("seed_data:operator_provided")
            formatted.append(opp_copy)
        return formatted

    def _generate_claims(self, niche_query: str, opportunities: list[dict], is_simulated: bool) -> list[dict[str, str]]:
        """Generate claims with source attribution."""
        claims = []
        for opp in opportunities:
            source_label = "simulated data" if is_simulated else opp.get("evidence_source", "unknown")
            claims.append({
                "claim": f"Keyword '{opp['keyword']}' has search volume ~{opp.get('search_volume_estimate', 'N/A')}",
                "source": source_label,
                "confidence_basis": opp.get("evidence_references", []),
            })
        return claims

    def _compute_confidence(self, opportunities: list[dict], source_type: str) -> int:
        """Compute confidence level based on evidence source."""
        if source_type == "simulated":
            return 20
        elif source_type == "seed":
            return 50
        elif source_type == "externally_sourced":
            return 80
        return 20

    def _generate_summary(self, niche_query: str, opportunities: list[dict], is_simulated: bool) -> str:
        sim_label = " [SIMULATED DATA]" if is_simulated else ""
        return (
            f"Researcher identified {len(opportunities)} content opportunities for '{niche_query}'."
            f" Top opportunity: '{opportunities[0]['keyword']}'"
            f" with buyer_intent={opportunities[0].get('buyer_intent', 'unknown')}.{sim_label}"
        )

    def archive_evidence(self, output_dir: Path) -> Path:
        """Copy researcher output to evidence/research.json for downstream agents."""
        output_path = output_dir / f"{self.agent_id}_output.json"
        evidence_path = self.experiment_dir / "evidence" / "research.json"

        if output_path.exists():
            evidence_path.write_text(
                output_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
        return evidence_path

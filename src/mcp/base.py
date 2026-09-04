"""MCP abstraction layer for Content Money Engine.

NO MCP servers are installed or configured in Phase A. This module defines
the abstract interfaces that concrete MCP servers will implement when
configured by the operator in a future phase.

The workstation core remains independent of specific MCP providers.

C1: MCPRegistry now loads config/mcp_config.yaml to resolve concrete
server bindings. All interfaces remain unconfigured (concrete_server: null).
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import yaml


class AbstractMCPServer(ABC):
    """Base interface for all MCP server wrappers.

    Concrete implementations are configured via config/mcp_config.yaml
    in a future phase. No servers are auto-installed.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._initialized = False

    @property
    def server_name(self) -> str:
        """Human-readable name of this MCP server."""
        return self.__class__.__name__

    @property
    def capabilities(self) -> list[str]:
        """List of capabilities this server provides."""
        return []

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the MCP server connection.

        Returns True if available, False if not configured or unavailable.
        """

    @abstractmethod
    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool on the MCP server.

        Returns a dict with 'success', 'result', and optional 'error'.
        """

    @property
    def requires_approval(self) -> bool:
        """Whether operations on this MCP server require §26 human approval.

        Defaults to False. Override in subclasses for approval-gated MCPs.
        """
        return False


class ResearchMCP(AbstractMCPServer):
    """Web research and data extraction MCP interface.

    Provides: web_fetch, web_search, structured_extract.

    Concrete server: TBD (firecrawl-mcp, exa-mcp, or custom scraper).
    Phase A status: NOT CONFIGURED.
    """

    @property
    def server_name(self) -> str:
        return "research_mcp"

    @property
    def capabilities(self) -> list[str]:
        return ["web_fetch", "web_search", "structured_extract"]

    def initialize(self) -> bool:
        self._initialized = False
        return False

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": False,
            "error": "MCP server not configured for research_mcp",
            "tool": tool_name,
        }


class AffiliateMCP(AbstractMCPServer):
    """Affiliate product and commission research MCP interface.

    Provides: product_search, commission_lookup, program_details.

    Concrete server: TBD (ShareASale, CJ, Impact API MCP).
    Phase A status: NOT CONFIGURED.
    """

    @property
    def server_name(self) -> str:
        return "affiliate_mcp"

    @property
    def capabilities(self) -> list[str]:
        return ["product_search", "commission_lookup", "program_details"]

    def initialize(self) -> bool:
        self._initialized = False
        return False

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": False,
            "error": "MCP server not configured for affiliate_mcp",
            "tool": tool_name,
        }


class ContentMCP(AbstractMCPServer):
    """Content generation MCP interface.

    Provides: generate_text, plagiarism_check, format_content.

    Concrete server: TBD (local Ollama, Claude API, or dedicated MCP).
    Phase A status: NOT CONFIGURED.
    """

    @property
    def server_name(self) -> str:
        return "content_mcp"

    @property
    def capabilities(self) -> list[str]:
        return ["generate_text", "plagiarism_check", "format_content"]

    def initialize(self) -> bool:
        self._initialized = False
        return False

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": False,
            "error": "MCP server not configured for content_mcp",
            "tool": tool_name,
        }


class PublishingMCP(AbstractMCPServer):
    """CMS and content publishing MCP interface. — REQUIRES §26 APPROVAL.

    Provides: publish_post, update_post, manage_media.

    Concrete server: TBD (WordPress, Ghost, etc.).
    Phase A status: NOT CONFIGURED.

    SECURITY: All operations in this interface require §26 human approval
    via the workstation's Controlled Dispatcher before execution.
    """

    @property
    def server_name(self) -> str:
        return "publishing_mcp"

    @property
    def capabilities(self) -> list[str]:
        return ["publish_post", "update_post", "manage_media"]

    @property
    def requires_approval(self) -> bool:
        return True

    def initialize(self) -> bool:
        self._initialized = False
        return False

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": False,
            "error": "MCP server not configured for publishing_mcp. Requires §26 approval.",
            "tool": tool_name,
        }


class AnalyticsMCP(AbstractMCPServer):
    """Analytics and performance tracking MCP interface.

    Provides: fetch_metrics, fetch_revenue, fetch_traffic.

    Concrete server: TBD (Google Analytics, Plausible, etc.).
    Phase A status: NOT CONFIGURED.
    """

    @property
    def server_name(self) -> str:
        return "analytics_mcp"

    @property
    def capabilities(self) -> list[str]:
        return ["fetch_metrics", "fetch_revenue", "fetch_traffic"]

    def initialize(self) -> bool:
        self._initialized = False
        return False

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": False,
            "error": "MCP server not configured for analytics_mcp",
            "tool": tool_name,
        }


class MCPRegistry:
    """Registry mapping abstract MCP interfaces to concrete implementations.

    In Phase A, all interfaces report as not-configured. When MCP servers
    are configured in a future phase, the operator specifies which concrete
    server implements each abstract interface via config/mcp_config.yaml.

    C1: Config loading is now implemented. The registry reads
    config/mcp_config.yaml at construction time and reflects the
    concrete_server field for each interface.
    """

    _INTERFACES = {
        "research": ResearchMCP,
        "affiliate": AffiliateMCP,
        "content": ContentMCP,
        "publishing": PublishingMCP,
        "analytics": AnalyticsMCP,
    }

    def __init__(self, config_path: str | os.PathLike[str] | None = None):
        self._config_path = Path(config_path) if config_path else None
        self._config: dict[str, Any] = {}
        self._servers: dict[str, AbstractMCPServer] = {}
        self._load_config()

    def _load_config(self):
        """Load MCP interface configuration from YAML.

        Parses config/mcp_config.yaml (or the path provided to __init__)
        and stores the parsed config. Each interface's concrete_server
        field determines whether a server is configured.
        """
        if self._config_path is None:
            return
        if not self._config_path.exists():
            return
        try:
            content = self._config_path.read_text(encoding="utf-8")
            self._config = yaml.safe_load(content) or {}
        except (yaml.YAMLError, OSError):
            self._config = {}

    @property
    def config(self) -> dict[str, Any]:
        """Return the loaded MCP configuration dict."""
        return self._config.copy()

    def is_interface_configured(self, interface_name: str) -> bool:
        """Check if a concrete MCP server is configured for an interface."""
        if interface_name not in self._INTERFACES:
            return False
        interfaces = self._config.get("interfaces", {})
        entry = interfaces.get(interface_name, {})
        return entry.get("concrete_server") is not None

    def get_server(self, interface_name: str) -> AbstractMCPServer | None:
        """Get an MCP server by interface name.

        Returns an instance of the abstract interface class. The
        returned server's initialize() method reflects whether a
        concrete server is configured.
        """
        cls = self._INTERFACES.get(interface_name)
        if cls is None:
            return None
        if interface_name not in self._servers:
            entry = self._config.get("interfaces", {}).get(interface_name, {})
            self._servers[interface_name] = cls(entry or {})
        return self._servers[interface_name]

    def list_interfaces(self) -> list[str]:
        """List all available MCP interface names."""
        return list(self._INTERFACES.keys())

    def list_configured_servers(self) -> dict[str, bool]:
        """Return which interfaces have concrete servers configured.

        Reads the loaded config to determine status. In Phase A, all
        return False (no concrete servers installed).
        """
        return {
            name: self.is_interface_configured(name)
            for name in self._INTERFACES
        }

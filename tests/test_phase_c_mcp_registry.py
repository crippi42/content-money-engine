"""C1 tests — MCP registry/interface resolution.

Tests cover:
- MCPRegistry config loading from config/mcp_config.yaml
- All interfaces correctly report not-configured
- Registry returns abstract server instances
- Config-based interface checking
- Missing config path handling
- Registry compatibility with future C2 ContentAgent integration
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Path setup
_WORKSTATION_ROOT = Path(__file__).resolve().parents[2] / "multi-ai-workstation-poc"
sys.path.insert(0, str(_WORKSTATION_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mcp.base import (
    MCPRegistry,
    ResearchMCP,
    AffiliateMCP,
    ContentMCP,
    PublishingMCP,
    AnalyticsMCP,
    AbstractMCPServer,
)


# ─── Fixtures ───


@pytest.fixture
def cme_mcp_config():
    """Path to the CME mcp_config.yaml."""
    return Path(__file__).resolve().parents[1] / "config" / "mcp_config.yaml"


@pytest.fixture
def registry(cme_mcp_config):
    """MCPRegistry loaded with the real CME config/mcp_config.yaml."""
    return MCPRegistry(cme_mcp_config)


# ─── Config Loading Tests ───


def test_registry_loads_config_from_yaml(cme_mcp_config):
    """MCPRegistry should parse config/mcp_config.yaml and store the config."""
    reg = MCPRegistry(cme_mcp_config)
    config = reg.config
    assert "interfaces" in config
    assert "research" in config["interfaces"]
    assert "content" in config["interfaces"]
    assert "publishing" in config["interfaces"]
    assert "analytics" in config["interfaces"]
    assert "affiliate" in config["interfaces"]


def test_registry_all_interfaces_not_configured(cme_mcp_config):
    """All MCP interfaces should report concrete_server: null in Phase A/C1."""
    reg = MCPRegistry(cme_mcp_config)
    configured = reg.list_configured_servers()
    for name, is_configured in configured.items():
        assert is_configured is False, f"Interface '{name}' should not be configured in C1"


def test_registry_config_has_correct_version(cme_mcp_config):
    """Config should have version 1.0."""
    reg = MCPRegistry(cme_mcp_config)
    assert reg.config.get("version") == "1.0"


def test_registry_config_interfaces_have_concrete_null(cme_mcp_config):
    """Every interface in config should have concrete_server: null."""
    reg = MCPRegistry(cme_mcp_config)
    interfaces = reg.config.get("interfaces", {})
    assert len(interfaces) == 5

    for name, entry in interfaces.items():
        assert "abstract_type" in entry, f"Interface '{name}' missing abstract_type"
        assert "concrete_server" in entry, f"Interface '{name}' missing concrete_server"
        assert entry["concrete_server"] is None, f"Interface '{name}' should have concrete_server: null in C1"


# ─── Interface Resolution Tests ───


def test_registry_get_server_returns_correct_types(cme_mcp_config):
    """get_server should return instances of the correct abstract classes."""
    reg = MCPRegistry(cme_mcp_config)

    assert isinstance(reg.get_server("research"), ResearchMCP)
    assert isinstance(reg.get_server("affiliate"), AffiliateMCP)
    assert isinstance(reg.get_server("content"), ContentMCP)
    assert isinstance(reg.get_server("publishing"), PublishingMCP)
    assert isinstance(reg.get_server("analytics"), AnalyticsMCP)


def test_registry_get_server_unknown_interface(cme_mcp_config):
    """get_server for unknown interface returns None."""
    reg = MCPRegistry(cme_mcp_config)
    assert reg.get_server("nonexistent") is None


def test_registry_get_server_returns_same_instance(cme_mcp_config):
    """get_server should return the same cached instance on repeated calls."""
    reg = MCPRegistry(cme_mcp_config)
    server1 = reg.get_server("research")
    server2 = reg.get_server("research")
    assert server1 is server2


# ─── Interface State Tests ───


def test_all_mcp_servers_initialize_returns_false(cme_mcp_config):
    """In C1, no MCP server should report as available."""
    reg = MCPRegistry(cme_mcp_config)
    for name in reg.list_interfaces():
        server = reg.get_server(name)
        assert server is not None
        assert not server.initialize(), f"MCP server '{name}' should not be available in C1"


def test_all_mcp_servers_are_abstract_subclasses(cme_mcp_config):
    """All returned servers should be instances of AbstractMCPServer."""
    reg = MCPRegistry(cme_mcp_config)
    for name in reg.list_interfaces():
        server = reg.get_server(name)
        assert isinstance(server, AbstractMCPServer), f"Interface '{name}' should be an AbstractMCPServer"


def test_publishing_mcp_requires_approval(cme_mcp_config):
    """PublishingMCP should be flagged as requiring approval."""
    reg = MCPRegistry(cme_mcp_config)
    publishing = reg.get_server("publishing")
    assert publishing is not None
    assert publishing.requires_approval is True


def test_research_content_affiliate_analytics_do_not_require_approval(cme_mcp_config):
    """Non-publishing MCP interfaces should not require approval."""
    reg = MCPRegistry(cme_mcp_config)
    for name in ["research", "content", "affiliate", "analytics"]:
        server = reg.get_server(name)
        assert server is not None
        assert server.requires_approval is False, f"Interface '{name}' should not require approval"


# ─── Config Path Handling Tests ───


def test_registry_no_config_path_defaults_to_empty():
    """MCPRegistry with no config path should work but report nothing configured."""
    reg = MCPRegistry(None)
    assert reg.config == {}
    assert all(v is False for v in reg.list_configured_servers().values())


def test_registry_missing_config_file_defaults_to_empty(tmp_path):
    """MCPRegistry with nonexistent config path should not crash."""
    reg = MCPRegistry(tmp_path / "nonexistent.yaml")
    assert reg.config == {}
    assert all(v is False for v in reg.list_configured_servers().values())


# ─── C2 Compatibility Tests ───


def test_registry_list_interfaces_returns_all_expected(cme_mcp_config):
    """list_interfaces should return all 5 expected interface names."""
    reg = MCPRegistry(cme_mcp_config)
    interfaces = reg.list_interfaces()
    assert set(interfaces) == {"research", "affiliate", "content", "publishing", "analytics"}


def test_registry_is_interface_configured_consistent_with_list(cme_mcp_config):
    """is_interface_configured should be consistent with list_configured_servers."""
    reg = MCPRegistry(cme_mcp_config)
    configured = reg.list_configured_servers()
    for name in reg.list_interfaces():
        assert reg.is_interface_configured(name) == configured[name]


def test_content_mcp_ready_for_c2_integration(cme_mcp_config):
    """Verify ContentMCP is resolvable and has the correct capabilities for C2 ContentAgent."""
    reg = MCPRegistry(cme_mcp_config)
    content_mcp = reg.get_server("content")
    assert content_mcp is not None
    assert isinstance(content_mcp, ContentMCP)
    assert "generate_text" in content_mcp.capabilities
    assert "plagiarism_check" in content_mcp.capabilities
    assert "format_content" in content_mcp.capabilities
    # In C1, server is not configured
    assert reg.is_interface_configured("content") is False
    assert content_mcp.initialize() is False


def test_research_mcp_ready_for_c2_integration(cme_mcp_config):
    """Verify ResearchMCP is resolvable with correct capabilities for externally_sourced research."""
    reg = MCPRegistry(cme_mcp_config)
    research_mcp = reg.get_server("research")
    assert research_mcp is not None
    assert isinstance(research_mcp, ResearchMCP)
    assert "web_fetch" in research_mcp.capabilities
    assert "web_search" in research_mcp.capabilities
    assert "structured_extract" in research_mcp.capabilities
    assert reg.is_interface_configured("research") is False
    assert research_mcp.initialize() is False


# ─── Backward Compatibility Tests ───


def test_registry_backward_compatible_no_config_path():
    """Existing tests that construct MCPRegistry() with no args should still work."""
    reg = MCPRegistry()
    assert reg.list_interfaces() == ["research", "affiliate", "content", "publishing", "analytics"]
    assert all(v is False for v in reg.list_configured_servers().values())


def test_registry_backward_compatible_get_server_no_config():
    """get_server with no config should still return instances."""
    reg = MCPRegistry()
    server = reg.get_server("research")
    assert server is not None
    assert isinstance(server, ResearchMCP)
    assert server.initialize() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

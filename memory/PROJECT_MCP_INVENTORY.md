# Content Money Engine — MCP Tool Inventory

## Status (Phase A)
**No MCP servers installed.** No external accounts connected.

## Purpose
This file tracks the MCP tool integration requirements for Content Money Engine. MCP servers will be added here as a registry of declared interfaces — concrete server implementations are configured by the operator, never auto-installed.

## MCP Architecture Overview
- `config/mcp_config.yaml` — Declares required MCP interfaces (abstract contracts)
- `src/mcp/base.py` — Abstract base class defining the MCP server interface
- `src/mcp/registry.py` — Maps abstract interfaces to concrete server implementations (C1: registry loader now reads config)
- Concrete MCP servers are loaded at runtime via configuration, not hardcoded

## MCP Capability Requirements

### MVP Required
| Capability | Abstract Interface | Concrete Server (TBD) | §26 Required? |
|---|---|---|---|
| Web research/scraping | `research_mcp` | firecrawl-mcp or similar (TBD) | ❌ No |
| Affiliate product research | `affiliate_mcp` | ShareASale/CJ/Impact API MCP (TBD) | ❌ No |
| Content generation | `content_mcp` | Local Ollama or existing workers (TBD) | ❌ No |
| Analytics fetching | `analytics_mcp` | Plausible/GA MCP (TBD) | ❌ No |

### Post-MVP (§26 Gated)
| Capability | Abstract Interface | §26 Required? |
|---|---|---|
| CMS publishing | `publishing_mcp` | ✅ Yes |
| Social media posting | `social_mcp` | ✅ Yes |
| Domain/hosting management | `infrastructure_mcp` | ✅ Yes |

## Current Servers Installed
None. All interfaces report `concrete_server: null` in config. The MCPRegistry loader reads config and correctly reports all interfaces as not-configured.

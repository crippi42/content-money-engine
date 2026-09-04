"""Opportunity Registry + Selection layer for Content Money Engine.

Provides:
- OpportunityRegistry: loads, indexes, and queries scored opportunities
- OpportunitySelector: selects one opportunity from the registry using a strategy

This is intentionally minimal and follows existing CME patterns:
- JSON evidence I/O via experiment_dir / evidence/
- No new dependencies
- No MCP server required
"""

from __future__ import annotations

from src.opportunities.registry import (
    Opportunity,
    OpportunityRegistry,
    NoQualifiedOpportunityError,
)
from src.opportunities.selector import (
    OpportunitySelector,
)

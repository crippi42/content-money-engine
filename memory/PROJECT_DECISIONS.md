# Content Money Engine — Project Decisions

## Recorded Decisions

### DECISION-001 — Project Location
**Date:** 2026-08-31  
**Rationale:** Dedicated top-level directory at `C:\Users\Omar\content-money-engine`, as a peer to Prospector and Amazon Money Auditor. The Multi-AI Workstation at `C:\Users\Omar\multi-ai-workstation-poc` remains the platform/infrastructure layer.  
**Affects:** All project paths, config references.  
**Status:** Approved by Omar (Phase A go-ahead).

### DECISION-002 — Agent Model
**Date:** 2026-08-31  
**Rationale:** The 5 conceptual agents (Researcher, Opportunity Scorer, Writer/Creator, Publisher, Analyst) will be implemented as separate workers within a new Content Money Engine room in the workstation.  
**Affects:** Worker registry configuration, agent code structure.  
**Status:** Approved by Omar (Phase A go-ahead).

### DECISION-003 — §26 Approval Gate Applies to All External Actions
**Date:** 2026-08-31  
**Rationale:** Research and drafting can be automated, but publishing, distribution, account changes, and financial commitments require human approval via the §26 Controlled Dispatcher.  
**Affects:** Agent design — agents produce artifacts, not external actions.  
**Status:** Approved.

### DECISION-004 — MCP as First-Class Integration Layer
**Date:** 2026-08-31  
**Rationale:** MCP provides the tool integration interface. The workstation core remains independent of specific MCP providers; CME defines required MCP interfaces. No MCP servers installed in Phase A.  
**Affects:** MCP architecture, provider selection.  
**Status:** Approved.

### DECISION-005 — MVP Scoped to Single Niche
**Date:** 2026-08-31  
**Rationale:** Start with 1 niche → limited opportunities → limited content → 1 publishing channel → measurable results.  
**Affects:** MVP scope.  
**Status:** Approved.

### DECISION-006 — CMOrchestrator Extends Orchestrator
**Date:** 2026-08-31  
**Rationale:** Reuse existing workstation Orchestrator via inheritance/composition. Do not duplicate §24-§26 infrastructure. CMOrchestrator adds content-specific phases (Research → Score → Create → Publish → Analyze → Feedback).  
**Affects:** Code architecture.  
**Status:** Approved.

### DECISION-007 — ACTIVE_PROJECT.md Not Changed
**Date:** 2026-08-31  
**Rationale:** CME is an independently registered project. The global ACTIVE_PROJECT.md remains pointing to the current active project. CME uses explicit project identity/authorization.  
**Affects:** Project activation.  
**Status:** Approved.

### DECISION-008 — Phase A Scaffolding Only
**Date:** 2026-08-31  
**Rationale:** Establish project structure, integration boundaries, and configuration. No agent implementation, no MCP installation, no external accounts, no autonomous loops.  
**Affects:** Implementation scope for this session.  
**Status:** Approved by Omar (Phase A go-ahead).

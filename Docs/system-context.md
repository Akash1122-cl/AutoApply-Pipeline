# System Context Diagram — AutoApply v1

Phase 0 artifact: high-level boundaries between orchestrator, agents, humans, and external systems.

## Textual Context

- **Human:** Reviews CP1/CP2, edits Sheet actions and approvals.
- **Orchestrator:** Scheduler-driven controller driving agents and checkpoints.
- **Agents 1–4 / 3b:** Domain workers reading/writing Pipeline Tracker per contracts.
- **Google Workspace:** Drive MCP + Sheets/Docs for pipeline state and CV artifacts.
- **Third-party APIs:** Job boards, enrichment, SerpAPI, Anthropic, optional Slack/email webhooks.
- **Automation:** Playwright for portals where permitted; manual queue when not.

## Mermaid Diagram

```mermaid
flowchart TB
  subgraph Human
    U[User]
  end

  subgraph AutoApply
    O[Orchestrator main.py]
    A1[Agent 1 Scout and Qualify]
    A2[Agent 2 Contact Discovery]
    A3[Agent 3 Content Generation]
    A3b[Agent 3b ATS Reviewer]
    A4[Agent 4 Execution and Tracking]
    O --> A1
    O --> A2
    O --> A3
    O --> A3b
    O --> A4
  end

  subgraph StateAndArtifacts
    S[(Job Pipeline Tracker Sheet)]
    D[Drive Docs CV artifacts]
  end

  subgraph ReadOnlyInputs
    MCV[Master CV Doc]
    AB[Accomplishments Bank Sheet]
  end

  subgraph External
    JB[Job Sources APIs and Scrapes]
    ENR[Hunter Apollo etc]
    LLM[Anthropic Claude API]
    GW[Gmail MCP]
    LI[LinkedIn MCP Playwright]
    NT[Email Slack Notifications]
  end

  U <-->|CP1 CP2 Sheet edits| S
  A1 --> JB
  A1 --> S
  A2 --> ENR
  A2 --> S
  A3 --> MCV
  A3 --> AB
  A3 --> D
  A3 --> S
  A3b --> LLM
  A3b --> D
  A3b --> S
  A4 --> LI
  A4 --> GW
  A4 --> S
  O --> NT
  O --> S
```

---

## Revision History

| Date | Change |
|------|--------|
| 2026-05-03 | Initial Phase 0 diagram |

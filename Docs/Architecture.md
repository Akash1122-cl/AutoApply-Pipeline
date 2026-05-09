# AutoApply Architecture (Phase-wise)

## 1) Vision and Problem Context

AutoApply is a single-user, multi-agent system that automates the Associate Product Manager (APM) job application lifecycle, while preserving strict human control at critical checkpoints.
The architecture is designed for:

- Maximum qualified job reach across India, Europe, and SEA
- ATS-optimized, personalized applications
- Zero fabricated claims in CV and outreach
- Reliable daily operations with clear state tracking and auditability

Core runtime model: **Orchestrator + 5 specialized agents + Google Sheet state machine + approval gates**.

---

## 2) Target State Architecture

### Core Components

1. **Orchestrator (`main.py`)**
   - Owns scheduling, workflow progression, state enforcement, retries policy, and daily reporting.
   - Triggers and sequences all agents based on row status in the Pipeline Tracker.

2. **Agent 1: Scout & Qualify**
   - Discovers jobs from multiple sources.
   - Scores each role (`fit_score`) and writes shortlisted rows.

3. **Agent 2: Contact Discovery**
   - Finds recruiter/hiring manager contacts and verifies work email quality.

4. **Agent 3: Content Generation**
   - Creates tailored CV + cold email + LinkedIn DM per approved row.
   - Uses only Master CV + Accomplishments Bank as source truth.

5. **Agent 3b: ATS Reviewer**
   - Evaluates CV ATS readiness and controls revision loop (max 2).

6. **Agent 4: Execution & Tracking**
   - Executes application + outreach only after human approval and ATS pass.
   - Monitors responses and updates final states.

7. **Shared State Layer**
   - Google Sheet (`Job Pipeline Tracker`) acts as central state machine.
   - Read/write by all agents with row-level status progression.
   - Concurrency-safe writes use optimistic locking (`updated_at` and optional `row_version`).

8. **Input Knowledge Layer (Read-only)**
   - Master CV (Google Doc)
   - Accomplishments Bank (Google Sheet)

9. **Notification Layer**
   - CP1 digest, CP2 digest, daily summary (email/Slack configurable)

---

## 2.1) Infrastructure and Deployment Baseline

### Hosting Environment (v1 recommendation)

- Runtime: single worker process on VPS or containerized service
- Scheduler: **GitHub Actions cron** (simple v1) or **AWS EventBridge / GCP Cloud Scheduler** (cloud-native option)
- Time handling: scheduler configured in UTC; orchestrator enforces **9:00 AM IST** runtime gate (`03:30 UTC`)
- Secrets: API keys in secure secret store (GitHub Secrets / cloud secrets manager)
- State/artifacts: Google Sheets + Drive remain source of truth; run logs persist to durable storage

### Daily Batch Trigger Mechanism

1. Scheduler triggers orchestrator once per day.
2. Orchestrator acquires single-run lock (no overlapping run).
3. Orchestrator validates execution window for 9:00 AM IST.
4. Pipeline executes and emits daily summary plus run logs.

### Deployment Guardrails

- Single active-run lock to prevent overlap
- Missed-run alert if scheduler fails
- Manual rerun supported with idempotency checks enabled

---

## 3) Architecture Principles (Non-negotiable)

- Human-in-loop before outreach/submission
- No fabricated experience/skills/metrics
- Idempotent operations (no duplicate applications/messages)
- Hard ATS loop cap (`revision_count < 2`)
- Graceful per-row failures (one failure never blocks whole batch)
- Modular agent contracts (replaceable agent implementations)
- Full state and action audit trail in tracker

---

## 4) Phase-wise Implementation Architecture

## Phase 0 - Foundations and Contracts

### Objective
Establish architecture contracts, shared schemas, and system boundaries before runtime implementation.

### Scope
- Define end-to-end state machine and row lifecycle.
- Finalize data schema for Pipeline Tracker and source input contracts.
- Set policy constraints (dedup, no fabrication, loop cap, approval gates).
- Decide delivery channels (email vs Slack) and hosting baseline.
- Define v1 cost model (fixed + variable + per-run estimate + monthly budget cap).
- Define GDPR/privacy retention policy for recruiter/contact data.
- Define explicit SLA targets for CP1/CP2 and row processing.

### Design Outputs
- **System Context Diagram** (Orchestrator, Agents, External Services)
- **Data Contract Spec**:
  - Pipeline columns
  - `human_action` enums
  - `status` transition rules
  - JSON payload fields passed between agents
- **Operational Policy Doc**:
  - error handling
  - cap controls
  - idempotency checks
- **FinOps and SLA Policy Doc**:
  - per-service cost assumptions (LLM, scraping, enrichment, automation)
  - monthly spend guardrail and alert thresholds
  - CP1/CP2 SLA targets and escalation path
- **Data Retention and Privacy Policy**:
  - contact data retention period
  - deletion/anonymization workflow
  - lawful basis and consent handling notes

### Exit Criteria
- All status transitions are deterministic and documented.
- Every agent has clear input/output contract.
- Open design decisions tracked with owner and due date.
- Budget guardrails, data retention window, and SLA targets are signed off.

### Phase 0 artifacts (implemented in repo)

| Artifact | Path |
|----------|------|
| State machine (status transitions, guards, terminals) | `contracts/state-machine-spec.md` |
| Data contracts (tracker columns, enums, agent JSON shapes) | `contracts/data-contracts.md` |
| Operational policy (errors, caps, idempotency, LinkedIn fallback) | `policies/operational-policy.md` |
| FinOps and SLA policy (cost model shape, budget tiers, SLAs) | `policies/finops-sla-policy.md` |
| Privacy and retention (contact data, purge workflow, lawful basis notes) | `policies/privacy-retention-policy.md` |
| System context diagram (Mermaid + narrative) | `Docs/system-context.md` |
| Open decisions tracker (owner/due placeholders) | `contracts/open-decisions.md` |

**Phase 0 operational sign-off:** Replace **TBD** budget caps and dates in `contracts/open-decisions.md` and `policies/finops-sla-policy.md` with user-approved values before Phase 2 enrichment spend.

---

## Phase 1 - Core Orchestrator and State Backbone

### Objective
Build the control plane that runs daily and governs row-level orchestration safely.

### Scope
- Implement orchestrator skeleton with daily schedule (9:00 AM IST).
- Integrate Google Sheet read/write adapter for central state.
- Implement row-level state transition validator.
- Implement failure handling (`FAILED` + notes logging).
- Implement summary job stub.
- Implement deployment scheduler config (GitHub Actions cron or cloud scheduler) and run-lock guard.
- Implement optimistic locking fields (`updated_at`, optional `row_version`) in sheet update path.

### Key Components
- **Scheduler module** (cron/event trigger)
- **State engine** (allowed transitions + guard checks)
- **Sheet gateway** (typed read/write adapters)
- **Run logger** (timestamped run metadata)
- **Run lock manager** (single active daily batch)
- **Conflict detector** (optimistic lock compare-and-set)

### Data Flow
1. Scheduler triggers run.
2. Orchestrator loads pending rows and workflow config.
3. Orchestrator dispatches row sets to active phase agents.
4. State engine validates and commits updates.

### Exit Criteria
- Daily run starts automatically.
- Rows can move through initial states without manual scripts.
- Transition violations are blocked and logged.
- Race-condition conflicts are detected and safely handled.
- Only one orchestrator run is active at any time.

### Phase 1 artifacts (implemented in repo)

| Artifact | Path |
|----------|------|
| Orchestrator skeleton (CP1/CP2 gates + summary stub) | `src/orchestrator/main.py` |
| State transition validator with guards | `src/orchestrator/state_engine.py` |
| Pipeline tracker gateway (Phase 1 in-memory adapter) | `src/shared/sheets_gateway.py` |
| Run metadata logger (run_id, timestamps, counts, errors) | `src/shared/run_logger.py` |
| Dry-run output logs | `logs/run-*.json` |

### Validation (Phase 1 dry-run)

- Command: `python -m src.orchestrator.main`
- Result: completes successfully and writes a run log into `logs/`.

---

## Phase 2 - Agent 1 (Discovery and Qualification)

### Objective
Produce high-quality daily shortlist across target geographies with deduplicated rows using web scraping with anti-ban measures.

### Scope
- Integrate multi-source collectors (LinkedIn/Otta/Wellfound/Naukri/Cutshort/Adzuna/SerpAPI/Bayt/fallback search).
- Implement web scraping infrastructure with anti-ban measures for portals without free APIs:
  - **Naukri**: RSS discovery + detail scraping (India) - 10 req/min, 500 pages/day
  - **Cutshort**: Full scraping (APM-specific for India) - 20 req/min, 300 pages/day
  - **Otta**: Playwright for JS rendering (Europe) - 15 req/min, 200 pages/day
  - **Bayt**: Full scraping (MENA region) - 10 req/min, 200 pages/day
- Implement query strategy per geography cluster.
- Build fit scoring engine (weighted 0-100).
- Deduplicate against `(company + role_title + job_url)`.
- Write rows with `SCRAPED -> SCORED -> AWAITING_HUMAN_REVIEW`.

### Key Components
- **Source adapters** (normalize raw listings)
  - API-based: AdzunaAdapter, SerpApiAdapter
  - Scraping-based: NaukriAdapter, CutshortAdapter, OttaAdapter, BaytAdapter
- **Base scraper** (`src/agent_1/scrapers/base_scraper.py`)
  - Rate limiting per portal with exponential backoff (tenacity)
  - Daily quota tracking with persistent storage
  - Anti-ban techniques (user agent rotation, persistent sessions, random delays ±30%)
  - Two-phase scraping architecture (discovery → details)
  - Error handling (RateLimitError → 1hr pause, BlockedError → 24hr pause)
  - 24-hour caching to avoid re-scraping
  - robots.txt checking
  - Monitoring metrics to `logs/scraper_metrics_{date}.json`
- **Individual scrapers**
  - `naukri_scraper.py`: RSS feeds for discovery, scraping for details
  - `cutshort_scraper.py`: Full scraping with BeautifulSoup
  - `otta_scraper.py`: Playwright for JavaScript rendering
  - `bayt_scraper.py`: Full scraping with BeautifulSoup
- **Scoring engine**
- **Dedup engine**
- **Region/work_mode classifier**

### Legal Compliance
- Check robots.txt before scraping any portal
- Respect portal Terms of Service
- NEVER scrape LinkedIn directly (use Proxycurl API instead)
- Use RSS feeds where available (Naukri) as primary discovery

### Quality Gates
- Minimum score threshold default = 60.
- Output target = 10-30 net new jobs/day.
- Required fields always present for downstream use.
- Success rate <70% triggers alert
- IP blocks trigger 24-hour pause
- Zero jobs discovered triggers alert

### Exit Criteria
- CP1 queue is consistently generated daily.
- No duplicate row creation.
- Region and work permit flags are correctly populated.
- Rate limiting prevents bans
- One portal failure does not block others
- Monitoring metrics logged daily

### Phase 2 artifacts (implemented in repo)

| Artifact | Path |
|----------|------|
| Source adapters with API integration | `src/agent_1/adapters.py` |
| Base scraper with anti-ban measures | `src/agent_1/scrapers/base_scraper.py` |
| Naukri scraper (RSS + scraping) | `src/agent_1/scrapers/naukri_scraper.py` |
| Cutshort scraper (full scraping) | `src/agent_1/scrapers/cutshort_scraper.py` |
| Otta scraper (Playwright for JS) | `src/agent_1/scrapers/otta_scraper.py` |
| Bayt scraper (full scraping) | `src/agent_1/scrapers/bayt_scraper.py` |
| Scraper test suite | `test_scrapers.py` |
| Scraping configuration | `.env.example` (ENABLE_*_SCRAPING flags) |

---

## Phase 3 - CP1 Human Review and Decisioning

### Objective
Introduce controlled human decision gate before any personalization effort.

### Scope
- Generate CP1 digest with shortlist rows.
- Support user actions: `Apply`, `Outreach Only`, `Skip`.
- Ensure no downstream trigger unless `human_action` is set.

### Key Components
- **Digest renderer**
- **Notification sender**
- **Action sync checker** (polls for decision completeness)

### Exit Criteria
- Rows without `human_action` never proceed.
- User decisions are reflected in pipeline status within SLA.

---

## Phase 4 - Agent 2 (Contact Discovery Layer)

### Objective
Enrich approved rows with high-value hiring contacts without blocking pipeline.

### Scope
- Run discovery for recruiter/hiring manager priority order.
- Enrich from LinkedIn + Hunter/Apollo + pattern inference.
- Validate deliverability (`email_verified`).
- Continue flow if no contact found.
- Handle provider/API 429 with exponential backoff + jitter and bounded retries.
- Persist paused rows (`paused_reason`, `resume_after`) when quota is exhausted.

### Key Components
- **People search module**
- **Email enrichment module**
- **Verification module**

### Exit Criteria
- Contact fields are populated where feasible.
- Non-blocking behavior verified for no-contact cases.

---

## Phase 5 - Agent 3 (Content Personalization Engine)

### Objective
Generate truthful, role-targeted application assets from trusted inputs.

### Scope
- Create tailored CV per approved row.
- Generate cold email and LinkedIn DM.
- Save CV as versioned document and write links to tracker.
- Log skill gaps when required JD skills are missing in source inputs.
- Handle LLM/API burst limits with exponential backoff and retry budget.
- Resume interrupted rows from last safe checkpoint after transient rate limits clear.

### Key Components
- **Input reader** (Master CV + Accomplishments Bank)
- **Skill alignment mapper**
- **CV rewriter (keyword + impact oriented)**
- **Outreach writer (email + DM templates)**

### Governance Controls
- Never invent skills/impact.
- Never mutate source input docs.
- Preserve traceability between source evidence and generated bullets.

### Exit Criteria
- 3 assets per row produced consistently.
- Skill gaps captured in notes.
- Ready for CP2 review.

---

## Phase 6 - CP2 Human Content Approval

### Objective
Ensure user validates generated CV + outreach before any external action.

### Scope
- Send CP2 digest containing CV link + outreach drafts.
- Hold execution until explicit approval.
- Allow human edits and re-approval.

### Key Components
- **Content review digest**
- **Approval gate checker**
- **Approval audit logger**

### Exit Criteria
- No email/DM/application is sent without CP2 approval flag.
- Approval history is auditable per row.

---

## Phase 7 - Agent 3b (ATS Quality and Revision Loop)

### Objective
Raise ATS pass probability while preventing infinite refinement loops.

### Scope
- Evaluate CV across structural and keyword checks.
- Compute `ats_score` and pass/fail.
- Route failures back to Agent 3 with actionable notes.
- Enforce max 2 revision cycles.

### Decision Policy
- `score >= 80`: mark `ATS_PASS`
- `score < 80` and `revision_count < 2`: increment and rework
- `score < 80` and `revision_count >= 2`: move to `HUMAN_REVIEW`

### Exit Criteria
- Revision cap is technically enforced.
- Every ATS fail has clear remediation notes.
- Endless loops are impossible by design.

---

## Phase 8 - Agent 4 (Execution and Action Layer)

### Objective
Execute approved applications and outreach safely, idempotently, and at controlled volume.

### Scope
- Submit job applications for eligible rows.
- Send cold emails and LinkedIn DMs when contact data exists.
- Respect platform safety cap (20-25 applications/day).
- Put non-automatable rows into manual queue.
- Enforce Gmail sending cap policy (free tier default: max 20 emails/day).
- Add LinkedIn fallback policy: if automation is blocked/risky, pivot row to `MANUAL_QUEUE` instead of forcing automation.
- Apply API rate-limit controls (429/5xx retry with backoff, pause/resume, bounded attempts).

### Key Components
- **Form automation engine** (Playwright)
- **Email sender** (Gmail MCP)
- **LinkedIn outreach module**
- **Idempotency guard** (pre-action status check)
- **Channel policy engine** (enforces per-channel limits and fallback routing)

### Exit Criteria
- Duplicate submissions prevented.
- `applied_at`/`outreach_sent_at` set reliably.
- Failed executions marked with root-cause notes.
- Gmail daily quota breaches are prevented by policy checks.
- LinkedIn automation failures are safely rerouted to manual queue.
- Rate-limited rows can resume safely without duplicate external actions.

---

## Phase 9 - Response Monitoring and Lifecycle Management

### Objective
Track inbound responses and maintain actionable pipeline visibility post-submission.

### Scope
- Poll inbox for outreach replies daily.
- Update `RESPONSE_RECEIVED` or `NO_RESPONSE`.
- Capture response snippets in notes.
- Surface follow-up opportunities in summary.

### Exit Criteria
- Response statuses update without manual inspection.
- Daily visibility into active conversation pipeline.

---

## Phase 10 - Reporting, Observability, and Operations Hardening

### Objective
Make the system operable, diagnosable, and continuously improvable.

### Scope
- Implement complete daily summary report format.
- Add run metrics dashboard (counts by status and stage).
- Add structured logs and per-agent latency tracking.
- Add operational alerts for failure spikes.

### Suggested Metrics
- Discovery yield/day
- CP1/CP2 turnaround time
- ATS first-pass rate
- Application success rate
- Outreach response rate
- Failure rate by agent/source
- Monthly run cost and cost per successful application
- SLA attainment rate (CP1/CP2 within target)

### Exit Criteria
- Daily report sent with correct aggregates.
- Operators can diagnose failed rows quickly.
- Cost and SLA reports are visible and actionable.

---

## 5) Cross-cutting Architecture Concerns

### Security and Privacy
- Store API keys/tokens in secure secrets manager.
- Restrict logging of personal contact data.
- Enforce least-privilege API scopes for Gmail/Drive/Sheets.
- Apply retention policy for recruiter contact data (recommended v1 default: 90 days; purge/anonymize after expiry).

### Reliability
- Row-level isolation for all agent errors.
- Safe retries only where idempotent and approved.
- Checkpointed progress to resume interrupted runs.
- Optimistic locking on row updates (`updated_at` / `row_version`) to prevent lost updates.
- Conflict policy: reload, re-validate, retry once, then escalate to `HUMAN_REVIEW`.

### State Locking and Race Condition Strategy
- Add `updated_at` and optional `row_version` columns to Pipeline Tracker.
- Every write performs compare-and-set against the last-read value.
- On conflict (human + orchestrator concurrent edit):
  1. Re-read latest row.
  2. Recompute transition guards.
  3. Merge non-destructive fields (for example, append-only notes).
  4. Retry once; if conflict persists, park row to `HUMAN_REVIEW` with conflict reason.
- Process rows sequentially per `job_id` within a run to minimize collision windows.

### Error Recovery Workflow (`FAILED` rows)
- `FAILED` stays terminal for automatic processing in the same run.
- Recovery is controlled and manual:
  1. Operator inspects `notes` and root cause.
  2. Operator resets row to last safe state (`AWAITING_HUMAN_REVIEW`, `CONTENT_GENERATION`, or `ATS_REVIEW`) and sets recovery note.
  3. Orchestrator re-validates transition + idempotency before re-entry.
  4. If prior external action outcome is uncertain, verify provider-side state before resend/resubmit.
- All recovery actions are audited (`recovered_by`, `recovered_at`, `recovery_reason`).

### Scalability (v1 -> v2)
- v1: single-user, daily batch.
- v2 ready: parallel row workers, queue-based dispatch, multi-tenant sheet partitioning.

### Compliance/Platform Risk
- Respect terms and rate limits for sourcing/automation endpoints.
- Keep automation fallback pathways (manual queue) for unstable channels.
- Treat LinkedIn automation as conditional capability; manual queue is the safe fallback mode.

### API Rate Limiting and Concurrency Control
- Exponential backoff with jitter for 429/5xx (`base=2s`, `max_delay=60s`, `max_attempts=5` default).
- Provider-specific concurrency caps (for example: LLM 3 concurrent, enrichment 2 concurrent).
- Pause/resume markers persisted in tracker (`paused_reason`, `resume_after`) for continuation in same or next run.
- Circuit-break noisy providers on sustained error rate and continue other pipeline stages where safe.
- Never retry non-idempotent actions without outcome verification.

### Service Levels (v1 defaults)
- CP1 digest delivery SLA: within 30 minutes of Agent 1 completion.
- CP2 digest delivery SLA: within 30 minutes of Agent 3 completion.
- Human response target for CP1/CP2: within 24 hours (configurable).
- Escalation: unresolved approvals beyond SLA are surfaced in daily summary as `ATTENTION NEEDED`.

---

## 6) Recommended Build Order (Execution Plan)

1. Phase 0 + Phase 1 (contracts + orchestrator backbone)
2. Phase 2 + Phase 3 (discovery + CP1)
3. Phase 4 + Phase 5 (contact + content generation)
4. Phase 6 + Phase 7 (CP2 + ATS loop)
5. Phase 8 + Phase 9 (execution + monitoring)
6. Phase 10 (observability + hardening)

This order minimizes integration risk by stabilizing state and control flow first, then layering domain complexity.

---

## 7) Definition of Done (System-level)

The architecture is considered production-ready when:

- Daily scheduled run executes without manual orchestration.
- Human checkpoints are enforced technically, not procedurally.
- No duplicate applications/messages are observed.
- ATS loop cap and failure routing work exactly as specified.
- End-to-end report reflects true pipeline state each day.
- At least one full week of stable run logs confirms operational reliability.

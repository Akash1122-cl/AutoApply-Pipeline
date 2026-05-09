# AutoApply Phase-wise Implementation Plan

## Purpose

This document is a separate implementation guide derived from the architecture.  
It translates each phase into execution-ready work items with dependencies, deliverables, and acceptance criteria.

---

## Phase 0 - Foundations and Contracts

### Goal
Freeze architecture contracts, policies, and implementation boundaries before coding runtime behavior.

### Implementation Tasks
- Finalize state machine and allowed transitions.
- Define canonical schemas for:
  - Pipeline Tracker row fields
  - Agent input/output payloads
  - Status/event logs
- Define v1 policies:
  - no fabrication
  - idempotency and dedup
  - ATS loop cap
  - human approval enforcement
- Define cost model:
  - fixed monthly infra cost
  - variable per-job/per-run costs
  - monthly budget cap and alert threshold
- Define data retention policy:
  - contact data retention duration
  - purge/anonymize process
  - audit logging for deletion events
- Define SLA targets:
  - CP1/CP2 digest delivery SLA
  - human review turnaround target
  - escalation triggers

### Deliverables
- `contracts/state-machine-spec.md`
- `contracts/data-contracts.md`
- `policies/finops-sla-policy.md`
- `policies/privacy-retention-policy.md`

### Dependencies
- None

### Acceptance Criteria
- All teams/agents reference one canonical schema set.
- Budget, privacy retention, and SLAs are approved and documented.

---

## Phase 1 - Orchestrator and State Backbone

### Goal
Build the central control plane for daily batch execution and safe state progression.

### Implementation Tasks
- Implement scheduler trigger for 9:00 AM IST.
- Set up deployment target and scheduler wiring (GitHub Actions cron or AWS EventBridge / GCP Cloud Scheduler).
- Build orchestrator workflow shell:
  - trigger Agent 1
  - gate at CP1
  - trigger Agent 2/3
  - gate at CP2
  - run Agent 3b and Agent 4
  - send daily report
- Implement state transition validator with strict guards.
- Implement run lock (single active run) to prevent overlapping daily executions.
- Add optimistic locking support in sheet writes using `updated_at` (and optional `row_version`).
- Implement row-level failure handling:
  - set `FAILED`
  - write error notes
  - continue other rows
- Add run metadata logging:
  - run_id
  - start/end timestamps
  - per-agent counts

### Deliverables
- `src/orchestrator/main.py`
- `src/orchestrator/state_engine.py`
- `src/shared/sheets_gateway.py`
- `src/shared/run_logger.py`
- `.github/workflows/daily-run.yml` (or equivalent cloud scheduler configuration doc)

### Dependencies
- Phase 0 contracts finalized

### Acceptance Criteria
- Orchestrator runs end-to-end on a dry-run dataset.
- Invalid transitions are blocked and logged.
- Concurrent write conflict is detected and resolved via retry/escalation policy.
- Duplicate scheduler overlap is prevented by run lock.

### Implementation Status
- Status: Implemented (Phase 1 scaffold complete)
- Implemented files:
  - `src/orchestrator/main.py`
  - `src/orchestrator/state_engine.py`
  - `src/shared/sheets_gateway.py`
  - `src/shared/run_logger.py`
- Dry-run command: `python -m src.orchestrator.main`
- Dry-run outcome: successful run; metadata log generated under `logs/`.

---

## Phase 2 - Agent 1 Discovery and Qualification

### Goal
Generate daily, deduplicated shortlist rows with fit scoring.

### Implementation Tasks
- Build source adapters for prioritized job sources.
- Implement regional query batches (India, EU-priority, EU-secondary, SEA).
- Normalize all listings to common schema.
- Compute weighted fit score (0-100).
- Enforce minimum shortlist threshold (default 60).
- Enforce dedup check `(company + role_title + job_url)`.
- Write `SCRAPED -> SCORED -> AWAITING_HUMAN_REVIEW`.

### Deliverables
- `src/agents/agent1_scout_qualify.py`
- `src/agents/agent1_sources/`
- `src/agents/scoring_engine.py`

### Dependencies
- Phase 1 orchestrator and sheet gateway

### Acceptance Criteria
- 10-30 valid new rows/day (target range, depends on source volume).
- Zero duplicate inserts for same key triple.

---

## Phase 3 - CP1 Shortlist Review Gate

### Goal
Introduce explicit human decision control before contact/content generation.

### Implementation Tasks
- Build CP1 digest generator (email/Slack format).
- Implement decision poller for `human_action`.
- Block downstream rows until action is set.
- Route decisions:
  - `Apply`
  - `Outreach Only`
  - `Skip`

### Deliverables
- `src/checkpoints/cp1_digest.py`
- `src/checkpoints/cp1_action_sync.py`

### Dependencies
- Phase 2 completed rows in `AWAITING_HUMAN_REVIEW`

### Acceptance Criteria
- No row proceeds without explicit CP1 action.
- CP1 digest delivery meets configured SLA.

---

## Phase 4 - Agent 2 Contact Discovery

### Goal
Enrich approved rows with recruiter/hiring contacts without blocking flow.

### Implementation Tasks
- Implement contact search priorities (recruiter -> hiring manager -> HoP/CPO -> founder).
- Integrate enrichment providers and email verification.
- Populate contact fields in tracker.
- Keep non-blocking behavior if no contact found.
- Implement 429/5xx retry policy (exponential backoff + jitter + max attempts).
- Persist pause/resume fields when enrichment quota is exhausted mid-run.

### Deliverables
- `src/agents/agent2_contact_discovery.py`
- `src/agents/contact_enrichment/`

### Dependencies
- CP1 decisions (`Apply` / `Outreach Only`)

### Acceptance Criteria
- Contact enrichment succeeds where data exists.
- Rows continue even when contact data is unavailable.
- Rate-limited requests recover automatically without duplicate writes.

---

## Phase 5 - Agent 3 Content Generation

### Goal
Create truthful personalized CV and outreach drafts per approved row.

### Implementation Tasks
- Read Master CV and Accomplishments Bank (read-only).
- Map JD required skills to source evidence.
- Generate tailored CV and store output link.
- Generate cold email and LinkedIn DM drafts.
- Log `skill_gap` in notes when required skill has no source evidence.
- Preserve revision mode support for ATS feedback rework.
- Add LLM rate-limit controls (retry/backoff + per-provider concurrency cap).

### Deliverables
- `src/agents/agent3_content_generation.py`
- `src/agents/content_templates/`
- `src/agents/cv_builder.py`

### Dependencies
- Phase 4 enrichment (optional but preferred)

### Acceptance Criteria
- 3 assets created per eligible row.
- No fabricated claims appear in output samples.
- Transient API throttling does not permanently fail eligible rows.

---

## Phase 6 - CP2 Content Approval Gate

### Goal
Enforce human approval before any application or outreach execution.

### Implementation Tasks
- Build CP2 digest with CV and outreach draft links.
- Add approval status tracking.
- Block Agent 4 unless CP2 approved.
- Log approval timestamps and reviewer actions.

### Deliverables
- `src/checkpoints/cp2_digest.py`
- `src/checkpoints/cp2_approval_sync.py`

### Dependencies
- Phase 5 content outputs

### Acceptance Criteria
- No sends/submissions happen without CP2 approval.
- CP2 digest delivery meets configured SLA.

---

## Phase 7 - Agent 3b ATS Review Loop

### Goal
Improve ATS readiness while enforcing strict max-2 revision loop.

### Implementation Tasks
- Implement ATS rule checks and scoring.
- Set pass/fail using threshold (default 80).
- On fail and `revision_count < 2`, return to Agent 3 with specific notes.
- On fail and `revision_count >= 2`, route to `HUMAN_REVIEW`.
- Persist ATS score/reasons for auditability.

### Deliverables
- `src/agents/agent3b_ats_reviewer.py`
- `src/agents/ats_checks/`

### Dependencies
- Phase 5 content generation

### Acceptance Criteria
- Revision loop never exceeds 2 cycles.
- Every ATS fail has actionable failure reasons.

---

## Phase 8 - Agent 4 Execution and Channel Policy

### Goal
Execute approved applications/outreach safely with channel caps and fallback policies.

### Implementation Tasks
- Build execution pipeline for:
  - application submission
  - cold email sending
  - LinkedIn DM sending
- Enforce idempotency checks before every action.
- Enforce Gmail free-tier default cap: max 20 emails/day.
- Enforce LinkedIn fallback:
  - if automation blocked/risky/failing -> route to `MANUAL_QUEUE`
- Persist execution timestamps and outcomes.
- Add bounded retry/backoff for 429/5xx failures and pause/resume checkpoints.

### Deliverables
- `src/agents/agent4_execution_tracking.py`
- `src/policies/channel_policy_engine.py`
- `src/automation/playwright_runner.py`

### Dependencies
- CP2 approval
- ATS pass

### Acceptance Criteria
- Duplicate submissions/sends are prevented.
- Gmail cap violations do not occur.
- LinkedIn unstable cases move to manual queue safely.
- Retry logic never causes duplicate non-idempotent external actions.

---

## Phase 9 - Response Monitoring

### Goal
Track incoming responses and keep post-execution pipeline state updated.

### Implementation Tasks
- Poll outreach mailbox daily.
- Match replies to job/application rows.
- Update response status and store useful snippets.
- Surface positive responses in summary.

### Deliverables
- `src/monitoring/response_monitor.py`
- `src/monitoring/reply_matcher.py`

### Dependencies
- Phase 8 outreach execution

### Acceptance Criteria
- Reply detection works on known test threads.
- Response status reflects latest inbox state.

---

## Phase 10 - Reporting, Observability, and Hardening

### Goal
Operationalize the platform with clear visibility into quality, cost, and SLA health.

### Implementation Tasks
- Implement final daily summary report output.
- Add dashboards/aggregates for:
  - pipeline throughput
  - ATS outcomes
  - execution success/failure
  - cost trends
  - SLA attainment
- Add alerting for:
  - failure spikes
  - cost threshold breaches
  - SLA misses
- Run resilience tests and recovery drills.
- Publish recovery dashboard for `FAILED` rows with last error and recommended reset state.

### Deliverables
- `src/reporting/daily_summary.py`
- `src/observability/metrics_collector.py`
- `src/observability/alerts.py`

### Dependencies
- All previous phases

### Acceptance Criteria
- Daily report includes cost and SLA health.
- Operators can quickly identify and triage issues.
- Recovery workflow for `FAILED` rows is documented and test-validated.

---

## Phase 10.1 - Error Recovery and Replay Controls

### Goal
Recover `FAILED` rows safely while preserving idempotency and auditability.

### Implementation Tasks
- Build manual recovery procedure and helper tooling:
  - inspect row error in `notes`
  - choose safe reset status
  - append recovery metadata (`recovered_by`, `recovered_at`, `recovery_reason`)
- Add pre-retry verification checks for uncertain external outcomes (email/apply/linkedin).
- Add replay guard: block retries if prior success is detected.
- Add recovery queue reporting in daily summary.

### Deliverables
- `src/orchestrator/recovery_service.py`
- `docs/runbooks/failed-row-recovery.md`

### Dependencies
- Phase 8 and Phase 10 observability outputs

### Acceptance Criteria
- Recovered rows resume from valid checkpoints only.
- No duplicate external side effects after recovery.
- All recovery actions are auditable.

---

## Formal Testing Strategy (applies across phases)

### Test Layers
- **Unit tests:** state transitions, scoring logic, policy rules, retry/backoff calculators.
- **Integration tests:** orchestrator + sheets gateway + checkpoint transitions.
- **Contract tests:** sheet schema, enum values, payload shape compatibility between agents.
- **End-to-end dry runs:** seeded rows through CP1/CP2/ATS/Execution stubs.

### API Mocking and Cost Control
- Mock LLM, enrichment, and notification providers for local/CI runs.
- Use recorded fixtures for common 200/429/500 responses.
- Disable paid API calls by default in test mode (`TEST_MODE=true`).
- Maintain one small paid canary suite (optional) with strict monthly cap.

### Minimum Test Requirements by Milestone
- M1: State engine + scheduler + dedup tests passing.
- M2: CP1/CP2 approval gates and no-send-without-approval tests passing.
- M3: Rate-limit retries, Gmail cap, LinkedIn fallback, and idempotency tests passing.
- M4: Recovery workflow + reporting accuracy + SLA metrics tests passing.

### CI Expectations
- Run unit + integration suites on every change.
- Block merge on failed contract tests.
- Publish coverage and flaky-test trend report.

---

## Phase-level Dependency Graph

`Phase 0 -> Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5 -> Phase 6 -> Phase 7 -> Phase 8 -> Phase 9 -> Phase 10`

Parallelization opportunities:
- Phase 4 and Phase 5 can partially overlap after CP1 if contracts are stable.
- Phase 9 can start early with mocked execution data.

---

## Milestone Readiness Checklist

- M1 (Phases 0-2): Discovery pipeline operational
- M2 (Phases 3-6): Human-gated personalization operational
- M3 (Phases 7-8): ATS loop and controlled execution operational
- M4 (Phases 9-10): Monitoring, reporting, and production hardening complete

---

## Default v1 Targets (Operational)

- CP1 digest delivery: within 30 minutes after Agent 1 completion
- CP2 digest delivery: within 30 minutes after Agent 3 completion
- Human decision target (CP1/CP2): within 24 hours
- Gmail send cap: 20 emails/day (free-tier default)
- LinkedIn automation mode: conditional; fallback to `MANUAL_QUEUE` when unstable
- Contact data retention: 90 days then purge/anonymize

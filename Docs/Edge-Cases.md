# AutoApply Edge Cases Register

Based on:
- `Docs/Architecture.md`
- `Docs/Phasewise-Implementation.md`

This file captures edge cases to handle proactively during implementation and operations.

---

## How to Use

- Use this register during design reviews, test planning, and incident triage.
- For each edge case: define owner, detection signal, and mitigation before production rollout.
- Link implemented handling back to code modules as phases are completed.

---

## Phase 0 - Foundations and Contracts

### Contract / Schema Edge Cases
- `status` values drift between docs and code (e.g., `ATS_PASS` as status vs `ats_pass` column only).
- Missing required columns in Pipeline Tracker after manual sheet edits.
- Enum mismatch (`Outreach Only` vs `OutreachOnly`) causes branch failures.
- `required_skills` stored as invalid JSON string.

### Policy Edge Cases
- Budget cap values left as `TBD` and paid APIs start unintentionally.
- Retention policy defined but no purge job implemented.
- SLA defined but no timestamp fields exist to measure attainment.

---

## Phase 1 - Orchestrator and State Backbone

### Scheduling / Execution
- Scheduler triggers twice at 9:00 AM (duplicate run) due to host restart/clock skew.
- Run starts late or is skipped when host is offline.
- Long run overlaps with next scheduled run.

### State Engine
- Terminal state receives new transition due to manual row edit.
- Valid transition attempted with missing context (`human_action`, `cp2_approved`, `ats_pass`).
- Row has unknown status value from legacy data.

### Fault Isolation
- One malformed row crashes whole batch instead of row-level failure.
- Notes field grows too large due to repeated stack traces.
- Retry logic accidentally replays non-idempotent actions.

### Observability
- Run log written but incomplete if process exits unexpectedly.
- Run IDs not unique across parallel workers.

---

## Phase 2 - Agent 1 Discovery and Qualification

### Source Collection
- API rate limits or temporary 429/503 from job sources.
- Source schema changes (field rename) break parser silently.
- Duplicate job appears across multiple platforms with different URLs.
- Posting date unavailable or timezone ambiguous, skewing recency score.

### Relevance / Quality
- Role title contains APM-like keyword but is unrelated (false positives).
- Internship/fresher jobs misclassified as Associate PM.
- Region detection wrong for “Remote (EMEA)” or “Remote (India preferred)”.
- Work permit requirement hidden in job description text, not structured.

### Deduplication
- Same job URL with tracking parameters bypasses dedup.
- Company naming variations (`ABC Pvt Ltd` vs `ABC`) create duplicate rows.

---

## Phase 3 - CP1 Shortlist Review

### Human Interaction
- User partially reviews rows; some remain pending indefinitely.
- Conflicting edits on same row from multiple devices/sessions.
- User changes action after downstream work already started.

### SLA / Notification
- CP1 digest sent but includes stale or already-updated statuses.
- Notification failure (email/Slack outage) with no fallback alert.

---

## Phase 4 - Agent 2 Contact Discovery

### Contact Accuracy
- Contact found is ex-employee/outdated profile.
- Inferred email format incorrect but appears syntactically valid.
- Personal email accidentally captured (policy violation).

### Non-blocking Behavior
- No contact found and row incorrectly halted.
- Contact provider quota exhausted mid-run.

### Data Quality
- Multiple valid contacts found; wrong priority chosen.
- `email_verified=true` despite provider confidence being low.

---

## Phase 5 - Agent 3 Content Generation

### Truthfulness / Hallucination
- LLM introduces unsupported skill/impact metric.
- Rewrites overstate ownership (“led” vs “supported”) without evidence.
- Skill mapping misses relevant accomplishment due to tag mismatch.

### Asset Generation
- CV link write succeeds but document creation fails (broken pointer).
- Email/DM templates exceed expected tone/length limits.
- Required skill gaps not logged in `notes`.

### Revision Context
- ATS feedback references old CV version after user edits.
- Rework loop overwrites user-edited content unintentionally.

---

## Phase 6 - CP2 Content Approval

### Gate Control
- `cp2_approved` missing or not persisted; execution starts anyway.
- User approves only one asset (CV) but system treats full approval.
- Approval revoked after approval and before execution; stale state used.

### UX / Audit
- No timestamp/user attribution for approval event.
- Edited drafts not synchronized to execution layer.

---

## Phase 7 - ATS Review Loop

### Scoring / Rules
- ATS rule parser fails on unusual CV formatting and returns false fail.
- Keyword coverage over-counts due to repeated keyword stuffing.
- Multi-language CV terms reduce measured coverage incorrectly.

### Loop Control
- `revision_count` not incremented atomically, causing >2 loops.
- Row bounces between `CONTENT_GENERATION` and `ATS_REVIEW` indefinitely.
- ATS pass threshold changed without versioning; inconsistent behavior.

---

## Phase 8 - Execution and Channel Policy

### Application Submission
- Form automation partially submits and then errors (unknown final state).
- Job portal requires CAPTCHA / OTP / anti-bot check.
- Duplicate submission due to rerun after uncertain previous outcome.

### Gmail Limits / Sending
- Gmail free-tier cap exceeded because personal sends reduced available quota.
- Daily quota resets by timezone mismatch.
- Send succeeded but API timeout caused false “failed” status.

### LinkedIn Automation
- LinkedIn UI changes break selectors.
- Account risk signal appears; automation should pivot to manual queue immediately.
- DM send blocked for non-1st-degree connections.

### Manual Queue
- Rows routed to manual queue without enough context (missing draft/link).
- Manual completion not fed back into tracker, causing repeated queueing.

---

## Phase 9 - Response Monitoring

### Matching / Classification
- Reply detected but cannot map to `job_id` due to subject changes.
- Auto-replies (OOO/newsletters) misclassified as true responses.
- Threading differences between Gmail API and client view create misses.

### Lifecycle
- `NO_RESPONSE` set too early; later real response not surfaced.
- Monitoring continues after terminal closure, wasting quota.

---

## Phase 10 - Reporting and Operations

### Metrics Integrity
- Counts mismatch between summary and sheet due to race conditions.
- Cost per application inflated by failed/duplicate attempts.
- SLA attainment appears high because missing timestamps are excluded.

### Alerting
- Alert storms for same underlying outage.
- Critical failures not alerted due to threshold misconfiguration.

---

## Cross-cutting Edge Cases

### Data and Privacy
- PII leakage in logs (`notes`, exception traces, debug dumps).
- Retention purge deletes needed audit metadata.
- Purge job misses records in archived tabs.

### Reliability and Recovery
- Power/network interruption mid-run leaves mixed states.
- Re-run without checkpointing duplicates downstream actions.
- Local clock drift affects scheduling and SLA calculations.

### Governance and Compliance
- Platform ToS changes invalidate current automation strategy.
- Region/legal rules change (e.g., work permit requirements) and filters become stale.

---

## Recommended Test Scenarios (Minimum)

1. Invalid status transition attempt from terminal state.
2. Duplicate scheduler trigger on same day.
3. CP2 not approved but execution attempted.
4. ATS fail loop hitting exactly 2 revisions.
5. Gmail cap reached mid-batch.
6. LinkedIn automation failure routes to manual queue.
7. Contact retention purge after 90 days.
8. Summary counts under concurrent row updates.

---

## Ownership Template (Fill During Implementation)

| Edge Case ID | Owner | Detection Signal | Mitigation | Status |
|---|---|---|---|---|
| EC-001 | TBD | TBD | TBD | Open |
| EC-002 | TBD | TBD | TBD | Open |


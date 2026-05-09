# Job Pipeline State Machine Specification

Version: v1 (Phase 0)  
Source of truth alignment: `Docs/Context.md`, `Docs/Architecture.md`

## Purpose

Defines deterministic `status` values, terminal states, allowed transitions, and guards so the orchestrator and agents cannot drift into ambiguous flows.

---

## Status Enumeration

### Canonical `status` values

| Status | Description |
|--------|-------------|
| `SCRAPED` | Row ingested from a source; minimal normalization complete |
| `SCORED` | Fit scoring computed (`fit_score` populated) |
| `AWAITING_HUMAN_REVIEW` | CP1: awaits user `human_action` |
| `CONTACT_DISCOVERY` | Agent 2 running or queued |
| `CONTENT_GENERATION` | Agent 3 running or queued (includes ATS-driven revisions) |
| `AWAITING_CONTENT_REVIEW` | CP2: awaits content approval |
| `ATS_REVIEW` | Agent 3b evaluating tailored CV |
| `EXECUTION` | Agent 4 performing submission/outreach |
| `MONITORING` | Post-send/open-loop tracking (replies, follow-through) |
| `RESPONSE_RECEIVED` | Reply detected for outreach/application thread |
| `NO_RESPONSE` | Monitoring concluded without reply within policy window |
| `ATS_PASS` | ATS threshold met (may coexist as checkpoint label—implementation maps to ATS gate cleared before EXECUTION) |
| `APPLIED` | **Terminal:** application submitted per approved intent |
| `OUTREACH_SENT` | **Terminal:** outreach-only path completed where applicable |
| `SKIPPED` | **Terminal:** user skipped |
| `HUMAN_REVIEW` | **Terminal:** ATS failed after max revisions OR explicit manual escalation |
| `FAILED` | **Terminal:** irrecoverable error on row; no auto-retry |

**Implementation note:** The conceptual diagram in Context merges ATS outcomes (`ATS_PASS`) with downstream execution. In code, either:

- Store ATS outcome in columns (`ats_pass`, `ats_score`) while using `status` = `EXECUTION` after pass; **or**
- Use `ATS_PASS` as a discrete status immediately before `EXECUTION`.

Pick one convention in Phase 1 and enforce it in the transition table below via aliases `[ATS_GATE_OK]` / `[EXECUTABLE]`.

---

## Human Actions (`human_action`)

Values are mutually exclusive per row:

| Value | Meaning |
|-------|---------|
| _(empty)_ | CP1 not complete |
| `Apply` | Application + optional outreach per Agent 4 rules |
| `Outreach Only` | Outreach channels only (no application automation unless separately justified—implement Agent 4 branch explicitly) |
| `Skip` | Terminal skip |

---

## Allowed Transitions (Directed Graph)

### Bootstrap path (Agent 1)

```
SCRAPED → SCORED → AWAITING_HUMAN_REVIEW
```

### CP1 gate

```
AWAITING_HUMAN_REVIEW → SKIPPED                    when human_action == Skip
AWAITING_HUMAN_REVIEW → CONTACT_DISCOVERY         when human_action ∈ {Apply, Outreach Only}
```

### Discovery + content

```
CONTACT_DISCOVERY → CONTENT_GENERATION            always proceed after Agent 2 (contacts optional)
CONTENT_GENERATION → AWAITING_CONTENT_REVIEW      when drafts exist for CP2
```

### CP2 gate

```
AWAITING_CONTENT_REVIEW → ATS_REVIEW              when CP2 approved AND tailored CV link valid
AWAITING_CONTENT_REVIEW → CONTENT_GENERATION      when CP2 requests edits (manual/automated rework signal—implementation-defined column optional)
```

**Hard rule:** No outreach/application sends unless CP2 approval is recorded (implementation: explicit flag column recommended—see `contracts/data-contracts.md`).

### ATS loop (Agent 3b)

Preconditions: CP2 approved, tailored CV present.

```
ATS_REVIEW → EXECUTION                           when ats_pass == true OR effective ATS score ≥ threshold (default 80)
ATS_REVIEW → CONTENT_GENERATION                  when ats_pass == false AND revision_count < 2 (increment revision_count)
ATS_REVIEW → HUMAN_REVIEW                         when ats_pass == false AND revision_count >= 2
```

**Hard rule:** `revision_count` increments at most twice per row for ATS-driven rework cycles before forcing `HUMAN_REVIEW`.

### Execution (Agent 4)

```
EXECUTION → APPLIED                              when human_action == Apply and submission succeeds
EXECUTION → OUTREACH_SENT                        when human_action == Outreach Only (and outreach policy satisfied)
EXECUTION → FAILED                               when submission/send fails irrecoverably
EXECUTION → MONITORING                           optional intermediate before terminal labels—omit if tracking stays column-driven
```

### Monitoring

```
MONITORING → RESPONSE_RECEIVED                    reply matched to row
MONITORING → NO_RESPONSE                          no reply within retention/timeline policy (implementation-defined window)
```

### Failure handling

Any agent may transition row → **`FAILED`** from any non-terminal state when execution raises uncaught errors:

```
<ANY_NON_TERMINAL> → FAILED                      with structured note (timestamp + agent + error summary)
```

**Hard rule:** No automatic retry from `FAILED` in v1.

---

## Terminal States

States below MUST NOT transition except explicit manual audit tooling:

- `APPLIED`
- `OUTREACH_SENT`
- `SKIPPED`
- `HUMAN_REVIEW`
- `FAILED`

---

## Idempotency and Dedup

- **Dedup key:** `(company, role_title, job_url)` — no duplicate inserts by Agent 1.
- **No duplicate sends/submits:** Before EXECUTION, validate row has not already reached terminal submit/send states for same action intent.

---

## Revision History

| Date | Change |
|------|--------|
| 2026-05-03 | Initial Phase 0 spec |

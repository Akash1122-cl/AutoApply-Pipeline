# Operational Policy — Errors, Caps, Idempotency

Version: v1 (Phase 0)

---

## 1. Human Approval Gates

- **CP1:** Downstream automation MUST NOT run until each advancing row has `human_action` set (`Apply`, `Outreach Only`, or `Skip`).
- **CP2:** Email, LinkedIn DM, and application submission MUST NOT execute unless `cp2_approved == true` (see `contracts/data-contracts.md`). Inline confirmation in sheet or companion UI must flip this flag explicitly.

---

## 2. Failure Handling

| Situation | Policy |
|-----------|--------|
| Agent throws on one row | Set `status = FAILED`, append structured entry to `notes`, continue all other rows |
| Network/transient errors | Orchestrator MAY retry same agent step **only** if operation is idempotent and retry count ≤ 1 per row per run (document outcome in `notes`); never violate dedup/send rules |
| User-facing visibility | All `FAILED` rows listed in daily summary `ATTENTION NEEDED` |

**Hard rule:** No automatic retry queue from `FAILED` in v1.

---

## 3. Idempotency

| Action | Idempotency Rule |
|--------|------------------|
| Insert job row | Dedup on `(company, role_title, job_url)` before insert |
| Application submit | Before submit: verify row not already `APPLIED` / no duplicate submit for same `job_url` |
| Cold email send | Before send: verify no prior successful send logged for same row + channel |
| LinkedIn DM | Same as email; plus automation fallback below |

---

## 4. Rate and Volume Caps

| Channel | Default Cap | Notes |
|---------|-------------|------|
| Gmail (consumer/free) | **20 outbound emails/day** | Align cold outreach batch to remaining quota after personal mail |
| LinkedIn applications | **20–25/day** total automation safety ceiling per Context | Split across rows deterministically |
| Hunter.io / Apollo | Monthly enrichment budget | See `finops-sla-policy.md` |

---

## 5. LinkedIn Automation Fallback

When LinkedIn automation is unavailable, blocked, high-risk, or repeatedly failing:

1. Do **not** hammer retries.
2. Route row to **manual queue** with URL + drafts surfaced in daily summary.
3. Set execution outcome notes; leave row out of automated submission loop until operator resets status manually when permitted.

---

## 6. Logging and PII

- Log agent names, `job_id`, timestamps, and non-sensitive outcomes by default.
- Avoid logging full email bodies or recruiter PII in plaintext aggregation logs; reference sheet row_id/job_id only.

---

## Revision History

| Date | Change |
|------|--------|
| 2026-05-03 | Initial Phase 0 policy |

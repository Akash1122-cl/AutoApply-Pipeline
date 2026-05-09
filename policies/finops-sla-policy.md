# FinOps and SLA Policy

Version: v1 (Phase 0)

---

## 1. Cost Model Structure

Costs split into **fixed monthly**, **variable per-run**, and **usage-metered** buckets.

### 1.1 Fixed Monthly (examples — tune with real invoices)

| Item | Notes |
|------|------|
| Hosting / runner | GitHub Actions minutes OR VPS OR cloud scheduler |
| Dominant baseline subscriptions | Domain, minimal monitoring |

### 1.2 Variable Per Job Row

| Category | Driver |
|----------|--------|
| LLM (Claude / Anthropic) | Tokens for scoring, CV rewrite, ATS qualitative checks |
| Job APIs | Adzuna, SerpAPI, Otta/Cutshort where billed |
| Contact enrichment | Hunter.io / Apollo per-email lookup |
| Browser automation | Compute time if isolated runners |

### 1.3 Per-run Estimate (planning template)

Use before production scale-up:

```
estimated_monthly_cost =
  fixed_monthly
  + (avg_daily_new_rows × working_days × cost_per_row_pipeline)
  + enrichment_budget_cap
```

Maintain a spreadsheet OR append actuals into tracker metadata during Phase 10.

---

## 2. Monthly Budget Guardrails

| Tier | Action |
|------|--------|
| Expected spend | Normal operation |
| 80% of monthly cap | Warning alert (daily summary line item) |
| 100% of monthly cap | Stop metered calls (enrichment, optional LLM extras); continue human-approved execution only if zero marginal API cost |
| Over CAP due to bug | Incident note + rollback enrichment |

**Default placeholder caps (must be replaced with user numbers):**

- `MONTHLY_TOTAL_CAP_USD`: **TBD — owner: user**
- `ENRICHMENT_CAP_USD`: **TBD — owner: user**

---

## 3. Service Level Targets (v1 Defaults)

| SLA | Target |
|-----|--------|
| CP1 digest issued | Within **30 minutes** after Agent 1 batch completes |
| CP2 digest issued | Within **30 minutes** after Agent 3 batch completes |
| Human turnaround (CP1/CP2) | **24 hours** configurable |
| Escalation | Rows awaiting CP1/CP2 longer than human target appear under daily summary **`ATTENTION NEEDED`** |

SLA measurement uses orchestrator timestamps (`digest_generated_at`, row entered checkpoint state).

---

## 4. Reporting

Phase 10 MUST emit:

- Monthly burn vs cap
- Cost per successful `APPLIED` / `OUTREACH_SENT`
- SLA attainment % for CP1/CP2 digests

---

## Revision History

| Date | Change |
|------|--------|
| 2026-05-03 | Initial Phase 0 policy |

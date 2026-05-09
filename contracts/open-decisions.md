# Open Design Decisions — Tracking

Phase 0 exit criterion: each item has owner and target resolution date.

| ID | Topic | Options | Recommendation | Owner | Due |
|----|-------|---------|----------------|-------|-----|
| OD-01 | CV artifact format | Native Google Doc vs DOCX on Drive | DOCX for ATS; Doc easier to automate — pick one | Architect | TBD |
| OD-02 | CP1/CP2 UX | Email digest vs lightweight web UI | Email v1 | Architect | TBD |
| OD-03 | LinkedIn jobs source | Partner API vs Proxycurl vs scrape | Risk/legal tradeoff | Architect | TBD |
| OD-04 | Orchestrator hosting | Serverless vs VPS | VPS v1 per Context | Architect | TBD |
| OD-05 | Enrichment budget | Hunter/Apollo monthly cap | Set USD cap | User | TBD |
| OD-06 | Application daily cap | Fixed 20–25 vs configurable | Config with safe default | Architect | TBD |
| OD-07 | EU work permit rows | Flag only vs hard exclude | Flag only | Architect | TBD |
| OD-08 | Stale rows | Archive tab vs delete after N days | Archive sheet tab | Architect | TBD |
| OD-09 | MONITORING terminal policy | Days until NO_RESPONSE | Define window | Architect | TBD |
| OD-10 | `ATS_PASS` vs column-only | Discrete status vs `ats_pass` + EXECUTION | Pick one in Phase 1 | Architect | TBD |

---

## Revision History

| Date | Change |
|------|--------|
| 2026-05-03 | Initial Phase 0 tracker |

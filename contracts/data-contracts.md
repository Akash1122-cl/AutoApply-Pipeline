# Data Contracts — Pipeline Tracker, Inputs, Agent Payloads

Version: v1 (Phase 0)  
Aligned with: `Docs/Context.md`

---

## 1. Job Pipeline Tracker (Google Sheet)

Central shared store for pipeline rows and shared JSON-bearing columns where noted.

### 1.1 Column Schema

Pipe-separated shorthand matches Context; implement one header row per column:

| Column | Type | Required | Written By | Notes |
|--------|------|----------|------------|-------|
| `job_id` | string (UUID) | Yes | Agent 1 | Stable identifier |
| `company` | string | Yes | Agent 1 | Normalized display |
| `role_title` | string | Yes | Agent 1 | |
| `job_url` | URL string | Yes | Agent 1 | Dedup key component |
| `source_platform` | string | Yes | Agent 1 | e.g. Otta, Naukri |
| `date_scraped` | date (ISO YYYY-MM-DD) | Yes | Agent 1 | |
| `region` | string | Yes | Agent 1 | Taxonomy per Context |
| `work_mode` | enum | Yes | Agent 1 | `onsite` \| `hybrid` \| `remote` |
| `work_permit_required` | boolean | Yes | Agent 1 | Flag EU/right-to-work constraints |
| `fit_score` | number (0–100) | Yes post-score | Agent 1 | |
| `required_skills` | JSON array string | Yes post-score | Agent 1 | e.g. `["SQL","agile"]` |
| `human_action` | enum | CP1 | User | `Apply` \| `Outreach Only` \| `Skip` |
| `status` | enum | Yes | Orchestrator / Agents | See `state-machine-spec.md` |
| `cv_doc_link` | URL | CP2 path | Agent 3 | Tailored CV artifact |
| `email_draft_link` | URL or empty | CP2 path | Agent 3 | Optional Doc/link storage |
| `linkedin_dm_draft` | text | CP2 path | Agent 3 | Inline DM |
| `contact_name` | string | Optional | Agent 2 | |
| `contact_role` | string | Optional | Agent 2 | |
| `contact_email` | string | Optional | Agent 2 | Work email only |
| `contact_linkedin` | URL | Optional | Agent 2 | |
| `contact_found` | boolean | Recommended | Agent 2 | Context semantics |
| `email_verified` | boolean | Optional | Agent 2 | |
| `cp2_approved` | boolean | CP2 | User/System | **Phase 0 additive:** explicit approval gate |
| `cp2_approved_at` | ISO-8601 datetime | Optional | System | Audit |
| `ats_score` | number (0–100) | ATS path | Agent 3b | |
| `ats_pass` | boolean | ATS path | Agent 3b | Derived |
| `revision_count` | integer ≥ 0 | ATS loop | Orchestrator | Increment rules per Context |
| `applied_at` | ISO-8601 datetime | Optional | Agent 4 | |
| `outreach_sent_at` | ISO-8601 datetime | Optional | Agent 4 | |
| `response_received` | boolean | Optional | Monitoring | |
| `notes` | text | Optional | All | Errors, ATS gaps, `skill_gap: [...]` |
| `updated_at` | ISO-8601 datetime | Yes | System | Optimistic locking compare-and-set field |
| `row_version` | integer | Recommended | System | Monotonic version for conflict detection |

### 1.2 `human_action` Enum

Exactly one of: `Apply`, `Outreach Only`, `Skip`; blank allowed until CP1.

### 1.3 JSON Between Agents

**Normalized Job Row (logical)** — all agents SHOULD serialize/deserialize to this shape for interoperability:

```json
{
  "job_id": "uuid",
  "company": "string",
  "role_title": "string",
  "job_url": "https://...",
  "source_platform": "string",
  "date_scraped": "YYYY-MM-DD",
  "region": "string",
  "work_mode": "remote",
  "work_permit_required": false,
  "fit_score": 82,
  "required_skills": ["skill"],
  "human_action": "Apply",
  "status": "SCORED",
  "pipeline_refs": {
    "cv_doc_link": "",
    "email_draft_link": "",
    "linkedin_dm_draft": ""
  },
  "contact": {
    "contact_name": "",
    "contact_role": "",
    "contact_email": "",
    "contact_linkedin": "",
    "contact_found": false,
    "email_verified": false
  },
  "ats": {
    "ats_score": null,
    "ats_pass": null,
    "revision_count": 0
  },
  "gates": {
    "cp2_approved": false,
    "cp2_approved_at": null
  },
  "notes": ""
}
```

**ATS revision payload (Agent 3b → Agent 3):**

```json
{
  "job_id": "uuid",
  "failures": [
    { "check_id": "keyword_coverage", "detail": "string", "severity": "high" }
  ],
  "recommended_changes": ["string"],
  "revision_count_next": 1
}
```

**Daily digest stub (Orchestrator → Notification channel):**

```json
{
  "digest_type": "CP1",
  "generated_at": "ISO-8601",
  "rows": [{ "job_id": "uuid", "company": "", "role_title": "", "job_url": "", "fit_score": 0 }]
}
```

---

## 2. Read-only Inputs

### Master CV (Google Doc)

- Consumed only by Agent 3; agents MUST NOT mutate file content.

### Accomplishments Bank (Sheet columns)

Per Context:

```
Role | Company | Duration | Accomplishment | Skills Used | Metrics/Impact | Tags
```

---

## 3. Accomplishments Bank Column Contract

| Column | Type |
|--------|------|
| Role | string |
| Company | string |
| Duration | string |
| Accomplishment | string |
| Skills Used | string |
| Metrics/Impact | string |
| Tags | string |

Agent 3 MUST cross-reference Tags / Skills Used when injecting bullets—never invent unmatched claims.

---

## Revision History

| Date | Change |
|------|--------|
| 2026-05-03 | Initial Phase 0 contracts |

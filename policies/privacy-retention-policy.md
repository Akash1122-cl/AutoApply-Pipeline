# Data Retention and Privacy Policy

Version: v1 (Phase 0)  
Scope: AutoApply single-user deployment storing recruiter/contact data in Job Pipeline Tracker and operational logs.

---

## 1. Categories of Personal Data

| Category | Examples | Where Stored |
|----------|----------|----------------|
| Contact identity | Name, job title | Pipeline Tracker |
| Professional contact | Work email, LinkedIn URL | Pipeline Tracker |
| Communication artifacts | Email/DM draft text | Tracker / linked Docs |
| Application telemetry | Timestamps, status | Tracker |

---

## 2. Retention Period

| Data | Default Retention | Action After Period |
|------|-------------------|---------------------|
| Recruiter/contact fields (`contact_*`) | **90 days** from last update OR terminal row date—whichever policy variant implementation chooses (document in code) | **Delete or anonymize** contact columns; retain aggregate metrics |
| Row existence for analytics | Optional extended retention if contact columns stripped | Keep anonymized row with company/role/source counts only |
| Structured logs | **30 days** operational default | Rotate/redact PII |

Retention defaults align with `Docs/Architecture.md` cross-cutting recommendation.

---

## 3. Deletion / Anonymization Workflow

1. Identify rows past retention cutoff via scheduled job or manual audit.
2. For each row:
   - Clear `contact_name`, `contact_role`, `contact_email`, `contact_linkedin`.
   - Replace free-text `notes` containing emails with `[REDACTED]` if automated scanner flags PII.
3. Append audit entry (non-PII): `privacy_purge_at`, `job_id`, action taken.

---

## 4. Lawful Basis and Consent (High-level)

- **Personal job search tool:** lawful basis commonly **legitimate interests** (contacting recruiters about employment opportunities) — **not legal advice**; user must confirm applicability in their jurisdiction.
- Outreach only uses **work contact points**; no scraping personal/non-work emails (per Context).
- User MUST be able to export their sheet and trigger purge.

---

## 5. User Rights (Operational)

Support manual workflows until automated tooling lands:

- **Access:** Google Sheet export.
- **Erasure:** Row delete or column purge per §3.
- **Restriction:** Pause Agent 4 sends via config kill-switch.

---

## Revision History

| Date | Change |
|------|--------|
| 2026-05-03 | Initial Phase 0 policy |

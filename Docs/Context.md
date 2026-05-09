# context.md — AutoApply: Multi-Agent Job Application System

> **READ THIS FIRST.**
> This file is the single source of context for building AutoApply.
> Do not make assumptions outside what is defined here.
> When in doubt, refer back to this file.

---

## WHAT WE ARE BUILDING

A personal, single-user, multi-agent AI pipeline that automates the end-to-end APM job application workflow — from daily discovery to executed applications — with human approval gates before anything is sent.

**Role being applied for:** Associate Product Manager (APM) / Associate PM  
**User location:** Bengaluru, India  
**Schedule:** Runs daily at 9:00 AM IST automatically  
**North star:** Maximum reach + ATS pass rate + personalised outreach + zero fabricated experience

---

## AGENT MAP (5 components)

```
ORCHESTRATOR
    |
    |-- AGENT 1   Scout & Qualify      (discover + score jobs)
    |-- AGENT 2   Contact Discovery    (find recruiter / hiring manager)
    |-- AGENT 3   Content Generation   (CV + cold email + LinkedIn DM)
    |-- AGENT 3b  ATS Reviewer         (score CV, loop max 2x)
    `-- AGENT 4   Execution & Tracking (apply + send + monitor replies)
```

**Human checkpoints exist at:**
- After Agent 1 -> user reviews shortlist (Apply / Outreach Only / Skip)
- After Agent 3 -> user reviews CV + email draft + LinkedIn DM before anything is sent

**Nothing is submitted or sent without explicit human approval.**

---

## TARGET GEOGRAPHIES

Agent 1 must search ALL of these simultaneously.

| Priority | Region | Locations |
|---|---|---|
| Primary | India | Pan-India — Bengaluru, Mumbai, Delhi, Hyderabad, Pune, Chennai + remote |
| Priority | Europe | Poland (Warsaw, Krakow), Norway (Oslo, Bergen) |
| Secondary | Europe | Germany, Netherlands, UK, Sweden, Ireland |
| Secondary | Southeast Asia | Singapore (primary), Malaysia/KL (secondary) |

**Include:** on-site in target cities, hybrid in target cities, remote open to India/SEA/EU  
**Exclude:** roles explicitly requiring US/Australia-only citizenship  
**Flag (don't auto-exclude):** EU citizenship required -> mark `work_permit_required = true` for human review  
Each job row must have: `region` and `work_mode` (onsite / hybrid / remote) fields

---

## SOURCE OF TRUTH INPUTS

> These are READ-ONLY. No agent ever writes to or modifies these.

| Input | Type | Location | Used By |
|---|---|---|---|
| Master CV | Google Doc | Google Drive | Agent 3 |
| Accomplishments Bank | Google Sheet | Google Drive | Agent 3 |
| Job Pipeline Tracker | Google Sheet | Google Drive | All agents (read + write) |

### Accomplishments Bank — Column Schema
```
Role | Company | Duration | Accomplishment | Skills Used | Metrics/Impact | Tags
```

Example:
```
Product Intern | XYZ Corp | Jun-Aug 2023 | Led redesign of onboarding flow | Figma, User Research, A/B Testing | 23% drop in drop-off rate | onboarding, ux, retention
```

---

## JOB PIPELINE TRACKER — GOOGLE SHEET SCHEMA

This sheet is the central state machine. Every agent reads from and writes status to this sheet.

```
job_id | company | role_title | job_url | source_platform | date_scraped |
region | work_mode | work_permit_required | fit_score | required_skills (JSON) |
human_action | status |
cv_doc_link | email_draft_link | linkedin_dm_draft |
contact_name | contact_role | contact_email | contact_linkedin | email_verified |
ats_score | ats_pass | revision_count |
applied_at | outreach_sent_at | response_received | notes
```

### `human_action` values
`Apply` | `Outreach Only` | `Skip`

### `status` — Full State Machine

```
SCRAPED
  -> SCORED
  -> AWAITING_HUMAN_REVIEW          <- CP1: user sets human_action

[if Apply or Outreach Only]
  -> CONTACT_DISCOVERY
  -> CONTENT_GENERATION
  -> AWAITING_CONTENT_REVIEW        <- CP2: user approves assets

[if approved]
  -> ATS_REVIEW
    -> ATS_PASS                     -> EXECUTION -> APPLIED / OUTREACH_SENT
    -> ATS_FAIL (revision_count < 2) -> CONTENT_GENERATION   [revision loop]
    -> HUMAN_REVIEW (revision_count >= 2)                    [loop stops here]

  -> MONITORING
    -> RESPONSE_RECEIVED
    -> NO_RESPONSE

Terminal states: APPLIED, SKIPPED, HUMAN_REVIEW, FAILED
```

### Deduplication Rule
Before Agent 1 writes any row: check if `(company + role_title + job_url)` already exists in the sheet. If yes -> skip. Never create duplicate rows.

---

## ORCHESTRATOR — main.py

**Role:** Central controller. Triggers agents in sequence, enforces state, manages checkpoints, prevents loops, sends daily summary.

### Daily Execution Flow
```
09:00 AM IST
  |
  |-- Trigger Agent 1
  |     `-- Writes SCRAPED + SCORED rows to Sheet
  |
  |-- Send CP1 digest to user (email or Slack)
  |     `-- Wait for human_action to be set on each row
  |
  |-- For each row where human_action = Apply or Outreach Only:
  |     |-- Trigger Agent 2 (Contact Discovery)
  |     `-- Trigger Agent 3 (Content Generation)
  |
  |-- Send CP2 digest to user (CV + drafts for review)
  |     `-- Wait for approval
  |
  |-- For each approved row:
  |     |-- Trigger Agent 3b (ATS Review) — max 2 cycles
  |     `-- Trigger Agent 4 (Execution)
  |
  `-- Send daily summary report
```

### Loop Prevention — HARD RULE
- If ATS fails AND `revision_count < 2` -> increment count, send back to Agent 3 with feedback
- If ATS fails AND `revision_count >= 2` -> set `HUMAN_REVIEW`, **stop. do not loop again.**

### Failure Handling
- Any agent throws error on a row -> set status `FAILED`, log to `notes`, continue pipeline for all other rows
- Never auto-retry failed rows
- Surface all FAILED rows in daily summary

---

## AGENT 1 — Scout & Qualify

**Input:** Target geographies + role keywords  
**Output:** Ranked, scored job rows written to Pipeline Tracker

### Job Sources

| Source | Method | Geography |
|---|---|---|
| LinkedIn Jobs | LinkedIn Jobs API or MCP | Global |
| Otta | API / scrape | Europe — key for Poland/Norway |
| Wellfound | API / scrape | Global startups |
| Naukri | RSS / scrape | India |
| Cutshort | API | India APM-specific |
| Adzuna | Free API | India + Europe |
| SerpAPI (Google Jobs) | API | Global fallback |
| Bayt | Scrape | SEA / Malaysia |
| DuckDuckGo MCP | Search | Last resort fallback |

### Search Query Pattern
```
"Associate Product Manager" [city or country] 2025
"APM" "Associate PM" entry level [city]
"Associate PM" [domain: fintech / SaaS / consumer] [city]
```
Run one query batch per region: India / Europe-PL-NO / Europe-Other / SEA

### Fit Scoring (0-100 per job)

| Factor | Weight |
|---|---|
| Role title match (APM / Associate PM > PM > Product) | 25% |
| Seniority fit (0-3 yrs required = high) | 20% |
| Domain alignment (fintech/SaaS/consumer > industrial) | 20% |
| Geography preference (target city or remote = high) | 15% |
| Company type (startup/scaleup > enterprise for APM) | 10% |
| Recency (posted <3 days = high; >14 days = low) | 10% |

**Minimum score to include in shortlist: 60** (configurable)  
**Target output:** 10-30 new jobs per daily run across all geographies

### Output per job row
```json
{
  "job_id": "uuid",
  "company": "Company Name",
  "role_title": "Associate Product Manager",
  "job_url": "https://...",
  "source_platform": "Otta",
  "date_scraped": "2025-05-01",
  "region": "Europe-PL",
  "work_mode": "hybrid",
  "work_permit_required": false,
  "fit_score": 82,
  "required_skills": ["SQL", "roadmapping", "stakeholder management", "agile"],
  "status": "SCORED"
}
```

---

## AGENT 2 — Contact Discovery

**Input:** Approved job rows (human_action = Apply or Outreach Only)  
**Output:** Contact fields populated in Pipeline Tracker

### Contact Priority
1. Recruiter handling the role
2. Hiring Manager / direct APM manager
3. Head of Product / CPO
4. Founder (early-stage startups only)

### Discovery Methods
- LinkedIn search: `"recruiter" OR "talent acquisition" [company name]`
- Hunter.io API or Apollo.io API for email lookup
- Email pattern inference: `firstname@company.com`, `f.lastname@company.com`
- MX record validation to confirm deliverability

### Output fields written to sheet
```json
{
  "contact_name": "Jane Doe",
  "contact_role": "Technical Recruiter",
  "contact_email": "jane@company.com",
  "contact_linkedin": "https://linkedin.com/in/janedoe",
  "email_verified": true
}
```

**If no contact found:** leave fields blank, set `contact_found = false`, continue pipeline — do not block  
**Never store:** personal/non-work email addresses

---

## AGENT 3 — Content Generation

**Input:** Job row (required_skills, JD, contact info, company context), Master CV, Accomplishments Bank  
**Input on revision:** ATS feedback from Agent 3b  
**Output:** 3 assets per job — (1) tailored CV, (2) cold email draft, (3) LinkedIn DM draft

### Asset 1 — Tailored CV

```
1. Read required_skills from job row
2. Read Master CV (baseline structure + experience)
3. Query Accomplishments Bank: match Tags / Skills Used to required_skills
4. Rewrite CV:
   - Reorder bullets: most relevant accomplishments surface first
   - Embed JD keywords naturally into bullets
   - Pull quantified metrics from Accomplishments Bank
   - Rewrite Summary/Objective to mirror role language
5. Save as new Google Doc: "[Company]_APM_CV_[YYYY-MM-DD]"
6. Write Doc URL to cv_doc_link in Pipeline Tracker
```

**HARD RULES — non-negotiable:**
- NEVER fabricate experience, projects, metrics, or skills
- NEVER write a skill into the CV that has no matching entry in Accomplishments Bank or Master CV
- NEVER modify Master CV or Accomplishments Bank
- If a required skill has no match -> log `skill_gap: [skill name]` in notes column
- On revision runs -> address specific ATS failures flagged by Agent 3b

### Asset 2 — Cold Email Draft

```
Subject: [Role Title] at [Company] — [one relevant hook]

Hi [Contact Name],

[1 sentence: connect their product/company to a specific interest or observation]
[1 sentence: your most relevant accomplishment for this domain with a metric]
[1 sentence: low-friction CTA — 15-min call or ask to forward to hiring manager]

[Name]
```

### Asset 3 — LinkedIn DM Draft

Max 300 characters. Direct, not salesy.

```
Hi [Name] — saw [Company] is hiring an APM. [One relevant line about background].
Would love to connect — happy to share my CV.
```

---

## AGENT 3b — ATS Reviewer

**Input:** Tailored CV Doc link from Agent 3  
**Output:** `ats_score`, `ats_pass`, updated `revision_count`, specific failure reasons in `notes`

### ATS Checks

| Category | Rule |
|---|---|
| Layout | Single-column only — no multi-column, no tables |
| File type | .docx preferred |
| Section headers | Must use: Summary, Experience, Education, Skills |
| Keyword coverage | >= 60% of required_skills appear in CV body |
| Bullet structure | Action verb + task + measurable outcome |
| Length | <= 1 page for <3 yrs experience; <= 2 pages max |
| Contact block | Name, email, phone, LinkedIn at very top |
| No headers/footers | ATS ignores content inside them |
| Date format | Consistent MM/YYYY or Month YYYY throughout |
| No graphics/logos | Images, icons, charts break ATS parsers |

**Score = (checks passed / total checks) × 100**  
**Pass threshold = >= 80**

### Decision Logic
```
score >= 80                          -> status = ATS_PASS
score < 80 AND revision_count < 2    -> revision_count++, write failures to notes, status = CONTENT_GENERATION
score < 80 AND revision_count >= 2   -> status = HUMAN_REVIEW  <- STOP. no more loops.
```

**Implementation note:** Use rule-based checks for format/structure + Claude prompt for keyword coverage and bullet quality. Do NOT call Greenhouse / Workday / Lever APIs — they have no public scoring endpoints.

---

## AGENT 4 — Execution & Tracking

**Input:** Rows with status = ATS_PASS  
**Output:** Applications submitted, outreach sent, statuses updated, replies monitored

### Submission Methods

| Channel | Method |
|---|---|
| LinkedIn Easy Apply | Playwright browser automation |
| Company career portals | Playwright form-fill where feasible |
| Cold email | Gmail MCP |
| LinkedIn DM | LinkedIn MCP or Playwright |
| Not automatable | Add to MANUAL_QUEUE, surface in summary |

### Execution Flow
```
1. Read all rows: status = ATS_PASS AND human_action = Apply
2. For each row:
   a. Submit application (LinkedIn Easy Apply or company portal)
   b. Send cold email via Gmail MCP if contact_email exists
   c. Send LinkedIn DM if contact_linkedin exists
   d. Set: status = APPLIED, applied_at = [timestamp]

3. MANUAL_QUEUE rows: include job URL + draft content in daily summary

4. [Daily monitoring — runs alongside main pipeline]
   a. Poll Gmail inbox for replies to outreach emails (via Gmail MCP)
   b. If reply found: status = RESPONSE_RECEIVED, log snippet in notes
   c. Surface in daily summary
```

### Rules
- **Never submit to the same job_url twice** — check status column before every action
- **Never send email or DM without CP2 human approval** — check approved flag first
- **Daily application cap: 20-25 max** — LinkedIn flags automation above this threshold
- **On submission failure:** status = FAILED, log error, do not retry automatically

---

## HUMAN CHECKPOINTS — SUMMARY

| # | Name | Trigger | User Does |
|---|---|---|---|
| CP1 | Shortlist Review | Agent 1 completes | Set `human_action` = Apply / Outreach Only / Skip per row |
| CP2 | Content Review | Agent 3 completes | Approve or edit CV, email draft, LinkedIn DM per row |
| CP3 | Human Review Queue | ATS failed 2x OR agent error | Manually fix CV or mark skip |

**Delivery method for CP1 and CP2:** email digest or Slack message (configurable — architect to decide)

---

## DAILY SUMMARY REPORT FORMAT

Sent by Orchestrator after pipeline completes. Delivery: email or Slack.

```
AutoApply Daily Report — [DATE]
================================

DISCOVERY
  New jobs found:               [n]
  In shortlist (score >= 60):   [n]   <- awaiting your review at CP1

PIPELINE
  Contacts found:               [n] / [n approved]
  CVs tailored:                 [n]
  ATS passed (1st attempt):     [n]
  ATS passed (after revision):  [n]

EXECUTION
  Applications submitted:       [n]
  Cold emails sent:             [n]
  LinkedIn DMs sent:            [n]
  Manual queue (needs you):     [n]

RESPONSES
  New replies in inbox:         [n]   <- details below

ATTENTION NEEDED
  Human review queue:           [n]   <- ATS failed 2x or errors
  Skill gaps detected:          [list — add these to Accomplishments Bank]

MANUAL QUEUE
  [Company] — [Role] — [URL]
  ...
================================
```

---

## TECH STACK

| Component | Tool | Notes |
|---|---|---|
| Agent orchestration | LangGraph or CrewAI | Loop prevention + state management built in |
| LLM | Claude via Anthropic API | All generation, scoring, ATS evaluation |
| Scheduling | GitHub Actions cron or AWS EventBridge | 9 AM IST = 3:30 AM UTC |
| Job scraping | Adzuna API + SerpAPI + Otta + Cutshort + LinkedIn Jobs API | Multi-source |
| Google Drive + Sheets | Google Drive MCP + Google Sheets API | User has Drive MCP connected |
| Contact enrichment | Hunter.io API or Apollo.io API | Email lookup + MX validation |
| CV output | python-docx -> saved to Google Drive | .docx is most ATS-compatible format |
| Browser automation | Playwright | LinkedIn Easy Apply + company portals |
| Email sending | Gmail MCP | Send cold outreach after CP2 approval |
| LinkedIn DMs | LinkedIn MCP or Playwright | After CP2 approval |
| Response monitoring | Gmail MCP polling | Check inbox for replies daily |
| Notifications | Gmail API or Slack webhook | CP1 digest, CP2 digest, daily summary |

---

## GOOGLE DRIVE MCP — INTEGRATION NOTES

User has **Google Drive MCP already connected**. All file and sheet operations must use this MCP.

| Operation | Agent | Method |
|---|---|---|
| Read Master CV | Agent 3 | Drive MCP -> read Google Doc |
| Read Accomplishments Bank | Agent 3 | Drive MCP -> read Google Sheet |
| Read/Write Pipeline Tracker | All agents | Drive MCP -> read/write Google Sheet |
| Create tailored CV | Agent 3 | Drive MCP -> create new Google Doc |
| Update tailored CV (revision) | Agent 3 | Drive MCP -> update existing Google Doc |

---

## DESIGN PRINCIPLES — NON-NEGOTIABLE

1. **Human-in-loop control** — AI drafts, human decides. Nothing sends without CP2 approval
2. **No fabricated experience** — Agent 3 reads only from Master CV + Accomplishments Bank
3. **Idempotency** — Check state before every action. Zero duplicate applications or messages
4. **Hard loop cap** — Max 2 ATS revision cycles per job row. Then HUMAN_REVIEW, full stop
5. **Graceful failure** — One row failing never blocks the rest of the pipeline
6. **Modular agents** — Each agent is independently replaceable
7. **Structured state** — Google Sheet is the only shared state store. JSON between agents
8. **Full audit trail** — Every action timestamped and logged in the sheet
9. **Read-only source inputs** — Master CV and Accomplishments Bank are never touched by agents
10. **Naming convention** — All tailored CVs saved as: `[Company]_APM_CV_[YYYY-MM-DD]`

---

## OUT OF SCOPE — v1

- Cover letter generation
- Interview scheduling
- Post-application follow-up email sequences
- Roles other than APM / Associate PM
- Geographies outside the defined list above
- Third-party ATS vendor APIs (Greenhouse, Lever, Workday have no public scoring endpoints)

---

## OPEN QUESTIONS — FOR ARCHITECT TO DECIDE

1. **CV format:** .docx stored in Google Drive (recommended, best ATS compat) vs native Google Doc (easier to programmatically edit). Pick one and implement consistently.
2. **Checkpoint delivery:** Email digest vs lightweight web UI for CP1/CP2 review. Email is simpler for v1.
3. **LinkedIn data source:** Official LinkedIn Jobs API (needs partner access) vs Proxycurl (paid, compliant wrapper) vs direct scraping (ToS risk). Architect to define acceptable approach.
4. **Orchestrator hosting:** AWS Lambda / GCP Cloud Functions (serverless, cheaper) vs VPS (persistent, easier to debug). Recommend VPS for v1.
5. **Contact enrichment budget:** Hunter.io and Apollo.io have per-request costs. Set a monthly cap before implementation.
6. **Daily application cap:** Default set to 20-25/day for LinkedIn safety. Confirm if user wants this adjustable.
7. **EU work permit logic:** Flag `work_permit_required = true` and include in shortlist for human review (recommended) vs hard-exclude from pipeline.
8. **Stale row policy:** Rows with no action for 30+ days -> archive to separate sheet tab or delete?

---

## BUILD SEQUENCE — RECOMMENDED ORDER

```
1. Orchestrator skeleton (state machine + scheduler + summary sender)
2. Agent 1 (Scout + Qualify) + Pipeline Tracker sheet setup
3. CP1 checkpoint notification
4. Agent 2 (Contact Discovery)
5. Agent 3 (Content Generation — CV first, then email + DM)
6. CP2 checkpoint notification
7. Agent 3b (ATS Reviewer)
8. Agent 4 (Execution — email first, then Easy Apply automation)
9. Response monitoring loop
10. Daily summary report
11. End-to-end integration test
```

---

*context.md — AutoApply v2.0 | Single-user multi-agent APM job application system | Do not modify this file during implementation — treat as the spec.*

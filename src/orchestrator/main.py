from __future__ import annotations

import os
from dotenv import load_dotenv
load_dotenv()

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from src.orchestrator.run_lock_manager import run_lock
from src.orchestrator.state_engine import (
    TransitionContext,
    validate_transition,
)
from src.shared.run_logger import RunLogger
from src.shared.sheets_gateway import SheetsGateway
from src.agent_1.pipeline import Agent1Pipeline
from src.checkpoints.cp1_digest import generate_cp1_digest
from src.checkpoints.cp1_action_sync import sync_cp1_actions
from src.checkpoints.cp2_digest import generate_cp2_digest
from src.checkpoints.cp2_approval_sync import CP2ApprovalSync, reset_cp2_fields_for_fresh_review
from src.checkpoints.cp2_validators import CP2Validator
from src.agent_2.pipeline import ContactDiscoveryAgent
from src.agent_3.pipeline import ContentGenerationAgent
from src.agent_3.fabrication_guard import FabricationError
from src.agent_3b.pipeline import ATSReviewAgent
from src.agent_3b.ats_constants import MAX_ATS_REVISIONS
from src.agent_4.pipeline import ExecutionAgent
from src.agent_9.response_monitor import ResponseMonitor
from src.agent_10.reporting_engine import ReportingEngine

IST = ZoneInfo("Asia/Kolkata")


class Orchestrator:
    """Phase 1 orchestrator skeleton with state guards and row-level fault isolation."""

    def __init__(self, sheets: SheetsGateway, logger: RunLogger) -> None:
        self.sheets = sheets
        self.logger = logger

    @staticmethod
    def should_run_now(now: datetime) -> bool:
        local = now.astimezone(IST)
        return local.hour == 9 and (0 <= local.minute <= 15)

    async def run_once(self) -> None:
        await self._process_discovery_phase()
        await self._process_scoring_phase()
        await self._process_qualification_gate()
        self.sheets.commit()
        
        # Phase 3 Checkpoints
        generate_cp1_digest(self.sheets, self.logger)
        await self._process_human_review_gate()
        self.sheets.commit()
        
        # Phase 4 Contact Discovery
        await self._process_contact_discovery()
        self.sheets.commit()
        

        # Phase 6: Content Generation (CVs & Emails)
        await self._process_content_generation()
        self.logger.increment("cvs_generated", len(self.sheets.get_rows_by_status("AWAITING_CONTENT_REVIEW")))
        self.sheets.commit()

        # Phase 6.5: Content Review Gate (CP2)
        await self._process_content_review_gate()
        self.sheets.commit()

        # Phase 7: ATS Review
        await self._process_ats_review()
        self.sheets.commit()

        # Phase 8: Execution (Submissions & Outreach)
        await self._process_execution()
        self.sheets.commit()

        # Phase 9: Response Monitoring
        await self._process_monitoring()
        self.sheets.commit()

        self._summary_stub()

    async def _process_discovery_phase(self) -> None:
        pipeline = Agent1Pipeline()
        existing_keys = self.sheets.get_existing_dedup_keys()
        new_jobs = await asyncio.to_thread(pipeline.run, existing_keys)
        if new_jobs:
            self.sheets.add_rows(new_jobs)
            self.logger.increment("jobs_discovered", len(new_jobs))

    async def _process_scoring_phase(self) -> None:
        for row in self.sheets.get_rows_by_status("SCRAPED"):
            self._safe_transition(row, "SCORED", TransitionContext())
            self.logger.increment("jobs_scored")

    async def _process_qualification_gate(self) -> None:
        for row in self.sheets.get_rows_by_status("SCORED"):
            score = row.get("score", 0)
            if score >= 60:
                self._safe_transition(row, "AWAITING_HUMAN_REVIEW", TransitionContext())
                self.logger.increment("jobs_qualified")
            else:
                self._safe_transition(row, "SKIPPED", TransitionContext())
                self.logger.increment("jobs_disqualified")

    def _safe_transition(self, row: dict, nxt: str, ctx: TransitionContext) -> None:
        job_id = row["job_id"]
        current = row["status"]
        expected_updated_at = row.get("updated_at")
        try:
            validate_transition(current, nxt, ctx)
            self.sheets.update_row(
                job_id,
                {"status": nxt},
                expected_updated_at=expected_updated_at,
            )
        except Exception as exc:  # noqa: BLE001 - keep pipeline alive
            # Optimistic lock conflict: re-read latest row and retry once.
            if "Write conflict" in str(exc):
                self.logger.record_error(job_id, "orchestrator", f"Conflict detected: {exc}")
                latest = self.sheets.get_row(job_id)
                try:
                    validate_transition(latest["status"], nxt, ctx)
                    self.sheets.update_row(
                        job_id,
                        {"status": nxt},
                        expected_updated_at=latest.get("updated_at"),
                    )
                    self.logger.record_error(job_id, "orchestrator", "Conflict recovered on retry")
                    return
                except Exception as retry_exc:  # noqa: BLE001
                    self.logger.record_error(job_id, "orchestrator", f"Conflict unresolved: {retry_exc}")
                    self.sheets.set_failed(job_id, "orchestrator", f"Conflict unresolved: {retry_exc}")
                    return

            self.logger.record_error(job_id, "orchestrator", str(exc))
            self.sheets.set_failed(job_id, "orchestrator", str(exc))

    async def _process_human_review_gate(self) -> None:
        sync_cp1_actions(self.sheets, self.logger, self._safe_transition)

    async def _process_content_review_gate(self) -> None:
        generate_cp2_digest(self.sheets, self.logger)
        sync = CP2ApprovalSync(self.sheets, self.logger, self._safe_transition)
        await sync.check_and_process()

    async def _process_execution(self) -> None:
        """Phase 8: Execute all rows that passed ATS review."""
        rows = self.sheets.get_rows_by_status("APPROVED_FOR_EXECUTION")
        if not rows:
            return

        metrics = {
            "rows_processed": 0,
            "applied": 0,
            "outreach_sent": 0,
            "manual_queued": 0,
            "failed": 0,
            "skipped": 0,
            "safety_blocked": 0,
        }

        agent = ExecutionAgent(self.logger)

        for row in rows:
            # Enforce daily application cap (maximum 25 per day) to prevent LinkedIn automation bans
            if agent.usage.applications_submitted >= 25:
                self.logger.record_error("phase_8", "execution", "Daily application cap (25) reached. Pausing remaining executions.")
                break

            job_id = row["job_id"]
            try:
                result = await agent.execute_row(row)
                metrics["rows_processed"] += 1

                final_status = result["final_status"]
                notes_append = result.get("notes_append", "")
                existing_notes = row.get("notes", "")
                new_notes = f"{existing_notes}\n{notes_append}".strip() if notes_append else existing_notes

                # Persist timestamps
                patch = {"notes": new_notes}
                if result.get("applied_at"):
                    patch["applied_at"] = result["applied_at"]
                    self.logger.increment("applications_submitted")
                if result.get("outreach_sent_at"):
                    patch["outreach_sent_at"] = result["outreach_sent_at"]
                    # Distinguish email vs linkedin if possible, or just increment both/one
                    if "Email sent" in notes_append:
                        self.logger.increment("emails_sent")
                    if "LinkedIn DM sent" in notes_append:
                        self.logger.increment("linkedin_dms_sent")
                self.sheets.update_row(job_id, patch)

                # Safety-blocked rows already had notes written above; count them
                if "safety gate" in (result.get("error") or "").lower():
                    metrics["safety_blocked"] += 1

                self._safe_transition(row, final_status, TransitionContext())

                key = final_status.lower()
                if key in metrics:
                    metrics[key] += 1

                self.logger.record_error(
                    job_id,
                    "agent4",
                    f"Execution complete: {final_status}",
                )

            except Exception as exc:  # noqa: BLE001
                existing_notes = row.get("notes", "")
                self.sheets.update_row(
                    job_id,
                    {"notes": f"{existing_notes}\n[Agent4] Unexpected error: {exc}".strip()},
                )
                self._safe_transition(row, "FAILED", TransitionContext())
                self.logger.record_error(job_id, "agent4", f"Unexpected error: {exc}")
                metrics["failed"] += 1

        self.logger.record_error("phase_8", "execution", f"Metrics: {metrics}")

    async def _process_monitoring(self) -> None:
        """Phase 9: Poll for replies on all active applications."""
        active_statuses = ["APPLIED", "OUTREACH_SENT", "MONITORING"]
        rows_to_monitor = []
        for status in active_statuses:
            rows_to_monitor.extend(self.sheets.get_rows_by_status(status))

        if not rows_to_monitor:
            return

        monitor = ResponseMonitor(self.logger)
        updates = await monitor.poll_and_process(rows_to_monitor)

        for update in updates:
            job_id = update["job_id"]
            row = self.sheets.get_row(job_id)
            
            # Persist notes
            existing_notes = row.get("notes", "")
            notes_append = update.get("notes_append", "")
            new_notes = f"{existing_notes}\n{notes_append}".strip() if notes_append else existing_notes
            
            self.sheets.update_row(job_id, {
                "notes": new_notes,
                "response_received": update["response_received"]
            })
            
            # Transition to RESPONSE_RECEIVED
            self._safe_transition(row, update["status"], TransitionContext())
            self.logger.record_error(job_id, "monitor", f"Status changed to {update['status']}")
            self.logger.increment("responses_tracked")

        # For remaining rows, move them to MONITORING if they were in APPLIED/OUTREACH_SENT
        updated_ids = {u["job_id"] for u in updates}
        for row in rows_to_monitor:
            if row["job_id"] not in updated_ids and row["status"] in ["APPLIED", "OUTREACH_SENT"]:
                self._safe_transition(row, "MONITORING", TransitionContext())
                self.logger.record_error(row["job_id"], "monitor", "Moving to MONITORING holding state")

    def _summary_stub(self) -> None:
        """Phase 10: Generate and save daily summary report."""
        try:
            reporter = ReportingEngine(self.logger, self.sheets)
            report = reporter.generate_daily_report()
            
            # Use relative path from CWD for reliability
            report_dir = Path("logs/reports")
            report_dir.mkdir(parents=True, exist_ok=True)
            report_file = report_dir / f"report-{self.logger.run_id}.md"
            
            report_file.write_text(report, encoding="utf-8")
            
            print("\n" + report)
            print(f"\nReport saved to: {report_file}")
        except Exception as e:
            self.logger.record_error("run", "reporting", f"Failed to generate report: {e}")
            print(f"ERROR in reporting: {e}")

    async def _process_ats_review(self) -> None:
        """Phase 7: Run ATS evaluation on all rows in ATS_REVIEW state."""
        rows = self.sheets.get_rows_by_status("ATS_REVIEW")
        if not rows:
            return

        metrics = {
            "rows_processed": 0,
            "ats_pass": 0,
            "ats_fail_regenerating": 0,
            "ats_fail_human_review": 0,
            "bypass_attempts_caught": 0,
            "extraction_failures": 0,
        }

        agent = ATSReviewAgent(self.logger)

        for row in rows:
            job_id = row["job_id"]

            # ── SAFETY NET: CP2 must have been explicitly approved ───────────
            validator = CP2Validator()
            is_valid, issues = validator.validate_for_ats_review(row)
            if not is_valid:
                existing_notes = row.get("notes", "")
                self.sheets.update_row(
                    job_id,
                    {
                        "notes": f"{existing_notes}\n[SAFETY] CP2 bypass detected: {'; '.join(issues)}".strip()
                    },
                )
                self._safe_transition(
                    row, "AWAITING_CONTENT_REVIEW", TransitionContext()
                )
                self.logger.record_error(
                    job_id, "ats_review", f"Bypass attempt caught: {issues}"
                )
                metrics["bypass_attempts_caught"] += 1
                continue

            try:
                result = await agent.review_cv(row)
                
                # Metrics for reporting
                if result and result.get("ats_pass"):
                    if row.get("revision_count", 0) == 0:
                        self.logger.increment("ats_pass_first_try")
                    else:
                        self.logger.increment("ats_pass_after_revision")

                if result is None:  # idempotency skip
                    continue

                metrics["rows_processed"] += 1

                # Unrecoverable extraction failure
                if result.get("status") == "FAILED":
                    existing_notes = row.get("notes", "")
                    self.sheets.update_row(
                        job_id,
                        {
                            "notes": f"{existing_notes}\n[ATS] Extraction failed: {result['error']}".strip()
                        },
                    )
                    self._safe_transition(row, "FAILED", TransitionContext())
                    metrics["extraction_failures"] += 1
                    continue

                # Persist score fields
                self.sheets.update_row(
                    job_id,
                    {
                        "ats_score": result["ats_score"],
                        "ats_pass": result["ats_pass"],
                        "ats_review_attempted_at": result["ats_review_attempted_at"],
                    },
                )

                # ── Routing decision ────────────────────────────────────────
                if result["ats_pass"]:
                    self._safe_transition(
                        row,
                        "APPROVED_FOR_EXECUTION",
                        TransitionContext(ats_pass=True),
                    )
                    metrics["ats_pass"] += 1
                    self.logger.record_error(
                        job_id,
                        "ats_review",
                        f"PASSED ATS (score={result['ats_score']}) → APPROVED_FOR_EXECUTION",
                    )

                else:
                    revision_count = int(row.get("revision_count", 0))

                    if revision_count < MAX_ATS_REVISIONS:
                        new_count = revision_count + 1
                        existing_notes = row.get("notes", "")
                        new_notes = f"{existing_notes}\n{result['feedback']}".strip()

                        self.sheets.update_row(
                            job_id,
                            {"revision_count": new_count, "notes": new_notes},
                        )
                        # Fresh CP2 fields — prevents stale auto-approval
                        reset_cp2_fields_for_fresh_review(job_id, self.sheets)

                        # Update row snapshot so safe_transition sees correct state
                        row["revision_count"] = new_count
                        self._safe_transition(
                            row,
                            "CONTENT_GENERATION",
                            TransitionContext(ats_pass=False, revision_count=new_count),
                        )
                        metrics["ats_fail_regenerating"] += 1
                        self.logger.record_error(
                            job_id,
                            "ats_review",
                            f"FAILED ATS (score={result['ats_score']}) — regenerating "
                            f"(attempt {new_count}/{MAX_ATS_REVISIONS})",
                        )

                    else:
                        existing_notes = row.get("notes", "")
                        self.sheets.update_row(
                            job_id,
                            {
                                "notes": f"{existing_notes}\n[ATS] Failed {MAX_ATS_REVISIONS} times — manual intervention required".strip()
                            },
                        )
                        self._safe_transition(
                            row,
                            "HUMAN_REVIEW",
                            TransitionContext(ats_pass=False, revision_count=revision_count),
                        )
                        metrics["ats_fail_human_review"] += 1
                        self.logger.record_error(
                            job_id,
                            "ats_review",
                            f"FAILED ATS {MAX_ATS_REVISIONS} times — escalated to HUMAN_REVIEW",
                        )

            except Exception as exc:  # noqa: BLE001
                existing_notes = row.get("notes", "")
                self.sheets.update_row(
                    job_id,
                    {"notes": f"{existing_notes}\n[ATS] Unexpected error: {exc}".strip()},
                )
                self._safe_transition(row, "FAILED", TransitionContext())
                self.logger.record_error(job_id, "ats_review", f"Unexpected error: {exc}")

        self.logger.record_error(
            "phase_7",
            "ats_review",
            f"Metrics: {metrics}",
        )

    async def _process_contact_discovery(self) -> None:
        agent = ContactDiscoveryAgent(self.logger)
        rows = self.sheets.get_rows_by_status("CONTACT_DISCOVERY")
        
        # Sort: paused rows first
        rows.sort(key=lambda x: not x.get("contact_discovery_paused", False))
        
        hunter_api_calls = 0
        rows_processed = 0
        contacts_found = 0
        contacts_not_found = 0
        
        for i, row in enumerate(rows):
            job_id = row["job_id"]
            try:
                enriched_row = await agent.discover_contact(row)
                rows_processed += 1
                
                # We count a hunter call for every row processed for now
                hunter_api_calls += 1 
                
                if enriched_row.get("contact_email") or enriched_row.get("contact_name"):
                    contacts_found += 1
                    self.logger.increment("contacts_found")
                else:
                    contacts_not_found += 1
                    
                # Reset paused flag if it existed
                if "contact_discovery_paused" in enriched_row:
                    enriched_row["contact_discovery_paused"] = False
                    
                # safe transition automatically updates status
                # But discover_contact sets status = CONTENT_GENERATION inside row.
                nxt = enriched_row.pop("status", "CONTENT_GENERATION")
                enriched_row["status"] = "CONTACT_DISCOVERY"
                
                # Update row directly, safe_transition only updates status.
                self.sheets.update_row(job_id, enriched_row)
                self._safe_transition(enriched_row, nxt, TransitionContext())
                
            except Exception as e:
                # Quota exhausted from HunterProvider raises exception with 429 string or max retries
                if "429" in str(e) or "quota" in str(e).lower():
                    self.logger.record_error(job_id, "agent2", "Quota exhausted, pausing remaining rows")
                    # Pause the current (failed) row
                    self.sheets.update_row(job_id, {"contact_discovery_paused": True})
                    self.logger.increment("rows_paused_quota_exhausted")
                    # Pause all rows that come AFTER the current one (i+1 onward)
                    for remaining_row in rows[i + 1:]:
                        self.sheets.update_row(remaining_row["job_id"], {"contact_discovery_paused": True})
                        self.logger.increment("rows_paused_quota_exhausted")
                    break
                else:
                    self.logger.record_error(job_id, "agent2", f"API failure: {e}")
                    # Do not block the pipeline (Rule 5)
                    existing_notes = row.get("notes", "")
                    row["notes"] = f"{existing_notes}\n[Agent2] API failure: {e}. Proceeding without contact.".strip()
                    row["contact_found"] = False
                    row["status"] = "CONTENT_GENERATION"
                    self.sheets.update_row(job_id, row)
                    self._safe_transition(row, "CONTENT_GENERATION", TransitionContext())
                    self.logger.increment("agent2_contacts_not_found_continued")
                    
        self.logger.increment("agent2_rows_processed", rows_processed)
        self.logger.increment("agent2_contacts_found", contacts_found)
        self.logger.increment("agent2_contacts_not_found_continued", contacts_not_found)
        self.logger.increment("agent2_hunter_api_calls", hunter_api_calls)

    async def _process_content_generation(self) -> None:
        agent = ContentGenerationAgent(self.logger)
        rows = self.sheets.get_rows_by_status("CONTENT_GENERATION")
        
        rows_processed = 0
        cvs_generated = 0
        emails_drafted = 0
        dms_drafted = 0
        rows_failed = 0
        
        for row in rows:
            job_id = row["job_id"]
            try:
                enriched_row = await agent.generate_content(row)
                rows_processed += 1
                
                if "cv_doc_link" in enriched_row:
                    cvs_generated += 1
                if "email_draft_link" in enriched_row:
                    emails_drafted += 1
                if "linkedin_dm_draft" in enriched_row:
                    dms_drafted += 1
                    
                from src.checkpoints.cp2_approval_sync import reset_cp2_fields_for_fresh_review
                if enriched_row.get("cp2_revision_count", 0) > 0:
                    reset_cp2_fields_for_fresh_review(job_id, self.sheets)
                    
                nxt = enriched_row.get("status", "AWAITING_CONTENT_REVIEW")
                
                self.sheets.update_row(job_id, enriched_row)
                self._safe_transition(enriched_row, nxt, TransitionContext())
                
            except FabricationError as e:
                self.logger.record_error(job_id, "agent3", f"Fabrication detected: {e}")
                self.sheets.set_failed(job_id, "agent3", "Fabrication detected - manual review required")
                rows_failed += 1
            except Exception as e:
                self.logger.record_error(job_id, "agent3", f"API failure: {e}")
                self.sheets.set_failed(job_id, "agent3", f"API failure: {e}")
                rows_failed += 1
                
        self.logger.increment("agent3_rows_processed", rows_processed)
        self.logger.increment("agent3_cvs_generated", cvs_generated)
        self.logger.increment("agent3_emails_drafted", emails_drafted)
        self.logger.increment("agent3_dms_drafted", dms_drafted)
        self.logger.increment("agent3_rows_failed", rows_failed)



def build_demo_rows() -> list[dict]:
    return [
        {
            "job_id": "job-001",
            "company": "Example Co",
            "role_title": "Associate Product Manager",
            "status": "AWAITING_HUMAN_REVIEW",
            "human_action": "Apply",
            "notes": "",
        },
        {
            "job_id": "job-002",
            "company": "Startup Labs",
            "role_title": "APM",
            "status": "AWAITING_HUMAN_REVIEW",
            "human_action": "Skip",
            "notes": "",
        },
        {
            "job_id": "job-003",
            "company": "Fintech Inc",
            "role_title": "Associate PM",
            "required_skills": ["SQL", "Roadmapping", "Python"],
            "status": "CONTACT_DISCOVERY",
            "notes": "",
        },
        {
            "job_id": "job-004",
            "company": "NoDomainStartup",
            "role_title": "APM",
            "required_skills": ["Figma", "Marketing"],
            "status": "CONTENT_GENERATION",
            "notes": "",
        },
        {
            "job_id": "job-005",
            "company": "Paused Startup",
            "role_title": "APM",
            "status": "CONTACT_DISCOVERY",
            "contact_discovery_paused": True,
            "notes": "",
        },
        # CP2 Test Cases
        {
            "job_id": "job-cp2-001",
            "company": "Approve Co",
            "role_title": "SWE",
            "status": "AWAITING_CONTENT_REVIEW",
            "cp2_action": "Approve",
            "notes": "",
        },
        {
            "job_id": "job-cp2-002",
            "company": "Edit Co",
            "role_title": "SWE",
            "status": "AWAITING_CONTENT_REVIEW",
            "cp2_action": "Edit",
            "notes": "",
        },
        {
            "job_id": "job-cp2-003",
            "company": "Reject Count 0",
            "role_title": "SWE",
            "status": "AWAITING_CONTENT_REVIEW",
            "cp2_action": "Reject",
            "cp2_revision_count": 0,
            "cp2_rejection_reason": "Tone too formal",
            "notes": "",
        },
        {
            "job_id": "job-cp2-004",
            "company": "Reject Count 2",
            "role_title": "SWE",
            "status": "AWAITING_CONTENT_REVIEW",
            "cp2_action": "Reject",
            "cp2_revision_count": 2,
            "cp2_rejection_reason": "Still not good enough",
            "notes": "",
        },
        {
            "job_id": "job-cp2-005",
            "company": "Skip Co",
            "role_title": "SWE",
            "status": "AWAITING_CONTENT_REVIEW",
            "cp2_action": "Skip",
            "notes": "",
        },
        {
            "job_id": "job-cp2-006",
            "company": "None Co",
            "role_title": "SWE",
            "status": "AWAITING_CONTENT_REVIEW",
            "cp2_action": None,
            "cv_doc_link": "http://example.com/cv",
            "email_draft_link": "draft body",
            "notes": "",
        },
        {
            "job_id": "job-cp2-007",
            "company": "Invalid Co",
            "role_title": "SWE",
            "status": "AWAITING_CONTENT_REVIEW",
            "cp2_action": "InvalidValue",
            "notes": "",
        },
        # ── Phase 7 / ATS Test Cases ─────────────────────────────────────────
        {
            "job_id": "ats-pass",
            "company": "TechCorp",
            "role_title": "Associate Product Manager",
            "status": "ATS_REVIEW",
            "cv_doc_link": "/tmp/cv_outputs/test_pass.docx",
            "required_skills": '["product strategy", "user research", "SQL", "stakeholder management"]',
            "cp2_approved": True,
            "cp2_decided_at": "2025-05-05T10:00:00",
            "email_draft_link": "Subject: Joining TechCorp\n\nHi!",
            "revision_count": 0,
            "notes": "",
        },
        {
            "job_id": "ats-fail-first",
            "company": "StartupXYZ",
            "role_title": "APM",
            "status": "ATS_REVIEW",
            "cv_doc_link": "/tmp/cv_outputs/test_fail_no_metrics.docx",
            "required_skills": '["roadmapping", "agile", "data analysis"]',
            "cp2_approved": True,
            "cp2_decided_at": "2025-05-05T10:00:00",
            "email_draft_link": "Subject: Joining StartupXYZ\n\nHi!",
            "revision_count": 0,
            "notes": "",
        },
        {
            "job_id": "ats-fail-capped",
            "company": "CorpD",
            "role_title": "APM",
            "status": "ATS_REVIEW",
            "cv_doc_link": "/tmp/cv_outputs/test_fail_chronic.docx",
            "required_skills": '["python", "SQL"]',
            "cp2_approved": True,
            "cp2_decided_at": "2025-05-05T10:00:00",
            "email_draft_link": "Subject: Joining CorpD\n\nHi!",
            "revision_count": 2,
            "notes": "",
        },
        {
            "job_id": "ats-bypass",
            "company": "BypassCo",
            "role_title": "APM",
            "status": "ATS_REVIEW",
            "cv_doc_link": "/tmp/cv_outputs/test.docx",
            "required_skills": '["product"]',
            "cp2_approved": False,
            "cp2_decided_at": None,
            "revision_count": 0,
            "notes": "",
        },
        # ── Phase 8 / Execution Test Cases ─────────────────────────────
        {
            # Test 1: Apply — should submit application (DRY_RUN mode)
            "job_id": "exec-apply",
            "company": "AppCo",
            "role_title": "APM",
            "status": "APPROVED_FOR_EXECUTION",
            "human_action": "Apply",
            "job_url": "https://appco.com/jobs/apm",
            "cv_doc_link": "/tmp/cv_outputs/test_pass.docx",
            "email_draft_link": "Subject: Hi\n\nBody",
            "contact_email": "hr@appco.com",
            "cp2_approved": True,
            "cp2_decided_at": "2026-05-05T10:00:00",
            "notes": "",
        },
        {
            # Test 2: Outreach Only — email + LinkedIn DM (DRY_RUN mode)
            "job_id": "exec-outreach",
            "company": "OutreachCo",
            "role_title": "APM",
            "status": "APPROVED_FOR_EXECUTION",
            "human_action": "Outreach Only",
            "cv_doc_link": "/tmp/cv_outputs/test_pass.docx",
            "email_draft_link": "Subject: Joining OutreachCo\n\nHi!",
            "contact_email": "recruiter@outreachco.com",
            "contact_linkedin": "https://linkedin.com/in/recruiter",
            "linkedin_dm_draft": "Hi! Saw you're hiring an APM. Would love to connect.",
            "cp2_approved": True,
            "cp2_decided_at": "2026-05-05T10:00:00",
            "notes": "",
        },
        {
            # Test 3: Safety gate bypass — cp2_approved=False
            "job_id": "exec-bypass",
            "company": "BypassExecCo",
            "role_title": "APM",
            "status": "APPROVED_FOR_EXECUTION",
            "human_action": "Apply",
            "job_url": "https://bypass.com/jobs/apm",
            "cv_doc_link": "/tmp/cv_outputs/test_pass.docx",
            "cp2_approved": False,  # Bypass attempt
            "cp2_decided_at": None,
            "notes": "",
        },
        {
            # Test 4: No contact — should route to MANUAL_QUEUE
            "job_id": "exec-no-contact",
            "company": "NoCo",
            "role_title": "APM",
            "status": "APPROVED_FOR_EXECUTION",
            "human_action": "Outreach Only",
            "cv_doc_link": "/tmp/cv_outputs/test_pass.docx",
            "email_draft_link": "Subject: Hi\n\nBody",
            "contact_email": "",
            "contact_linkedin": "",
            "cp2_approved": True,
            "cp2_decided_at": "2026-05-05T10:00:00",
            "notes": "",
        },
        {
            # Test 5: Already applied (idempotency)
            "job_id": "exec-already-applied",
            "company": "DoneCo",
            "role_title": "APM",
            "status": "APPROVED_FOR_EXECUTION",
            "human_action": "Apply",
            "job_url": "https://doneco.com/jobs/apm",
            "cv_doc_link": "/tmp/cv_outputs/test_pass.docx",
            "email_draft_link": "Subject: Hi\n\nBody",
            "contact_email": "hr@doneco.com",
            "applied_at": "2026-05-05T09:00:00+00:00",  # Already applied
            "cp2_approved": True,
            "cp2_decided_at": "2026-05-05T10:00:00",
            "notes": "",
        },
        # ── Phase 9 / Monitoring Test Cases ───────────────────────────
        {
            # Test 6: Existing APPLIED row — should move to MONITORING
            "job_id": "mon-applied",
            "company": "MonitorCo",
            "role_title": "APM",
            "status": "APPLIED",
            "contact_email": "hr@monitorco.com",
            "applied_at": "2026-05-01T10:00:00Z",
            "notes": "",
        },
        {
            # Test 7: OUTREACH_SENT row — simulated reply found
            "job_id": "mon-reply",
            "company": "ReplyCo", # Monitor matcher will check company 'outreachco' in simulated reply
            "role_title": "APM",
            "status": "OUTREACH_SENT",
            "contact_email": "recruiter@outreachco.com",
            "outreach_sent_at": "2026-05-04T10:00:00Z",
            "notes": "Initial notes.",
        },
    ]



async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true", help="Run in continuous scheduling mode")
    parser.add_argument("--once", action="store_true", help="Run once immediately (default)")
    args = parser.parse_args()

    lock_path = Path("logs/.orchestrator.lock")
    
    if args.daemon:
        print("Starting orchestrator in DAEMON mode (9 AM IST trigger)...")
        last_run_date = None
        while True:
            now = datetime.now(timezone.utc)
            if Orchestrator.should_run_now(now):
                current_date = now.astimezone(IST).date()
                if last_run_date != current_date:
                    print(f"Trigger hit at {now}. Running pipeline...")
                    with run_lock(lock_path):
                        use_demo = os.environ.get("USE_DEMO_DATA", "false").lower() == "true"
                        initial_rows = build_demo_rows() if use_demo else []
                        sheets = SheetsGateway.from_seed_rows(initial_rows)
                        logger = RunLogger()
                        orchestrator = Orchestrator(sheets=sheets, logger=logger)
                        await orchestrator.run_once()
                        log_path = logger.close()
                        print(f"Daily run complete. Log: {log_path}")
                    last_run_date = current_date
            
            # Check every minute
            await asyncio.sleep(60)
    else:
        # Run once mode
        with run_lock(lock_path):
            use_demo = os.environ.get("USE_DEMO_DATA", "false").lower() == "true"
            initial_rows = build_demo_rows() if use_demo else []
            sheets = SheetsGateway.from_seed_rows(initial_rows)
            logger = RunLogger()
            orchestrator = Orchestrator(sheets=sheets, logger=logger)
            await orchestrator.run_once()
            log_path = logger.close()
            print(f"Phase 10 run completed. Log written to: {log_path}")


if __name__ == "__main__":
    asyncio.run(main())

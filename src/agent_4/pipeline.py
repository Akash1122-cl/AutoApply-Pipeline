"""
Agent 4 — Execution Pipeline (Phase 8)

The final execution layer. For each APPROVED_FOR_EXECUTION row:
  1. Run CP2Validator.validate_can_proceed_to_phase_8() — absolute safety gate
  2. Determine channel action via ChannelPolicyEngine
  3. Execute: submit application / send email / send LinkedIn DM / route to manual
  4. Persist timestamps and transition to terminal state

Non-negotiables:
  - Safety gate on EVERY row (no exceptions)
  - Idempotency guard in every channel module
  - On any failure: FAILED state, notes updated, continue for other rows
  - LinkedIn automation failures → MANUAL_QUEUE (not FAILED)
  - Never exceed daily caps
"""

from datetime import datetime, timezone
from src.shared.run_logger import RunLogger
from src.checkpoints.cp2_validators import CP2Validator
from src.agent_4.channel_policy import ChannelPolicyEngine, ChannelUsage, ACTION_APPLY, ACTION_EMAIL, ACTION_LINKEDIN_DM, ACTION_MANUAL_QUEUE, ACTION_SKIP
from src.agent_4.email_sender import EmailSender
from src.agent_4.linkedin_outreach import LinkedInOutreach
from src.agent_4.application_submitter import ApplicationSubmitter


class ExecutionAgent:
    """
    Phase 8 Agent 4.
    Processes all APPROVED_FOR_EXECUTION rows and dispatches execution actions.
    """

    def __init__(self, logger: RunLogger):
        self.logger = logger
        self.usage = ChannelUsage()
        self.email_sender = EmailSender()
        self.linkedin = LinkedInOutreach()
        self.submitter = ApplicationSubmitter()

    async def execute_row(self, row: dict) -> dict:
        """
        Executes a single approved row. Returns result dict with fields:
          - final_status: "APPLIED" | "OUTREACH_SENT" | "MANUAL_QUEUE" | "FAILED" | "SKIPPED"
          - applied_at / outreach_sent_at (if executed)
          - notes_append: additional text to append to row notes
          - error: error message if failed
        """
        job_id = row.get("job_id", "unknown")

        # ── Step 1: Absolute safety gate ─────────────────────────────────────
        validator = CP2Validator()
        is_valid, issues = validator.validate_can_proceed_to_phase_8(row)
        if not is_valid:
            # Distinguish: missing contact is a routing issue → MANUAL_QUEUE
            # Real approval/fabrication violations → FAILED
            is_contact_only = all("contact" in i for i in issues)
            final_status = "MANUAL_QUEUE" if is_contact_only else "FAILED"
            return {
                "final_status": final_status,
                "error": f"Phase 8 safety gate failed: {'; '.join(issues)}",
                "notes_append": f"[SAFETY] Phase 8 blocked ({final_status}): {'; '.join(issues)}",
            }

        # ── Step 2: Channel policy decision ──────────────────────────────────
        policy = ChannelPolicyEngine(self.usage)
        decision = policy.decide(row)

        if self.logger:
            self.logger.record_error(
                job_id, "agent4", f"Channel decision: {decision.action} — {decision.reason}"
            )

        # ── Step 3: SKIP ──────────────────────────────────────────────────────
        if decision.action == ACTION_SKIP:
            return {
                "final_status": "SKIPPED",
                "error": None,
                "notes_append": f"[Execution] Skipped: {decision.reason}",
            }

        # ── Step 4: MANUAL QUEUE ─────────────────────────────────────────────
        if decision.route_to_manual:
            self.usage.manual_queued += 1
            return {
                "final_status": "MANUAL_QUEUE",
                "error": None,
                "notes_append": f"[Execution] Manual queue: {decision.reason}",
            }

        # ── Step 5: Execute actions ───────────────────────────────────────────
        applied_at = None
        outreach_sent_at = None
        notes_parts = []
        any_success = False

        # Application submission
        if decision.submit_application:
            result = await self.submitter.submit(row)
            if result["success"]:
                applied_at = result["applied_at"]
                self.usage.applications_submitted += 1
                any_success = True
                notes_parts.append(f"[Applied] at {applied_at}")
            else:
                return {
                    "final_status": "FAILED",
                    "error": result["error"],
                    "notes_append": f"[Application FAILED] {result['error']}",
                }

        # Email send
        if decision.send_email:
            result = await self.email_sender.send(row)
            if result["success"] and not result.get("skipped"):
                outreach_sent_at = result["sent_at"]
                self.usage.emails_sent += 1
                any_success = True
                notes_parts.append(f"[Email sent] to {row.get('contact_email')} at {outreach_sent_at}")
            elif not result["success"]:
                # Email failure is non-fatal if we also submitted an application
                notes_parts.append(f"[Email FAILED] {result['error']}")
                if not applied_at:
                    return {
                        "final_status": "FAILED",
                        "error": result["error"],
                        "notes_append": "\n".join(notes_parts),
                    }

        # LinkedIn DM send
        if decision.send_linkedin_dm:
            result = await self.linkedin.send_dm(row)
            if result["success"] and not result.get("skipped"):
                outreach_sent_at = outreach_sent_at or result["sent_at"]
                self.usage.linkedin_dms_sent += 1
                any_success = True
                notes_parts.append(f"[LinkedIn DM sent] at {result['sent_at']}")
            elif not result["success"]:
                if result.get("route_to_manual"):
                    # LinkedIn risk → manual queue (not FAILED)
                    self.usage.manual_queued += 1
                    notes_parts.append(f"[LinkedIn pivoted to manual] {result['error']}")
                    if not applied_at and not outreach_sent_at:
                        return {
                            "final_status": "MANUAL_QUEUE",
                            "error": None,
                            "notes_append": "\n".join(notes_parts),
                        }
                else:
                    notes_parts.append(f"[LinkedIn FAILED] {result['error']}")

        # ── Step 6: Determine final status ───────────────────────────────────
        if applied_at:
            final_status = "APPLIED"
        elif outreach_sent_at:
            final_status = "OUTREACH_SENT"
        elif any_success:
            final_status = "OUTREACH_SENT"
        else:
            final_status = "FAILED"

        return {
            "final_status": final_status,
            "applied_at": applied_at,
            "outreach_sent_at": outreach_sent_at,
            "error": None,
            "notes_append": "\n".join(notes_parts) if notes_parts else f"[Execution] {decision.reason}",
        }

from typing import Callable
from datetime import datetime, timezone

from src.orchestrator.state_engine import TransitionContext
from src.shared.run_logger import RunLogger
from src.shared.sheets_gateway import SheetsGateway

class CP2ApprovalSync:
    def __init__(self, sheets: SheetsGateway, logger: RunLogger, safe_transition_fn: Callable):
        self.sheets = sheets
        self.logger = logger
        self.safe_transition_fn = safe_transition_fn

    async def check_and_process(self):
        """
        Polls the 'cp2_action' field for rows in 'AWAITING_CONTENT_REVIEW'.
        Routes decisions to the correct next state and blocks downstream rows
        until action is set.
        """
        for row in self.sheets.get_rows_by_status("AWAITING_CONTENT_REVIEW"):
            job_id = row["job_id"]
            action = row.get("cp2_action")
            
            # Block downstream rows until action is set
            if not action or action not in {"Approve", "Edit", "Reject", "Skip"}:
                if action:
                    self.logger.record_error(job_id, "cp2_sync", f"Invalid cp2_action '{action}'. Ignoring.")
                continue

            if action in {"Approve", "Edit"}:
                # Need to update row directly for persistent flags
                now_iso = datetime.now(tz=timezone.utc).isoformat()
                updates = {
                    "cp2_approved": True,
                    "cp2_decided_at": now_iso
                }
                self.sheets.update_row(job_id, updates)
                
                # We merge back to the row object so safe_transition context is correct
                row["cp2_approved"] = True
                row["cp2_decided_at"] = now_iso
                
                self.safe_transition_fn(
                    row,
                    "ATS_REVIEW",
                    TransitionContext(cp2_approved=True)
                )
                
            elif action == "Reject":
                revision_count = int(row.get("cp2_revision_count", 0))
                
                if revision_count < 2:
                    new_count = revision_count + 1
                    rejection_reason = row.get("cp2_rejection_reason", "No reason provided")
                    existing_notes = row.get("notes", "")
                    feedback_marker = f"[CP2 Rejection Feedback - Attempt {new_count}]: {rejection_reason}"
                    new_notes = f"{existing_notes}\n{feedback_marker}".strip()
                    
                    self.sheets.update_row(job_id, {
                        "cp2_revision_count": new_count,
                        "notes": new_notes
                    })
                    
                    # Update row object for safe_transition
                    row["cp2_revision_count"] = new_count
                    row["notes"] = new_notes
                    
                    self.safe_transition_fn(
                        row,
                        "CONTENT_GENERATION",
                        TransitionContext()
                    )
                else:
                    self.safe_transition_fn(
                        row,
                        "HUMAN_REVIEW",
                        TransitionContext(ats_pass=False, revision_count=revision_count) # Using existing context rules
                    )
                    
            elif action == "Skip":
                self.safe_transition_fn(
                    row,
                    "SKIPPED",
                    TransitionContext()
                )
                
            self.logger.increment("cp2_gate")
            self.logger.record_error(job_id, "cp2_gate", f"Processed cp2_action={action}")

def reset_cp2_fields_for_fresh_review(row_id: str, tracker_gateway: SheetsGateway):
    """
    Called when Agent 3 regenerates content after a Reject.
    Clears CP2 decision fields but preserves history.
    """
    tracker_gateway.update_row(row_id, {
        "cp2_action": None,                    # Clear (needs new decision)
        "cp2_approved": False,                 # Reset flag
        "cp2_decided_at": None,                # Clear timestamp
        "cp2_edits_summary": None,             # Clear edit summary
    })

"""
Recovery Service — Phase 10.1

Provides safe recovery mechanisms for FAILED rows while preserving
idempotency and auditability.
"""

from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from src.shared.sheets_gateway import SheetsGateway
from src.shared.run_logger import RunLogger


class RecoveryAction(Enum):
    RETRY_SAME_CHECKPOINT = "retry_same_checkpoint"
    RESET_TO_CP1 = "reset_to_cp1"
    RESET_TO_CP2 = "reset_to_cp2"
    RESET_TO_CONTACT_DISCOVERY = "reset_to_contact_discovery"
    RESET_TO_CONTENT_GENERATION = "reset_to_content_generation"
    MANUAL_REVIEW = "manual_review"


@dataclass
class RecoveryMetadata:
    recovered_by: str
    recovered_at: datetime
    recovery_reason: str
    original_status: str
    original_error: str
    recovery_action: RecoveryAction


class RecoveryService:
    def __init__(self, sheets: SheetsGateway, logger: RunLogger):
        self.sheets = sheets
        self.logger = logger
        self.valid_reset_statuses = {
            RecoveryAction.RETRY_SAME_CHECKPOINT: ["FAILED"],
            RecoveryAction.RESET_TO_CP1: ["FAILED", "HUMAN_REVIEW"],
            RecoveryAction.RESET_TO_CP2: ["FAILED", "HUMAN_REVIEW"],
            RecoveryAction.RESET_TO_CONTACT_DISCOVERY: ["FAILED"],
            RecoveryAction.RESET_TO_CONTENT_GENERATION: ["FAILED"],
            RecoveryAction.MANUAL_REVIEW: ["FAILED", "HUMAN_REVIEW"]
        }
    
    def get_failed_rows(self) -> List[Dict[str, Any]]:
        """Get all rows with FAILED status."""
        return self.sheets.get_rows_by_status("FAILED")
    
    def inspect_row_error(self, row_id: str) -> Dict[str, Any]:
        """Inspect the error details for a specific failed row."""
        try:
            row = self.sheets.get_row(row_id)
        except KeyError:
            row = None
        if not row:
            return {"error": "Row not found"}
        
        return {
            "row_id": row_id,
            "current_status": row.get("status"),
            "error_notes": row.get("notes", ""),
            "last_updated": row.get("updated_at"),
            "company": row.get("company"),
            "role_title": row.get("role_title"),
            "job_url": row.get("job_url"),
            "human_action": row.get("human_action"),
            "cp2_approval": row.get("cp2_approval"),
            "ats_score": row.get("ats_score"),
            "revision_count": row.get("revision_count", 0)
        }
    
    def get_safe_recovery_actions(self, row_id: str) -> List[RecoveryAction]:
        """Determine safe recovery actions for a failed row."""
        try:
            row = self.sheets.get_row(row_id)
        except KeyError:
            row = None
        if not row:
            return []
        
        current_status = row.get("status", "")
        error_notes = row.get("notes", "").lower()
        human_action = row.get("human_action", "")
        cp2_approval = row.get("cp2_approval", "")
        revision_count = row.get("revision_count", 0)
        
        safe_actions = []
        
        # Always allow manual review
        safe_actions.append(RecoveryAction.MANUAL_REVIEW)
        
        # Analyze error type and determine appropriate resets
        if "timeout" in error_notes or "network" in error_notes:
            # Network/timeouts can be retried from same checkpoint
            safe_actions.append(RecoveryAction.RETRY_SAME_CHECKPOINT)
        
        if "api" in error_notes or "rate_limit" in error_notes:
            # API issues can be retried from same checkpoint
            safe_actions.append(RecoveryAction.RETRY_SAME_CHECKPOINT)
        
        # If human action is missing, reset to CP1
        if not human_action:
            safe_actions.append(RecoveryAction.RESET_TO_CP1)
        
        # If CP2 approval is missing, reset to CP2 (but only if human action exists)
        if human_action and not cp2_approval:
            safe_actions.append(RecoveryAction.RESET_TO_CP2)
        
        # If contact discovery failed, reset to contact discovery
        if "contact" in error_notes or "enrichment" in error_notes:
            safe_actions.append(RecoveryAction.RESET_TO_CONTACT_DISCOVERY)
        
        # If content generation failed, reset to content generation
        if "content" in error_notes or "cv" in error_notes or "email" in error_notes:
            safe_actions.append(RecoveryAction.RESET_TO_CONTENT_GENERATION)
        
        # Prevent excessive ATS revision loops
        if "ats" in error_notes and revision_count >= 2:
            # Force manual review for ATS failures after 2 revisions
            safe_actions = [RecoveryAction.MANUAL_REVIEW]
        
        return safe_actions
    
    def verify_external_outcome(self, row_id: str) -> Dict[str, Any]:
        """Check for uncertain external outcomes before retry."""
        try:
            row = self.sheets.get_row(row_id)
        except KeyError:
            row = None
        if not row:
            return {"error": "Row not found"}
        
        verification = {
            "email_sent": self._check_email_sent(row),
            "application_submitted": self._check_application_submitted(row),
            "linkedin_dm_sent": self._check_linkedin_sent(row),
            "recommendation": "safe_to_retry"
        }
        
        # If any external action appears successful, recommend manual review
        external_actions = [
            verification["email_sent"],
            verification["application_submitted"], 
            verification["linkedin_dm_sent"]
        ]
        if any(external_actions):
            verification["recommendation"] = "manual_review_required"
        
        return verification
    
    def recover_row(self, row_id: str, action: RecoveryAction, 
                   recovered_by: str, recovery_reason: str) -> Dict[str, Any]:
        """Safely recover a failed row with proper audit trail."""
        
        # Validate row exists and is in recoverable state
        try:
            row = self.sheets.get_row(row_id)
        except KeyError:
            row = None
        if not row:
            return {"success": False, "error": "Row not found"}
        
        current_status = row.get("status", "")
        if current_status not in self.valid_reset_statuses.get(action, []):
            return {"success": False, "error": f"Cannot apply {action.value} to status {current_status}"}
        
        # Check for external outcomes before retry
        if action != RecoveryAction.MANUAL_REVIEW:
            verification = self.verify_external_outcome(row_id)
            if verification["recommendation"] == "manual_review_required":
                return {
                    "success": False, 
                    "error": "External action detected, manual review required",
                    "verification": verification
                }
        
        # Determine new status based on action
        # All statuses must be valid states in ALLOWED_TRANSITIONS
        status_mapping = {
            RecoveryAction.RETRY_SAME_CHECKPOINT: self._determine_retry_checkpoint(row),
            RecoveryAction.RESET_TO_CP1: "AWAITING_HUMAN_REVIEW",
            RecoveryAction.RESET_TO_CP2: "AWAITING_CONTENT_REVIEW",
            RecoveryAction.RESET_TO_CONTACT_DISCOVERY: "CONTACT_DISCOVERY",
            RecoveryAction.RESET_TO_CONTENT_GENERATION: "CONTENT_GENERATION",
            RecoveryAction.MANUAL_REVIEW: "HUMAN_REVIEW"
        }
        
        new_status = status_mapping.get(action)
        if not new_status:
            return {"success": False, "error": f"Unknown recovery action: {action.value}"}
        
        # Create recovery metadata
        recovery_metadata = RecoveryMetadata(
            recovered_by=recovered_by,
            recovered_at=datetime.now(),
            recovery_reason=recovery_reason,
            original_status=current_status,
            original_error=row.get("notes", ""),
            recovery_action=action
        )
        
        # Prepare update data (use UTC for timestamp consistency)
        update_data = {
            "status": new_status,
            "notes": f"Recovered: {recovery_reason} (by {recovered_by} at {recovery_metadata.recovered_at.strftime('%Y-%m-%d %H:%M:%S')} UTC)",
            "recovery_metadata": self._serialize_recovery_metadata(recovery_metadata),
        }
        
        # Reset specific fields based on action
        if action == RecoveryAction.RESET_TO_CP1:
            update_data.update({
                "human_action": "",
                "cp2_approval": "",
                "contact_email": "",
                "contact_name": "",
                "cv_link": "",
                "email_draft": "",
                "linkedin_draft": ""
            })
        elif action == RecoveryAction.RESET_TO_CP2:
            update_data.update({
                "cp2_approval": "",
                "cv_link": "",
                "email_draft": "",
                "linkedin_draft": ""
            })
        elif action == RecoveryAction.RESET_TO_CONTACT_DISCOVERY:
            update_data.update({
                "contact_email": "",
                "contact_name": "",
                "contact_title": ""
            })
        elif action == RecoveryAction.RESET_TO_CONTENT_GENERATION:
            update_data.update({
                "cv_link": "",
                "email_draft": "",
                "linkedin_draft": ""
            })
        
        # Apply the recovery — update_row() returns the updated row dict (not a bool)
        try:
            self.sheets.update_row(row_id, update_data)
            # Log the recovery event using available logger methods
            self.logger.increment("rows_recovered")
            self.logger.record_error(
                row_id,
                "recovery_service",
                f"Recovered: {action.value} | {current_status} → {new_status} | reason: {recovery_reason} | by: {recovered_by}"
            )
            return {
                "success": True,
                "row_id": row_id,
                "action": action.value,
                "old_status": current_status,
                "new_status": new_status,
                "recovered_by": recovered_by,
                "recovered_at": recovery_metadata.recovered_at.isoformat()
            }
        except Exception as e:
            return {"success": False, "error": f"Recovery failed: {str(e)}"}
    
    def get_recovery_queue_report(self) -> Dict[str, Any]:
        """Generate recovery queue reporting for daily summary."""
        failed_rows = self.get_failed_rows()
        human_review_rows = self.sheets.get_rows_by_status("HUMAN_REVIEW")
        
        # Analyze failure patterns
        failure_patterns = {}
        for row in failed_rows:
            error_notes = row.get("notes", "").lower()
            if "timeout" in error_notes:
                failure_patterns["timeout"] = failure_patterns.get("timeout", 0) + 1
            elif "api" in error_notes:
                failure_patterns["api"] = failure_patterns.get("api", 0) + 1
            elif "contact" in error_notes:
                failure_patterns["contact"] = failure_patterns.get("contact", 0) + 1
            elif "content" in error_notes:
                failure_patterns["content"] = failure_patterns.get("content", 0) + 1
            elif "ats" in error_notes:
                failure_patterns["ats"] = failure_patterns.get("ats", 0) + 1
            else:
                failure_patterns["other"] = failure_patterns.get("other", 0) + 1
        
        return {
            "failed_rows_count": len(failed_rows),
            "human_review_count": len(human_review_rows),
            "failure_patterns": failure_patterns,
            "recent_recoveries": self._get_recent_recoveries(),
            "recommended_actions": self._get_recommended_actions(failed_rows)
        }
    
    def _determine_retry_checkpoint(self, row: Dict[str, Any]) -> str:
        """Determine the appropriate checkpoint for retry based on row state.
        
        All returned statuses must be valid states in the state machine's
        ALLOWED_TRANSITIONS table.
        """
        if not row.get("human_action"):
            return "AWAITING_HUMAN_REVIEW"
        elif not row.get("cp2_approved"):  # correct field name is cp2_approved
            return "AWAITING_CONTENT_REVIEW"
        elif not row.get("contact_email") and row.get("human_action") in ["Apply", "Outreach Only"]:
            return "CONTACT_DISCOVERY"
        elif not row.get("cv_doc_link"):  # correct field name is cv_doc_link
            return "CONTENT_GENERATION"
        else:
            return "APPROVED_FOR_EXECUTION"
    
    def _check_email_sent(self, row: Dict[str, Any]) -> bool:
        """Check if email was actually sent (stub implementation)."""
        # In real implementation, this would check email logs/Gmail API
        notes = row.get("notes", "").lower()
        return "email sent" in notes or "delivered" in notes
    
    def _check_application_submitted(self, row: Dict[str, Any]) -> bool:
        """Check if application was actually submitted (stub implementation)."""
        # In real implementation, this would check application logs
        notes = row.get("notes", "").lower()
        return "application submitted" in notes or "applied" in notes
    
    def _check_linkedin_sent(self, row: Dict[str, Any]) -> bool:
        """Check if LinkedIn DM was actually sent (stub implementation)."""
        # In real implementation, this would check LinkedIn logs
        notes = row.get("notes", "").lower()
        return "linkedin sent" in notes or "dm sent" in notes
    
    def _serialize_recovery_metadata(self, metadata: RecoveryMetadata) -> str:
        """Serialize recovery metadata for storage."""
        return f"{metadata.recovered_by}|{metadata.recovered_at.isoformat()}|{metadata.recovery_reason}|{metadata.original_status}|{metadata.original_error}|{metadata.recovery_action.value}"
    
    def _get_recent_recoveries(self) -> List[Dict[str, Any]]:
        """Get recent recovery actions from logs."""
        # In real implementation, this would query the run logs
        return []
    
    def _get_recommended_actions(self, failed_rows: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze failed rows and recommend recovery actions."""
        recommendations = {}
        for row in failed_rows:
            safe_actions = self.get_safe_recovery_actions(row["job_id"])  # correct key is job_id
            for action in safe_actions:
                recommendations[action.value] = recommendations.get(action.value, 0) + 1
        return recommendations

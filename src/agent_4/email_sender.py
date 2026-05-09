"""
Email Sender — Phase 8

Logs cold email drafts for manual review. No automatic sending.
All emails are saved to logs/emails/ for manual sending by the user.

Rules:
  - Never send automatically - manual only
  - Idempotency: skip if outreach_sent_at already set
"""

import json
from datetime import datetime, timezone
from pathlib import Path


class EmailSender:
    """Logs cold email drafts for manual sending. No automatic Gmail integration."""

    async def send(self, row: dict) -> dict:
        """
        Logs the email draft for manual review. No automatic sending.
        Returns a result dict: {"success": bool, "error": str|None, "sent_at": str|None}
        """
        job_id = row.get("job_id", "unknown")

        # Idempotency guard
        if row.get("outreach_sent_at"):
            return {
                "success": True,
                "error": None,
                "sent_at": row["outreach_sent_at"],
                "skipped": True,
                "reason": "Already sent (idempotency guard)",
            }

        draft = row.get("email_draft_link", "").strip()
        if not draft:
            return {"success": False, "error": "email_draft_link is empty", "sent_at": None}

        recipient = row.get("contact_email", "")
        if not recipient:
            return {"success": False, "error": "contact_email missing", "sent_at": None}

        logged_at = datetime.now(tz=timezone.utc).isoformat()

        # Log for manual review - no automatic sending
        self._log_draft(job_id, recipient, draft, logged_at)
        return {
            "success": True,
            "error": None,
            "sent_at": logged_at,
            "manual": True,
            "message": "Email logged for manual sending. Review in logs/emails/"
        }

    def _log_draft(self, job_id: str, recipient: str, draft: str, logged_at: str) -> None:
        log_dir = Path("logs/emails")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{job_id}_email_draft.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "job_id": job_id,
                    "recipient": recipient,
                    "draft": draft,
                    "logged_at": logged_at,
                    "mode": "MANUAL_REVIEW_REQUIRED",
                    "instructions": "Send this email manually via Gmail. Do not use automatic sending."
                },
                f,
                indent=2,
            )

"""
LinkedIn Outreach Module — Phase 8

Logs LinkedIn DMs for manual review. No automatic sending.
All DMs are saved to logs/linkedin_dms/ for manual sending by the user.

LinkedIn Safety Rules (from Architecture.md):
  - If automation blocked/risky/failing → pivot row to MANUAL_QUEUE
  - Never force automation when account risk signals appear
  - DMs blocked for non-1st-degree connections → route to manual
  - Cap: 20 DMs/day
"""

import json
from datetime import datetime, timezone
from pathlib import Path

LINKEDIN_RISK_SIGNALS = [
    "Security checkpoint",
    "Account Restricted",
    "Page contains CAPTCHA",
    "Verification required",
    "Automation detected",
]


class LinkedInOutreach:
    """Logs LinkedIn DMs for manual sending. No automatic Playwright integration."""

    async def send_dm(self, row: dict) -> dict:
        """
        Logs the LinkedIn DM for manual review. No automatic sending.
        Returns: {"success": bool, "error": str|None, "sent_at": str|None}
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

        dm_draft = row.get("linkedin_dm_draft", "").strip()
        if not dm_draft:
            return {
                "success": False,
                "error": "linkedin_dm_draft is empty",
                "sent_at": None,
            }

        contact_linkedin = row.get("contact_linkedin", "")
        if not contact_linkedin:
            return {
                "success": False,
                "error": "contact_linkedin missing — cannot send DM",
                "sent_at": None,
            }

        logged_at = datetime.now(tz=timezone.utc).isoformat()

        # Log for manual review - no automatic sending
        self._log_dm(job_id, contact_linkedin, dm_draft, logged_at)
        return {
            "success": True,
            "error": None,
            "sent_at": logged_at,
            "manual": True,
            "message": "LinkedIn DM logged for manual sending. Review in logs/linkedin_dms/"
        }

    def _log_dm(self, job_id: str, profile_url: str, dm: str, logged_at: str) -> None:
        log_dir = Path("logs/linkedin_dms")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{job_id}_linkedin_dm.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "job_id": job_id,
                    "linkedin_profile": profile_url,
                    "dm": dm,
                    "logged_at": logged_at,
                    "mode": "MANUAL_SENDING_REQUIRED",
                    "instructions": "Send this LinkedIn DM manually via LinkedIn. Do not use automatic sending."
                },
                f,
                indent=2,
            )

"""
Application Submitter — Phase 8

Logs job application details for manual submission. No automatic form automation.
All applications are saved to logs/applications/ for manual submission by the user.

Rules (from Context.md):
  - NEVER submit to the same job_url twice — check applied_at before acting
  - On submission failure: status = FAILED, log error, do not retry automatically
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path


class ApplicationSubmitter:
    """Logs job application details for manual submission. No automatic Playwright integration."""

    async def submit(self, row: dict) -> dict:
        """
        Logs the application details for manual review. No automatic submission.
        Returns: {"success": bool, "error": str|None, "applied_at": str|None}
        """
        job_id = row.get("job_id", "unknown")

        # Idempotency guard — never submit twice
        if row.get("applied_at"):
            return {
                "success": True,
                "error": None,
                "applied_at": row["applied_at"],
                "skipped": True,
                "reason": "Already applied (idempotency guard)",
            }

        job_url = row.get("job_url", "").strip()
        if not job_url:
            return {"success": False, "error": "job_url missing", "applied_at": None}

        cv_doc_link = row.get("cv_doc_link", "").strip()
        if not cv_doc_link:
            return {
                "success": False,
                "error": "cv_doc_link missing — cannot submit without CV",
                "applied_at": None,
            }

        logged_at = datetime.now(tz=timezone.utc).isoformat()

        # Log for manual review - no automatic submission
        self._log_application(job_id, job_url, cv_doc_link, logged_at)
        return {
            "success": True,
            "error": None,
            "applied_at": logged_at,
            "manual": True,
            "message": "Application logged for manual submission. Review in logs/applications/"
        }

    def _log_application(
        self, job_id: str, job_url: str, cv_link: str, logged_at: str
    ) -> None:
        log_dir = Path("logs/applications")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{job_id}_application_details.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "job_id": job_id,
                    "job_url": job_url,
                    "cv_doc_link": cv_link,
                    "logged_at": logged_at,
                    "mode": "MANUAL_SUBMISSION_REQUIRED",
                    "instructions": "Submit this application manually via the job portal URL. Do not use automatic submission."
                },
                f,
                indent=2,
            )

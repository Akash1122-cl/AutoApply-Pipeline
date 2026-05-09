"""
Response Monitor — Phase 9

Polls the inbox for recruiter responses and updates the tracker.
In DRY_RUN mode, uses simulated responses.

PRODUCTION STATUS: NOT IMPLEMENTED
  The Gmail API / MCP integration that fetches real inbound emails is
  NOT yet built. The production path in _fetch_inbound_emails() returns
  an empty list, which means Phase 9 is a no-op outside dry-run.

  Action required before going live:
  1. Implement Gmail OAuth token refresh and keep DRY_RUN=true until done.
  2. Use the Gmail API (or MCP gmail tool) to fetch unread threads.
  3. Parse sender/subject from each thread and feed into ReplyMatcher.

  Until this is done, always run with DRY_RUN=true in your .env file.
"""

import os
from datetime import datetime, timezone
from typing import List, Dict, Any
from src.shared.run_logger import RunLogger
from src.agent_9.reply_matcher import ReplyMatcher

DRY_RUN: bool = os.getenv("DRY_RUN", "true").lower() == "true"


class ResponseMonitor:
    def __init__(self, logger: RunLogger):
        self.logger = logger
        self.matcher = ReplyMatcher()

    async def poll_and_process(self, rows_to_monitor: List[dict]) -> List[Dict[str, Any]]:
        """
        Polls for replies and matches them to rows.
        Returns a list of updates for the tracker.
        """
        if not rows_to_monitor:
            return []

        # 1. Fetch inbound emails (stubbed)
        inbound_emails = await self._fetch_inbound_emails()
        
        updates = []

        for email in inbound_emails:
            sender = email["sender"]
            subject = email["subject"]
            body = email["body"]
            
            # Skip auto-replies to keep metrics clean
            if self.matcher.is_auto_reply(subject, body):
                self.logger.record_error("monitor", "matcher", f"Ignored auto-reply from {sender}")
                continue

            matched_row = self.matcher.match_reply_to_row(sender, subject, rows_to_monitor)
            
            if matched_row:
                job_id = matched_row["job_id"]
                snippet = body[:200].replace("\n", " ")
                
                updates.append({
                    "job_id": job_id,
                    "status": "RESPONSE_RECEIVED",
                    "response_received": True,
                    "notes_append": f"[RESPONSE] {sender}: {snippet}..."
                })
                self.logger.record_error(job_id, "monitor", f"Matched response from {sender}")

        return updates

    async def _fetch_inbound_emails(self) -> List[Dict[str, str]]:
        """
        Manual mode: Returns empty list as user checks Gmail inbox manually.
        No automatic Gmail API polling.
        """
        print("INFO: Response monitor in manual mode. User should check Gmail inbox manually for recruiter responses.")
        return []

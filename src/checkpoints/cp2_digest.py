import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.shared.run_logger import RunLogger
from src.shared.sheets_gateway import SheetsGateway
from src.checkpoints.notification_sender import NotificationSender

MANUAL_MODE = os.getenv("MANUAL_MODE", "true").lower() == "true"

class CP2DigestRenderer:
    def render_digest(self, rows: List[dict]) -> dict:
        plain_text = "Action required: The following jobs have generated content awaiting your approval:\n\n"
        html = "<h2>Action Required: Content Awaiting Approval</h2><ul>"
        
        for row in rows:
            company = row.get("company", "Unknown")
            role = row.get("role_title", "Unknown")
            plain_text += f"- {company} ({role})\n"
            plain_text += f"  CV: {row.get('cv_doc_link', 'None')}\n"
            plain_text += f"  Email Draft: {row.get('email_draft_link', 'None')}\n"
            plain_text += f"  DM Draft: {row.get('linkedin_dm_draft', 'None')}\n\n"
            
            html += f"<li><b>{company}</b> ({role})<ul>"
            html += f"<li>CV: <a href='{row.get('cv_doc_link', '#')}'>Link</a></li>"
            html += f"<li>Email: {row.get('email_draft_link', 'None')}</li>"
            html += f"<li>DM: {row.get('linkedin_dm_draft', 'None')}</li></ul></li>"
            
        html += "</ul><p>Please review and set 'cp2_action' to 'Approve' or 'Reject' in the tracker.</p>"
        plain_text += "Please review and set 'cp2_action' to 'Approve' or 'Reject' in the tracker."
        
        return {
            "subject": f"AutoApply CP2 Digest: {len(rows)} jobs awaiting content review",
            "plain_text": plain_text,
            "html": html
        }

def generate_cp2_digest(sheets: SheetsGateway, logger: RunLogger) -> None:
    """
    Generates the CP2 digest containing all rows that are AWAITING_CONTENT_REVIEW
    and have no cp2_action set. Respects MANUAL_MODE flag.
    """
    pending_rows = []
    
    for row in sheets.get_rows_by_status("AWAITING_CONTENT_REVIEW"):
        if not row.get("cp2_action"):
            pending_rows.append(row)

    if not pending_rows:
        logger.record_error("cp2_digest", "generator", "No pending rows for CP2 digest.")
        return

    renderer = CP2DigestRenderer()
    digest = renderer.render_digest(pending_rows)

    if MANUAL_MODE:
        # Save digest to logs/ instead of sending
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        logs_dir = Path("logs")
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / f"cp2_digest_{timestamp}.json"
        
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": timestamp,
                "subject": digest["subject"],
                "plain_text": digest["plain_text"],
                "row_count": len(pending_rows),
                "row_ids": [r.get("job_id") for r in pending_rows]
            }, f, indent=2)
            
        logger.record_error("cp2_digest", "generator", f"MANUAL_MODE: CP2 digest saved to {log_path}")
    else:
        # Actually send via NotificationSender
        try:
            sender = NotificationSender(channel="email")
            sender.send(digest["subject"], digest["plain_text"], digest["html"])
            logger.record_error("cp2_digest", "generator", f"CP2 digest sent for {len(pending_rows)} rows")
        except Exception as e:
            logger.record_error("cp2_digest", "generator", f"Failed to send CP2 digest: {e}")

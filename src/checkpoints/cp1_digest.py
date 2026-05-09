import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.shared.run_logger import RunLogger
from src.shared.sheets_gateway import SheetsGateway


def generate_cp1_digest(sheets: SheetsGateway, logger: RunLogger) -> None:
    """
    Generates the CP1 digest containing all rows that are AWAITING_HUMAN_REVIEW
    and have no human_action set. In this v1/mock implementation, the digest is
    saved to the logs directory.
    """
    pending_rows = []
    
    for row in sheets.get_rows_by_status("AWAITING_HUMAN_REVIEW"):
        if not row.get("human_action"):
            # Only include necessary fields per the data contract
            pending_rows.append({
                "job_id": row.get("job_id"),
                "company": row.get("company"),
                "role_title": row.get("role_title"),
                "job_url": row.get("job_url"),
                "score": row.get("score", 0)
            })

    if not pending_rows:
        logger.record_error("cp1_digest", "generator", "No pending rows for CP1 digest.")
        return

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    digest = {
        "digest_type": "CP1",
        "generated_at": now_iso,
        "rows": pending_rows
    }

    # Write digest to file (simulating notification sender)
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    filename = f"cp1_digest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = logs_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(digest, f, indent=2)

    logger.record_error("cp1_digest", "generator", f"CP1 Digest generated at {filepath} with {len(pending_rows)} jobs.")

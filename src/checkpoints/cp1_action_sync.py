from typing import Callable, Any

from src.orchestrator.state_engine import TransitionContext
from src.shared.run_logger import RunLogger
from src.shared.sheets_gateway import SheetsGateway


def sync_cp1_actions(
    sheets: SheetsGateway, 
    logger: RunLogger, 
    safe_transition_fn: Callable[[dict, str, TransitionContext], None]
) -> None:
    """
    Polls the 'human_action' field for rows in 'AWAITING_HUMAN_REVIEW'.
    Routes decisions to the correct next state and blocks downstream rows
    until action is set.
    """
    for row in sheets.get_rows_by_status("AWAITING_HUMAN_REVIEW"):
        job_id = row["job_id"]
        action = row.get("human_action")
        
        # Block downstream rows until action is set
        if action not in {"Apply", "Outreach Only", "Skip"}:
            continue

        # Route decisions
        if action == "Skip":
            safe_transition_fn(
                row,
                "SKIPPED",
                TransitionContext(human_action="Skip"),
            )
        else:
            # For 'Apply' and 'Outreach Only'
            safe_transition_fn(
                row,
                "CONTACT_DISCOVERY",
                TransitionContext(human_action=action),
            )
            
        logger.increment("cp1_gate")
        logger.record_error(job_id, "cp1_gate", f"Processed action={action}")

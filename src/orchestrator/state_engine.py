from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, Optional, Set


class StateTransitionError(ValueError):
    """Raised when a row tries to move to an invalid status."""


TERMINAL_STATES: FrozenSet[str] = frozenset(
    {"SKIPPED", "HUMAN_REVIEW", "FAILED", "MANUAL_QUEUE", "RESPONSE_RECEIVED", "NO_RESPONSE"}
)

# Non-terminal states that are also valid end-of-run holding states
HOLDING_STATES: FrozenSet[str] = frozenset(
    {"AWAITING_HUMAN_REVIEW", "AWAITING_CONTENT_REVIEW", "ATS_REVIEW", "APPROVED_FOR_EXECUTION", "APPLIED", "OUTREACH_SENT", "MONITORING"}
)

ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "SCRAPED": {"SCORED", "FAILED"},
    "SCORED": {"AWAITING_HUMAN_REVIEW", "SKIPPED", "FAILED"},
    "AWAITING_HUMAN_REVIEW": {"CONTACT_DISCOVERY", "SKIPPED", "FAILED"},
    "CONTACT_DISCOVERY": {"CONTENT_GENERATION", "FAILED"},
    "CONTENT_GENERATION": {"AWAITING_CONTENT_REVIEW", "FAILED"},
    "AWAITING_CONTENT_REVIEW": {"ATS_REVIEW", "CONTENT_GENERATION", "SKIPPED", "HUMAN_REVIEW", "FAILED"},
    # Phase 7: ATS passes → APPROVED_FOR_EXECUTION (Phase 8 reads from here)
    "ATS_REVIEW": {"APPROVED_FOR_EXECUTION", "CONTENT_GENERATION", "HUMAN_REVIEW", "FAILED", "AWAITING_CONTENT_REVIEW"},
    # Phase 8: Agent 4 transitions directly to terminal execution states
    "APPROVED_FOR_EXECUTION": {"APPLIED", "OUTREACH_SENT", "MANUAL_QUEUE", "FAILED", "SKIPPED"},
    # Phase 9: Monitoring the outreach
    "APPLIED": {"MONITORING", "RESPONSE_RECEIVED", "FAILED"},
    "OUTREACH_SENT": {"MONITORING", "RESPONSE_RECEIVED", "FAILED"},
    "MONITORING": {"RESPONSE_RECEIVED", "NO_RESPONSE", "FAILED"},
    # Legacy EXECUTION state kept for schema compatibility
    "EXECUTION": {"APPLIED", "OUTREACH_SENT", "FAILED", "MONITORING"},
}


@dataclass(frozen=True)
class TransitionContext:
    human_action: Optional[str] = None
    cp2_approved: bool = False
    ats_pass: Optional[bool] = None
    revision_count: int = 0


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise StateTransitionError(message)


def validate_transition(current: str, nxt: str, ctx: Optional[TransitionContext] = None) -> None:
    """Validate status movement based on the Phase 0/1 rules."""
    if current in TERMINAL_STATES:
        raise StateTransitionError(f"Terminal status '{current}' cannot transition to '{nxt}'.")

    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if nxt not in allowed:
        raise StateTransitionError(f"Invalid transition '{current}' -> '{nxt}'.")

    ctx = ctx or TransitionContext()

    if current == "AWAITING_HUMAN_REVIEW" and nxt == "CONTACT_DISCOVERY":
        _assert(
            ctx.human_action in {"Apply", "Outreach Only"},
            "CONTACT_DISCOVERY requires human_action Apply or Outreach Only.",
        )
    if current == "AWAITING_HUMAN_REVIEW" and nxt == "SKIPPED":
        _assert(ctx.human_action == "Skip", "SKIPPED requires human_action Skip.")

    if current == "AWAITING_CONTENT_REVIEW" and nxt == "ATS_REVIEW":
        _assert(ctx.cp2_approved, "ATS_REVIEW requires cp2_approved=true.")

    if current == "ATS_REVIEW" and nxt == "APPROVED_FOR_EXECUTION":
        _assert(ctx.ats_pass is True, "APPROVED_FOR_EXECUTION requires ats_pass=true.")
    if current == "ATS_REVIEW" and nxt == "CONTENT_GENERATION":
        _assert(
            (ctx.ats_pass is False) and (ctx.revision_count < 2),
            "CONTENT_GENERATION from ATS_REVIEW requires fail with revision_count < 2.",
        )
    if current == "ATS_REVIEW" and nxt == "HUMAN_REVIEW":
        _assert(
            (ctx.ats_pass is False) and (ctx.revision_count >= 2),
            "HUMAN_REVIEW requires fail with revision_count >= 2.",
        )


def can_transition(current: str, nxt: str, ctx: Optional[TransitionContext] = None) -> bool:
    try:
        validate_transition(current, nxt, ctx)
        return True
    except StateTransitionError:
        return False


def valid_next_states(current: str) -> Iterable[str]:
    return tuple(ALLOWED_TRANSITIONS.get(current, set()))

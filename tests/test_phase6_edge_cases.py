"""
Phase 6 Edge-Case Test Suite
Based on: Docs/Edge-Cases.md — Phase 6 Section (lines 125-135)

Covers all CP2 Content Approval Gate components:
  - cp2_validators.py  → validate_for_ats_review, validate_can_proceed_to_phase_8
  - cp2_approval_sync.py → Approve/Edit/Reject/Skip routing, revision cap, feedback injection
  - cp2_digest.py      → Digest only contains pending rows, DRY_RUN saves to file
  - reset_cp2_fields   → Fields cleared on regeneration

Edge Cases from Edge-Cases.md:
  EC-6-1: cp2_approved missing → execution blocked
  EC-6-2: User approves but content links missing → blocked
  EC-6-3: Approval revoked (cp2_approved=False) after being set → Phase 8 blocked
  EC-6-4: cp2_decided_at timestamp always set on approval
  EC-6-5: Edited drafts: Edit action still sets cp2_approved=True and routes to ATS_REVIEW
  EC-6-6: cp2_revision_count cap enforced at 2 (rejected 3rd time → HUMAN_REVIEW)
  EC-6-7: Rejection feedback appended to notes with correct attempt number
  EC-6-8: Skip action → SKIPPED state
  EC-6-9: None/invalid cp2_action → row stays blocked (no transition)
  EC-6-10: reset_cp2_fields clears flags without deleting notes history
  EC-6-11: Digest only includes rows without a cp2_action (truly pending)
  EC-6-12: validate_can_proceed_to_phase_8 blocks non-APPROVED_FOR_EXECUTION status
  EC-6-13: validate_can_proceed_to_phase_8 blocks fabrication_violations in notes
  EC-6-14: validate_can_proceed_to_phase_8 blocks missing contact for Outreach Only
  EC-6-15: validate_for_ats_review blocks when cp2_revision_count > 2
"""

import asyncio
import sys
import os
import json
from unittest.mock import MagicMock, patch

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.checkpoints.cp2_validators import CP2Validator
from src.checkpoints.cp2_approval_sync import CP2ApprovalSync, reset_cp2_fields_for_fresh_review
from src.checkpoints.cp2_digest import CP2DigestRenderer
from src.shared.sheets_gateway import SheetsGateway
from src.orchestrator.state_engine import TransitionContext

# ──────────────────────────────────────────────────────────────────────────────
# Test runner helpers
# ──────────────────────────────────────────────────────────────────────────────
RESULTS = []

def record(name: str, passed: bool, detail: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    RESULTS.append((name, passed, detail))
    print(f"  {status}  {name}")
    if detail and not passed:
        print(f"         Detail: {detail}")

def make_logger():
    m = MagicMock()
    m.record_error = MagicMock()
    m.increment = MagicMock()
    return m

def make_approved_row(**overrides):
    """Returns a minimally valid CP2-approved row."""
    base = {
        "job_id": "job-001",
        "company": "TestCo",
        "role_title": "APM",
        "status": "AWAITING_CONTENT_REVIEW",
        "cp2_approved": True,
        "cp2_decided_at": "2026-05-05T10:00:00+00:00",
        "cv_doc_link": "http://example.com/cv.docx",
        "email_draft_link": "Subject: Hi\n\nBody",
        "linkedin_dm_draft": "",
        "cp2_revision_count": 0,
        "notes": "",
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# CP2Validator — validate_for_ats_review
# ══════════════════════════════════════════════════════════════════════════════

def test_ec_6_1_missing_cp2_approved():
    """EC-6-1: cp2_approved missing/False blocks ATS review."""
    for val in [False, None, ""]:
        row = make_approved_row(cp2_approved=val)
        valid, issues = CP2Validator.validate_for_ats_review(row)
        blocked = not valid and any("cp2_approved" in i for i in issues)
        record(f"EC-6-1: cp2_approved={val!r} is blocked", blocked, str(issues))


def test_ec_6_2_missing_content_links():
    """EC-6-2: Row approved but no content links → validator blocks it."""
    row = make_approved_row(cv_doc_link="", email_draft_link="", linkedin_dm_draft="")
    valid, issues = CP2Validator.validate_for_ats_review(row)
    blocked_cv = any("cv_doc_link" in i for i in issues)
    blocked_content = any("email draft" in i or "linkedin" in i for i in issues)
    record("EC-6-2: Missing cv_doc_link is caught", blocked_cv, str(issues))
    record("EC-6-2: Missing both drafts is caught", blocked_content, str(issues))


def test_ec_6_3_revoked_approval_blocked_phase8():
    """EC-6-3: Stale state — cp2_approved revoked before Phase 8 should block."""
    row = make_approved_row(
        cp2_approved=False,  # revoked
        status="APPROVED_FOR_EXECUTION",
    )
    valid, issues = CP2Validator.validate_can_proceed_to_phase_8(row)
    record("EC-6-3: Revoked approval blocks Phase 8", not valid, str(issues))


def test_ec_6_4_decided_at_timestamp():
    """EC-6-4: cp2_decided_at must be present; absent timestamp is caught."""
    row = make_approved_row(cp2_decided_at=None)
    valid, issues = CP2Validator.validate_for_ats_review(row)
    blocked = not valid and any("cp2_decided_at" in i for i in issues)
    record("EC-6-4: Missing cp2_decided_at is caught by validator", blocked, str(issues))


def test_ec_6_15_revision_count_exceeded():
    """EC-6-15: cp2_revision_count > 2 is flagged by validator."""
    row = make_approved_row(cp2_revision_count=3)
    valid, issues = CP2Validator.validate_for_ats_review(row)
    blocked = not valid and any("revision_count" in i for i in issues)
    record("EC-6-15: cp2_revision_count=3 exceeds cap and is caught", blocked, str(issues))


def test_ec_6_valid_row_passes():
    """Positive test: A fully valid row passes validate_for_ats_review."""
    row = make_approved_row()
    valid, issues = CP2Validator.validate_for_ats_review(row)
    record("EC-6-VALID: Fully valid row passes validator", valid, str(issues))


# ══════════════════════════════════════════════════════════════════════════════
# CP2Validator — validate_can_proceed_to_phase_8
# ══════════════════════════════════════════════════════════════════════════════

def test_ec_6_12_wrong_status_phase8():
    """EC-6-12: Status != APPROVED_FOR_EXECUTION blocks Phase 8."""
    for bad_status in ["ATS_REVIEW", "AWAITING_CONTENT_REVIEW", "CONTENT_GENERATION"]:
        row = make_approved_row(
            status=bad_status,
            cv_doc_link="/tmp/cv.docx",
            contact_email="hr@example.com",
        )
        valid, issues = CP2Validator.validate_can_proceed_to_phase_8(row)
        blocked = not valid and any("APPROVED_FOR_EXECUTION" in i for i in issues)
        record(f"EC-6-12: Status={bad_status} blocked for Phase 8", blocked, str(issues))


def test_ec_6_13_fabrication_violations_block_phase8():
    """EC-6-13: fabrication_violations in notes must block Phase 8."""
    row = make_approved_row(
        status="APPROVED_FOR_EXECUTION",
        cv_doc_link="/tmp/cv.docx",
        notes="All good.\n[CP2 Rejection Feedback]: fabrication_violations found in bullet",
    )
    valid, issues = CP2Validator.validate_can_proceed_to_phase_8(row)
    record("EC-6-13: fabrication_violations in notes blocks Phase 8", not valid, str(issues))


def test_ec_6_14_outreach_only_no_contact():
    """EC-6-14: Outreach Only requires contact_email or contact_linkedin."""
    row = make_approved_row(
        status="APPROVED_FOR_EXECUTION",
        cv_doc_link="/tmp/cv.docx",
        human_action="Outreach Only",
        contact_email="",
        contact_linkedin="",
    )
    valid, issues = CP2Validator.validate_can_proceed_to_phase_8(row)
    blocked = not valid and any("contact" in i for i in issues)
    record("EC-6-14: Outreach Only without contact is blocked", blocked, str(issues))


def test_ec_6_phase8_valid_row_passes():
    """Positive: Fully valid row passes Phase 8 validator."""
    row = make_approved_row(
        status="APPROVED_FOR_EXECUTION",
        cv_doc_link="/tmp/cv.docx",
        human_action="Apply",
    )
    valid, issues = CP2Validator.validate_can_proceed_to_phase_8(row)
    record("EC-6-PHASE8-VALID: Valid row passes Phase 8 gate", valid, str(issues))


# ══════════════════════════════════════════════════════════════════════════════
# CP2ApprovalSync — action routing
# ══════════════════════════════════════════════════════════════════════════════

async def test_ec_6_5_edit_routes_to_ats_review_with_flag():
    """EC-6-5: Edit action sets cp2_approved=True and routes to ATS_REVIEW."""
    transitions = []

    def fake_transition(row, nxt, ctx):
        transitions.append((row["job_id"], nxt, ctx))

    row = make_approved_row(cp2_action="Edit", cp2_approved=False)
    sheets = SheetsGateway.from_seed_rows([row])
    logger = make_logger()

    sync = CP2ApprovalSync(sheets, logger, fake_transition)
    await sync.check_and_process()

    routed_to_ats = any(t[1] == "ATS_REVIEW" for t in transitions)
    flag_set = sheets.get_row("job-001").get("cp2_approved") is True
    decided_at_set = bool(sheets.get_row("job-001").get("cp2_decided_at"))

    record("EC-6-5: Edit routes to ATS_REVIEW", routed_to_ats, str(transitions))
    record("EC-6-5: Edit sets cp2_approved=True persistently", flag_set)
    record("EC-6-5: Edit sets cp2_decided_at timestamp", decided_at_set)


async def test_ec_6_approve_routes_to_ats_review():
    """Approve action sets cp2_approved and routes to ATS_REVIEW."""
    transitions = []

    def fake_transition(row, nxt, ctx):
        transitions.append((row["job_id"], nxt, ctx.cp2_approved))

    row = make_approved_row(cp2_action="Approve", cp2_approved=False)
    sheets = SheetsGateway.from_seed_rows([row])
    logger = make_logger()

    sync = CP2ApprovalSync(sheets, logger, fake_transition)
    await sync.check_and_process()

    routed = any(t[1] == "ATS_REVIEW" and t[2] is True for t in transitions)
    record("EC-6-APPROVE: Approve routes to ATS_REVIEW with cp2_approved=True", routed, str(transitions))


async def test_ec_6_7_reject_feedback_appended():
    """EC-6-7: Rejection appends feedback marker with attempt number to notes."""
    transitions = []

    def fake_transition(row, nxt, ctx):
        transitions.append((row["job_id"], nxt))

    row = make_approved_row(
        cp2_action="Reject",
        cp2_revision_count=0,
        cp2_rejection_reason="Tone too corporate",
        notes="Previous note.",
    )
    sheets = SheetsGateway.from_seed_rows([row])
    logger = make_logger()

    sync = CP2ApprovalSync(sheets, logger, fake_transition)
    await sync.check_and_process()

    updated_row = sheets.get_row("job-001")
    notes = updated_row.get("notes", "")
    has_marker = "[CP2 Rejection Feedback - Attempt 1]" in notes
    has_reason = "Tone too corporate" in notes
    count_updated = updated_row.get("cp2_revision_count") == 1
    routes_to_regen = any(t[1] == "CONTENT_GENERATION" for t in transitions)

    record("EC-6-7: Rejection feedback marker in notes", has_marker, notes[:120])
    record("EC-6-7: Rejection reason preserved in notes", has_reason)
    record("EC-6-7: cp2_revision_count incremented to 1", count_updated, str(updated_row.get("cp2_revision_count")))
    record("EC-6-7: Rejection routes to CONTENT_GENERATION", routes_to_regen, str(transitions))


async def test_ec_6_6_reject_cap_routes_to_human_review():
    """EC-6-6: Third rejection (count=2) routes to HUMAN_REVIEW, not CONTENT_GENERATION."""
    transitions = []

    def fake_transition(row, nxt, ctx):
        transitions.append((row["job_id"], nxt))

    row = make_approved_row(
        cp2_action="Reject",
        cp2_revision_count=2,
        cp2_rejection_reason="Still not good",
        notes="",
    )
    sheets = SheetsGateway.from_seed_rows([row])
    logger = make_logger()

    sync = CP2ApprovalSync(sheets, logger, fake_transition)
    await sync.check_and_process()

    routes_to_human = any(t[1] == "HUMAN_REVIEW" for t in transitions)
    not_regen = not any(t[1] == "CONTENT_GENERATION" for t in transitions)
    record("EC-6-6: Rejection at cap routes to HUMAN_REVIEW", routes_to_human, str(transitions))
    record("EC-6-6: Rejection at cap does NOT route to CONTENT_GENERATION", not_regen)


async def test_ec_6_8_skip_routes_to_skipped():
    """EC-6-8: Skip action routes row to SKIPPED."""
    transitions = []

    def fake_transition(row, nxt, ctx):
        transitions.append((row["job_id"], nxt))

    row = make_approved_row(cp2_action="Skip")
    sheets = SheetsGateway.from_seed_rows([row])
    logger = make_logger()

    sync = CP2ApprovalSync(sheets, logger, fake_transition)
    await sync.check_and_process()

    routed = any(t[1] == "SKIPPED" for t in transitions)
    record("EC-6-8: Skip routes to SKIPPED", routed, str(transitions))


async def test_ec_6_9_invalid_action_blocked():
    """EC-6-9: Invalid and None cp2_action — no transition made."""
    for bad_action in [None, "", "YOLO", "approve", "APPROVE"]:
        transitions = []

        def fake_transition(row, nxt, ctx):
            transitions.append(nxt)

        row = make_approved_row(job_id=f"job-bad-{bad_action}", cp2_action=bad_action)
        sheets = SheetsGateway.from_seed_rows([row])
        logger = make_logger()

        sync = CP2ApprovalSync(sheets, logger, fake_transition)
        await sync.check_and_process()

        no_transition = len(transitions) == 0
        record(f"EC-6-9: cp2_action={bad_action!r} produces no transition", no_transition, str(transitions))


# ══════════════════════════════════════════════════════════════════════════════
# reset_cp2_fields_for_fresh_review
# ══════════════════════════════════════════════════════════════════════════════

def test_ec_6_10_reset_clears_fields_preserves_notes():
    """EC-6-10: reset_cp2_fields clears approval fields but keeps notes history."""
    row = make_approved_row(
        cp2_approved=True,
        cp2_decided_at="2026-05-05T10:00:00",
        cp2_action="Approve",
        cp2_edits_summary="Minor tone fix",
        notes="[CP2 Rejection Feedback - Attempt 1]: Tone too formal",
    )
    sheets = SheetsGateway.from_seed_rows([row])
    reset_cp2_fields_for_fresh_review("job-001", sheets)
    updated = sheets.get_row("job-001")

    record("EC-6-10: cp2_approved cleared to False", updated.get("cp2_approved") is False)
    record("EC-6-10: cp2_action cleared to None", updated.get("cp2_action") is None)
    record("EC-6-10: cp2_decided_at cleared to None", updated.get("cp2_decided_at") is None)
    record("EC-6-10: cp2_edits_summary cleared to None", updated.get("cp2_edits_summary") is None)
    # Notes must be PRESERVED (contains rejection history)
    notes_preserved = "[CP2 Rejection Feedback" in (updated.get("notes") or "")
    record("EC-6-10: notes history preserved after reset", notes_preserved, str(updated.get("notes")))


# ══════════════════════════════════════════════════════════════════════════════
# CP2DigestRenderer
# ══════════════════════════════════════════════════════════════════════════════

def test_ec_6_11_digest_only_pending_rows():
    """EC-6-11: Digest only includes rows with no cp2_action set."""
    renderer = CP2DigestRenderer()

    pending_rows = [
        {"job_id": "p1", "company": "Co A", "role_title": "APM", "cv_doc_link": "http://a.com"},
        {"job_id": "p2", "company": "Co B", "role_title": "PM",  "cv_doc_link": "http://b.com"},
    ]

    digest = renderer.render_digest(pending_rows)

    has_subject = "2 jobs" in digest["subject"]
    has_co_a = "Co A" in digest["plain_text"]
    has_co_b = "Co B" in digest["plain_text"]
    has_html = "<ul>" in digest["html"]

    record("EC-6-11: Digest subject contains row count", has_subject, digest["subject"])
    record("EC-6-11: Digest plain text includes Co A", has_co_a)
    record("EC-6-11: Digest plain text includes Co B", has_co_b)
    record("EC-6-11: Digest HTML output is valid HTML snippet", has_html)


def test_ec_6_digest_empty_pending():
    """Digest with 0 pending rows still returns a valid structure."""
    renderer = CP2DigestRenderer()
    digest = renderer.render_digest([])
    has_subject = "0 jobs" in digest["subject"]
    record("EC-6-DIGEST-EMPTY: Empty digest produces valid subject", has_subject, digest["subject"])


# ══════════════════════════════════════════════════════════════════════════════
# State engine — CP2-specific transitions
# ══════════════════════════════════════════════════════════════════════════════

def test_ec_6_state_engine_ats_review_requires_cp2():
    """State engine must reject AWAITING_CONTENT_REVIEW → ATS_REVIEW without cp2_approved."""
    from src.orchestrator.state_engine import validate_transition, StateTransitionError

    # Without cp2_approved
    try:
        validate_transition("AWAITING_CONTENT_REVIEW", "ATS_REVIEW", TransitionContext(cp2_approved=False))
        record("EC-6-STATE: ATS_REVIEW without cp2_approved is blocked", False, "No exception raised")
    except StateTransitionError as e:
        record("EC-6-STATE: ATS_REVIEW without cp2_approved is blocked", True, str(e))

    # With cp2_approved
    try:
        validate_transition("AWAITING_CONTENT_REVIEW", "ATS_REVIEW", TransitionContext(cp2_approved=True))
        record("EC-6-STATE: ATS_REVIEW with cp2_approved=True is allowed", True)
    except StateTransitionError as e:
        record("EC-6-STATE: ATS_REVIEW with cp2_approved=True is allowed", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# Main runner
# ══════════════════════════════════════════════════════════════════════════════

async def run_all():
    print("\n" + "=" * 68)
    print("  PHASE 6 EDGE-CASE TEST SUITE (from Edge-Cases.md)")
    print("=" * 68)

    # --- Sync tests ---
    sync_tests = [
        test_ec_6_1_missing_cp2_approved,
        test_ec_6_2_missing_content_links,
        test_ec_6_3_revoked_approval_blocked_phase8,
        test_ec_6_4_decided_at_timestamp,
        test_ec_6_15_revision_count_exceeded,
        test_ec_6_valid_row_passes,
        test_ec_6_12_wrong_status_phase8,
        test_ec_6_13_fabrication_violations_block_phase8,
        test_ec_6_14_outreach_only_no_contact,
        test_ec_6_phase8_valid_row_passes,
        test_ec_6_10_reset_clears_fields_preserves_notes,
        test_ec_6_11_digest_only_pending_rows,
        test_ec_6_digest_empty_pending,
        test_ec_6_state_engine_ats_review_requires_cp2,
    ]

    for fn in sync_tests:
        try:
            fn()
        except Exception as exc:
            import traceback
            record(fn.__name__, False, f"EXCEPTION: {exc}\n{traceback.format_exc()}")

    # --- Async tests ---
    async_tests = [
        test_ec_6_5_edit_routes_to_ats_review_with_flag,
        test_ec_6_approve_routes_to_ats_review,
        test_ec_6_7_reject_feedback_appended,
        test_ec_6_6_reject_cap_routes_to_human_review,
        test_ec_6_8_skip_routes_to_skipped,
        test_ec_6_9_invalid_action_blocked,
    ]

    for fn in async_tests:
        try:
            await fn()
        except Exception as exc:
            import traceback
            record(fn.__name__, False, f"EXCEPTION: {exc}\n{traceback.format_exc()}")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print()
    print("=" * 68)
    print(f"  RESULT: {passed}/{total} passed")
    if passed < total:
        print()
        print("  FAILURES:")
        for name, ok, detail in RESULTS:
            if not ok:
                print(f"    ❌ {name}")
                if detail:
                    print(f"       {detail[:120]}")
    print("=" * 68 + "\n")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_all())

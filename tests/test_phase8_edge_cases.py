"""
Phase 8 Edge-Case Test Suite
Based on: Docs/Edge-Cases.md — Phase 8 Section (lines 152-172)

Covers:
  - EC-8-1: Submission failure (unknown state) handling
  - EC-8-2: Anti-bot (CAPTCHA) detection → MANUAL_QUEUE
  - EC-8-3: Idempotency (already applied) guard
  - EC-8-4: Gmail cap exceeded → MANUAL_QUEUE
  - EC-8-5: LinkedIn risk signal → MANUAL_QUEUE pivot
  - EC-8-6: Missing drafts for Manual Queue → validation check
"""

import asyncio
import sys
import os
import json
from unittest.mock import MagicMock, patch, AsyncMock

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agent_4.pipeline import ExecutionAgent
from src.agent_4.channel_policy import ChannelUsage, GMAIL_DAILY_CAP
from src.agent_4.linkedin_outreach import LINKEDIN_RISK_SIGNALS
from src.shared.run_logger import RunLogger

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

def make_approved_row(**overrides):
    base = {
        "job_id": "test-8",
        "company": "EdgeCo",
        "role_title": "APM",
        "status": "APPROVED_FOR_EXECUTION",
        "human_action": "Apply",
        "job_url": "https://edge.com/jobs/apm",
        "cv_doc_link": "/tmp/cv_outputs/test.docx",
        "email_draft_link": "Subject: Hi\n\nBody",
        "contact_email": "hr@edge.com",
        "cp2_approved": True,
        "cp2_decided_at": "2026-05-05T10:00:00",
        "notes": "",
    }
    base.update(overrides)
    return base


# ──────────────────────────────────────────────────────────────────────────────
# EC-8-1: Submission failure (unknown state)
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_8_1_submission_failure():
    """EC-8-1: Portal error during submission sets status to FAILED."""
    agent = ExecutionAgent(RunLogger())
    
    # Mock submitter to fail
    agent.submitter.submit = AsyncMock(return_value={
        "success": False,
        "error": "Timeout on page 3 of application form",
        "applied_at": None
    })
    
    row = make_approved_row()
    result = await agent.execute_row(row)
    
    record(
        "EC-8-1: Submission failure results in FAILED state",
        result["final_status"] == "FAILED",
        f"Status: {result['final_status']}, Error: {result['error']}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# EC-8-2: Anti-bot (CAPTCHA) detection
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_8_2_captcha_detection():
    """EC-8-2: CAPTCHA detected during LinkedIn DM → MANUAL_QUEUE pivot."""
    agent = ExecutionAgent(RunLogger())
    
    # Mock LinkedIn to hit a risk signal
    agent.linkedin.send_dm = AsyncMock(return_value={
        "success": False,
        "error": "Page contains CAPTCHA",
        "sent_at": None,
        "route_to_manual": True
    })
    
    row = make_approved_row(
        human_action="Outreach Only", 
        contact_email="",  # Ensure only LinkedIn is tried
        contact_linkedin="https://linkedin.com/in/test"
    )
    result = await agent.execute_row(row)
    
    record(
        "EC-8-2: CAPTCHA risk signal pivots to MANUAL_QUEUE",
        result["final_status"] == "MANUAL_QUEUE",
        f"Status: {result['final_status']}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# EC-8-3: Idempotency guard
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_8_3_idempotency():
    """EC-8-3: Already applied row skips submission."""
    agent = ExecutionAgent(RunLogger())
    row = make_approved_row(applied_at="2026-05-01T10:00:00Z")
    
    # If it tries to submit, it's a fail. Submitter has internal guard too.
    result = await agent.execute_row(row)
    
    # Should still be APPLIED but with existing timestamp
    record(
        "EC-8-3: Idempotency guard skips re-submission",
        result["final_status"] == "APPLIED" and result.get("applied_at") == "2026-05-01T10:00:00Z",
        str(result)
    )


# ──────────────────────────────────────────────────────────────────────────────
# EC-8-4: Gmail cap exceeded
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_8_4_gmail_cap():
    """EC-8-4: When Gmail daily cap is hit, row routes to MANUAL_QUEUE."""
    agent = ExecutionAgent(RunLogger())
    # Force cap hit
    agent.usage.emails_sent = GMAIL_DAILY_CAP
    
    row = make_approved_row(human_action="Outreach Only")
    result = await agent.execute_row(row)
    
    record(
        "EC-8-4: Gmail daily cap hit routes Outreach Only to MANUAL_QUEUE",
        result["final_status"] == "MANUAL_QUEUE",
        f"Status: {result['final_status']}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# EC-8-5: LinkedIn risk signal pivot
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_8_5_linkedin_risk_pivot():
    """EC-8-5: 'Account Restricted' signal detected → MANUAL_QUEUE pivot."""
    agent = ExecutionAgent(RunLogger())
    
    # Mock LinkedIn outreach to return a known risk signal error
    agent.linkedin.send_dm = AsyncMock(return_value={
        "success": False,
        "error": f"LinkedIn error: {LINKEDIN_RISK_SIGNALS[0]}",
        "sent_at": None,
        "route_to_manual": True
    })
    
    row = make_approved_row(
        human_action="Outreach Only", 
        contact_email="",  # Ensure only LinkedIn is tried
        contact_linkedin="https://ln.com/test"
    )
    result = await agent.execute_row(row)
    
    record(
        "EC-8-5: LinkedIn risk signal detected → pivot to MANUAL_QUEUE",
        result["final_status"] == "MANUAL_QUEUE",
        f"Status: {result['final_status']}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# EC-8-6: Safety Gate - Missing drafts
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_8_6_safety_missing_content():
    """EC-8-6: Approved for execution but draft is missing → SAFETY FAILED."""
    agent = ExecutionAgent(RunLogger())
    
    # Missing both email and dm drafts for Outreach Only
    row = make_approved_row(human_action="Outreach Only", email_draft_link="", linkedin_dm_draft="")
    result = await agent.execute_row(row)
    
    record(
        "EC-8-6: Missing drafts for Outreach Only results in FAILED status",
        result["final_status"] == "FAILED",
        f"Status: {result['final_status']}, Error: {result['error']}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Main runner
# ──────────────────────────────────────────────────────────────────────────────
async def run_all():
    print("\n" + "=" * 65)
    print("  PHASE 8 EDGE-CASE TEST SUITE (from Edge-Cases.md)")
    print("=" * 65)

    tests = [
        test_ec_8_1_submission_failure,
        test_ec_8_2_captcha_detection,
        test_ec_8_3_idempotency,
        test_ec_8_4_gmail_cap,
        test_ec_8_5_linkedin_risk_pivot,
        test_ec_8_6_safety_missing_content,
    ]

    for test_fn in tests:
        try:
            await test_fn()
        except Exception as exc:
            import traceback
            record(test_fn.__name__, False, f"EXCEPTION: {exc}\n{traceback.format_exc()}")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print()
    print("=" * 65)
    print(f"  RESULT: {passed}/{total} passed")
    print("=" * 65 + "\n")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_all())

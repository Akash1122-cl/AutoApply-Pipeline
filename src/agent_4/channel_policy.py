"""
Channel Policy Engine — Phase 8

Enforces per-channel daily limits and determines the correct action
for each row based on human_action and available contact data.

Rules (from Context.md / Architecture.md):
  - Gmail free-tier cap: max 20 emails/day
  - Application cap: 20-25/day (LinkedIn flags above this)
  - LinkedIn DM fallback: if risky/blocked → MANUAL_QUEUE
  - Never send without CP2 approval
  - Never submit to the same job_url twice
"""

import os
from dataclasses import dataclass, field
from datetime import date


# ─────────────────────────── Constants ───────────────────────────────────────
# Daily caps (not used in manual mode, kept for reference)
# All operations are manual, so caps are not enforced
GMAIL_DAILY_CAP: int = int(os.getenv("GMAIL_DAILY_CAP", "20"))
APPLICATION_DAILY_CAP: int = int(os.getenv("APPLICATION_DAILY_CAP", "20"))
LINKEDIN_DAILY_CAP: int = int(os.getenv("LINKEDIN_DAILY_CAP", "20"))

# Channel action values
ACTION_APPLY = "apply"
ACTION_EMAIL = "email"
ACTION_LINKEDIN_DM = "linkedin_dm"
ACTION_MANUAL_QUEUE = "manual_queue"
ACTION_SKIP = "skip"


# ────────────────────────── Policy state tracker ─────────────────────────────
@dataclass
class ChannelUsage:
    """Tracks same-run usage counts to enforce daily caps."""
    emails_sent: int = 0
    applications_submitted: int = 0
    linkedin_dms_sent: int = 0
    manual_queued: int = 0

    def can_send_email(self) -> bool:
        return self.emails_sent < GMAIL_DAILY_CAP

    def can_submit_application(self) -> bool:
        return self.applications_submitted < APPLICATION_DAILY_CAP

    def can_send_linkedin(self) -> bool:
        return self.linkedin_dms_sent < LINKEDIN_DAILY_CAP


# ────────────────────────── Decision result ──────────────────────────────────
@dataclass
class ChannelDecision:
    """The outcome of the policy engine for a single row."""
    action: str                     # One of the ACTION_* constants
    reason: str                     # Human-readable explanation
    send_email: bool = False
    send_linkedin_dm: bool = False
    submit_application: bool = False
    route_to_manual: bool = False


# ─────────────────────────── Policy engine ───────────────────────────────────
class ChannelPolicyEngine:
    """
    Determines what execution action to take for an approved row.
    Called once per row at the start of _process_execution().
    """

    def __init__(self, usage: ChannelUsage):
        self.usage = usage

    def decide(self, row: dict) -> ChannelDecision:
        """
        Returns a ChannelDecision based on human_action, contact data,
        and remaining daily quotas.
        """
        human_action = row.get("human_action", "")
        has_email = bool(row.get("contact_email"))
        has_linkedin = bool(row.get("contact_linkedin"))
        job_url = row.get("job_url", "")

        # ── Apply (submit job application + optional outreach) ────────────────
        if human_action == "Apply":
            if not job_url:
                return ChannelDecision(
                    action=ACTION_MANUAL_QUEUE,
                    reason="job_url missing — cannot automate submission",
                    route_to_manual=True,
                )
            if not self.usage.can_submit_application():
                return ChannelDecision(
                    action=ACTION_MANUAL_QUEUE,
                    reason=f"Application daily cap ({APPLICATION_DAILY_CAP}) reached",
                    route_to_manual=True,
                )
            decision = ChannelDecision(
                action=ACTION_APPLY,
                reason="Submitting application via job portal",
                submit_application=True,
            )
            # Also send cold email if contact available and quota permits
            if has_email and self.usage.can_send_email():
                decision.send_email = True
            return decision

        # ── Outreach Only (email + optional LinkedIn DM) ──────────────────────
        if human_action == "Outreach Only":
            if not has_email and not has_linkedin:
                return ChannelDecision(
                    action=ACTION_MANUAL_QUEUE,
                    reason="No contact found — cannot execute outreach automatically",
                    route_to_manual=True,
                )

            decision = ChannelDecision(
                action=ACTION_EMAIL,
                reason="Sending cold email outreach",
            )

            if has_email:
                if self.usage.can_send_email():
                    decision.send_email = True
                else:
                    # Email cap hit — try LinkedIn instead
                    decision.reason = f"Gmail cap ({GMAIL_DAILY_CAP}) reached, pivoting to LinkedIn"
                    decision.action = ACTION_LINKEDIN_DM

            if has_linkedin and self.usage.can_send_linkedin():
                decision.send_linkedin_dm = True

            # If nothing can be sent, route to manual
            if not decision.send_email and not decision.send_linkedin_dm:
                return ChannelDecision(
                    action=ACTION_MANUAL_QUEUE,
                    reason="All channel caps reached — queued for manual send",
                    route_to_manual=True,
                )
            return decision

        # ── Unknown / Skip ────────────────────────────────────────────────────
        return ChannelDecision(
            action=ACTION_SKIP,
            reason=f"human_action='{human_action}' — no execution required",
        )

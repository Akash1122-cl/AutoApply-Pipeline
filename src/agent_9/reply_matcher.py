"""
Reply Matcher — Phase 9

Matches inbound emails to job/application rows in the tracker.
Uses email address as primary key and fuzzy subject matching as fallback.
"""

import re
from typing import List, Optional, Dict


class ReplyMatcher:
    def match_reply_to_row(self, email_addr: str, subject: str, rows: List[dict]) -> Optional[dict]:
        """
        Attempts to find a matching row for a given inbound email.
        """
        email_addr = email_addr.lower().strip()
        subject_lower = subject.lower().strip()

        # 1. Primary Match: contact_email
        for row in rows:
            if row.get("contact_email") and row["contact_email"].lower().strip() == email_addr:
                return row

        # 2. Secondary Match: Fuzzy Subject Match
        # Look for company name or role title in the subject line
        for row in rows:
            company = row.get("company", "").lower().strip()
            role = row.get("role_title", "").lower().strip()
            
            # If company name is long enough to be unique-ish
            if company and len(company) > 3 and company in subject_lower:
                return row
                
        return None

    def is_auto_reply(self, subject: str, body: str) -> bool:
        """
        Detects if an email is an OOO, auto-reply, or newsletter based on common patterns.
        """
        subject_lower = subject.lower()
        body_lower = body.lower()

        patterns = [
            r"\bout of (the )?office\b",
            r"\bautomatic reply\b",
            r"\bauto-reply\b",
            r"\bunsubscribe\b",
            r"\bnewsletter\b",
            r"\bthank you for (your )?interest\b", # often automated rejections
        ]

        for pattern in patterns:
            if re.search(pattern, subject_lower) or re.search(pattern, body_lower[:200]):
                return True
                
        return False

from typing import Tuple, List

class CP2Validator:
    """
    Strict validation layer that runs before any ATS or Execution steps.
    Enforces the persistent 'cp2_approved' flag to prevent manual bypasses.
    """

    @staticmethod
    def validate_for_ats_review(row: dict) -> Tuple[bool, List[str]]:
        """
        Used by Phase 7 (ATS Review).
        Verifies:
        - cp2_approved == True
        - cp2_decided_at is set
        - cv_doc_link exists
        - email_draft_link OR linkedin_dm_draft has content
        - cp2_revision_count <= 2
        """
        issues = []
        
        if not row.get("cp2_approved"):
            issues.append("cp2_approved is False or missing")
            
        if not row.get("cp2_decided_at"):
            issues.append("cp2_decided_at timestamp is missing")
            
        if not row.get("cv_doc_link"):
            issues.append("cv_doc_link is missing")
            
        has_email = bool(row.get("email_draft_link"))
        has_dm = bool(row.get("linkedin_dm_draft"))
        if not (has_email or has_dm):
            issues.append("Must have at least an email draft or linkedin dm draft")
            
        revision_count = int(row.get("cp2_revision_count", 0))
        if revision_count > 2:
            issues.append(f"cp2_revision_count ({revision_count}) exceeds cap of 2")
            
        return len(issues) == 0, issues

    @staticmethod
    def validate_can_proceed_to_phase_8(row: dict) -> Tuple[bool, List[str]]:
        """
        Final validator before Phase 8 sends emails or DMs externally.
        Phase 8 MUST call this method on every row before any external action.
        This is the absolute final gate enforcing 'never send without CP2 approval'.
        """
        # First, it must pass the ATS review validation
        is_valid, issues = CP2Validator.validate_for_ats_review(row)
        
        # It must be APPROVED_FOR_EXECUTION
        status = row.get("status")
        if status != "APPROVED_FOR_EXECUTION":
            issues.append(f"Status is {status}, must be APPROVED_FOR_EXECUTION")
            is_valid = False
            
        # No fabrication violations
        notes = row.get("notes", "")
        if "fabrication_violations" in notes.lower() or "fabrication detected" in notes.lower():
            issues.append("Fabrication violations found in notes")
            is_valid = False
            
        # Normalise path separators so the check works on both Windows (C:\tmp) and Unix (/tmp)
        cv_link = row.get("cv_doc_link", "")
        normalised_link = cv_link.replace("\\", "/")
        if not cv_link or ("http" not in normalised_link and "tmp/" not in normalised_link):
            issues.append("cv_doc_link is invalid or inaccessible")
            is_valid = False
            
        # Must have a contact to send to if action requires sending
        # Note: If they selected "Apply", they might not need an email, but outreach needs one.
        # This is a strict check, we ensure at least one contact method exists.
        has_contact_email = bool(row.get("contact_email"))
        has_contact_linkedin = bool(row.get("contact_linkedin"))
        
        human_action = row.get("human_action", "")
        if human_action == "Outreach Only":
            if not (has_contact_email or has_contact_linkedin):
                issues.append("Outreach requires contact_email or contact_linkedin")
                is_valid = False
                
        return is_valid, issues

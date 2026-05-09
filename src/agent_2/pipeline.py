from typing import Dict, Any

from src.shared.run_logger import RunLogger
from src.agent_2.retry import RetryPolicy
from src.agent_2.enrichment.hunter_provider import HunterProvider
from src.agent_2.enrichment.pattern_provider import PatternProvider
from src.agent_2.enrichment.linkedin_search import LinkedInSearch
from src.agent_2.verification import EmailVerifier


class ContactDiscoveryAgent:
    """Main pipeline for Phase 4 Contact Discovery."""
    
    def __init__(self, logger: RunLogger):
        self.logger = logger
        self.retry_policy = RetryPolicy(logger)
        self.hunter = HunterProvider(logger, self.retry_policy)
        self.pattern_provider = PatternProvider()
        self.verifier = EmailVerifier(logger, self.retry_policy)
        
        # Priority mapping
        self.priority_keywords = [
            ["recruiter", "talent acquisition"],
            ["hiring manager", "product manager"],
            ["head of product", "cpo", "vp product"],
        ]
        self.startup_keywords = ["founder", "ceo", "cto"]

    async def discover_contact(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Attempts to enrich row with contact data.
        Returns the updated row dict.
        """
        company = row.get("company", "")
        role_title = row.get("role_title", "")
        
        # Determine keywords to check
        keywords_to_check = list(self.priority_keywords)
        
        # Startup check (heuristic based on company name or if size is known)
        # We don't have company_size in row, so we might just append startup keywords as a last resort
        keywords_to_check.append(self.startup_keywords)
        
        contact_data = None
        
        for keywords in keywords_to_check:
            try:
                contact_data = await self.hunter.find_contact(company, keywords)
                if contact_data:
                    break
            except Exception as e:
                # Quota exhausted or other fatal error bubbles up
                raise

        # If we got a contact, verify it
        if contact_data:
            contact_email = contact_data.get("contact_email")
            if contact_email:
                # Filter out personal emails
                personal_domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
                domain = contact_email.split("@")[1].lower() if "@" in contact_email else ""
                
                if domain in personal_domains:
                    contact_data["contact_email"] = None
                    contact_data["email_verified"] = False
                    row["notes"] = row.get("notes", "") + " Filtered out personal email."
                else:
                    is_verified = await self.verifier.verify(contact_email)
                    contact_data["email_verified"] = is_verified
            else:
                # We have a name but no email. Use PatternProvider.
                name = contact_data.get("contact_name")
                if name:
                    inferred_email = self.pattern_provider.generate_email(name, company)
                    contact_data["contact_email"] = inferred_email
                    contact_data["email_verified"] = False
                    row["notes"] = row.get("notes", "") + " Email is pattern-guessed, verify manually."

            # Update row with contact data
            row.update({
                "contact_name": contact_data.get("contact_name"),
                "contact_role": contact_data.get("contact_role"),
                "contact_email": contact_data.get("contact_email"),
                "email_verified": contact_data.get("email_verified", False)
            })
        else:
            row["notes"] = row.get("notes", "") + " skill_gap: No contact found."
            
        # Always populate linkedin search url
        row["contact_linkedin"] = LinkedInSearch.generate_search_url(company, "recruiter")
        
        # Status always goes to CONTENT_GENERATION
        row["status"] = "CONTENT_GENERATION"
        
        return row

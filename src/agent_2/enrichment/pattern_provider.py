from typing import Optional, List, Dict, Any

from src.agent_2.enrichment.base import ContactEnrichmentProvider

class PatternProvider(ContactEnrichmentProvider):
    """
    Generates likely email patterns based on company domain and contact name.
    """

    async def find_contact(self, company: str, role_keywords: List[str]) -> Optional[Dict[str, Any]]:
        # Pattern provider cannot find a contact from scratch, it's used as a fallback
        # when we already have a name but no email. 
        # Since the interface is find_contact, if called directly it returns None.
        return None
        
    def generate_email(self, name: str, domain: str) -> str:
        """
        Generates the most likely email pattern: firstname@company.com
        For a more complex implementation, we could return a list to test against MX.
        """
        parts = name.strip().lower().split()
        if not parts:
            return ""
            
        first_name = parts[0]
        # Clean up domain
        clean_domain = domain.lower().replace(" ", "")
        if "." not in clean_domain:
            clean_domain = clean_domain + ".com"
            
        return f"{first_name}@{clean_domain}"

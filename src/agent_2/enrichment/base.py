from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

class ContactEnrichmentProvider(ABC):
    """Abstract base class for all contact enrichment providers."""
    
    @abstractmethod
    async def find_contact(self, company: str, role_keywords: List[str]) -> Optional[Dict[str, Any]]:
        """
        Attempts to find a contact at the given company matching the role keywords.
        
        Returns dict with keys (or None if no contact found):
        {
          "contact_name": str,
          "contact_role": str,
          "contact_email": str | None,
          "contact_linkedin": str | None,
          "email_verified": bool,
          "source": str,
          "confidence": float
        }
        """
        pass

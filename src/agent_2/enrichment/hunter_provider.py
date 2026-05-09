import os
from typing import Optional, List, Dict, Any

from src.agent_2.enrichment.base import ContactEnrichmentProvider
from src.shared.run_logger import RunLogger
from src.agent_2.retry import RetryPolicy


class HunterProvider(ContactEnrichmentProvider):
    """
    Hunter.io API integration for discovering contacts.
    """
    
    def __init__(self, logger: RunLogger, retry_policy: RetryPolicy):
        self.logger = logger
        self.retry_policy = retry_policy
        self.api_key = os.environ.get("HUNTER_IO_API_KEY")
        self.base_url = "https://api.hunter.io/v2/domain-search"

    async def find_contact(self, company: str, role_keywords: List[str]) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            self.logger.record_error("hunter_provider", "find_contact", "HUNTER_IO_API_KEY not set. Skipping.")
            return None
            
        import httpx
        
        # Clean company name to guess domain if it's not a url
        # For a robust implementation, we might extract the domain from job_url,
        # but here we'll pass company directly to hunter and let it try its best,
        # or construct a generic domain. We'll use the company name as domain for now, 
        # stripping spaces.
        domain = company.lower().replace(" ", "") + ".com"
        if "." in company:
            domain = company
            
        params = {
            "domain": domain,
            "api_key": self.api_key,
            "limit": 10
        }
        
        async def _make_request():
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                return response.json()
                
        try:
            data = await self.retry_policy.execute_with_retry(_make_request)
            
            # Extract emails
            emails = data.get("data", {}).get("emails", [])
            if not emails:
                return None
                
            # Filter by role_keywords
            for email_data in emails:
                position = str(email_data.get("position", "")).lower()
                
                # Check if position matches any keyword
                if any(keyword.lower() in position for keyword in role_keywords):
                    first_name = email_data.get("first_name", "")
                    last_name = email_data.get("last_name", "")
                    name = f"{first_name} {last_name}".strip()
                    
                    return {
                        "contact_name": name,
                        "contact_role": email_data.get("position"),
                        "contact_email": email_data.get("value"),
                        "contact_linkedin": email_data.get("linkedin"),
                        "email_verified": False, # Will verify later via MX
                        "source": "hunter",
                        "confidence": email_data.get("confidence", 50) / 100.0
                    }
                    
            return None
        except httpx.HTTPStatusError as exc:
            # Re-raised from retry_policy if non-retryable or max attempts hit
            if exc.response.status_code == 429:
                self.logger.record_error("hunter_provider", "find_contact", "Hunter.io quota exhausted (429).")
                raise # Let pipeline handle quota exhausted
            return None
        except Exception as exc:
            self.logger.record_error("hunter_provider", "find_contact", f"Error querying Hunter: {exc}")
            return None

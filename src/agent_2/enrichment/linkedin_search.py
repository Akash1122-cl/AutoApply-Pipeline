import urllib.parse

class LinkedInSearch:
    """Generates LinkedIn search URLs for manual discovery fallback."""
    
    @staticmethod
    def generate_search_url(company: str, role: str) -> str:
        """
        Construct LinkedIn search URLs.
        Pattern: https://www.linkedin.com/search/results/people/?keywords={role}+{company}
        """
        query = f"{role} {company}"
        encoded_query = urllib.parse.quote(query)
        return f"https://www.linkedin.com/search/results/people/?keywords={encoded_query}"

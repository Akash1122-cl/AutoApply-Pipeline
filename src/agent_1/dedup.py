import urllib.parse
from typing import Dict, Any, List, Set, Tuple

def deduplicate_jobs(
    jobs: List[Dict[str, Any]], 
    existing_keys: Set[Tuple[str, str, str]]
) -> List[Dict[str, Any]]:
    """
    Removes duplicates from a list of jobs, checking against existing keys
    as well as internal duplicates within the new list itself.
    """
    deduplicated = []
    seen = set(existing_keys) # Copy so we can add to it while processing
    
    for job in jobs:
        company = str(job.get("company", "")).strip().lower()
        role_title = str(job.get("role_title", "")).strip().lower()
        
        # Strip URL query parameters for more robust deduplication
        raw_url = str(job.get("job_url", "")).strip().lower()
        parsed_url = urllib.parse.urlparse(raw_url)
        job_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        
        key = (company, role_title, job_url)
        if key not in seen:
            seen.add(key)
            deduplicated.append(job)
            
    return deduplicated

from typing import Dict, Any

def classify_region_and_work_mode(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes the region and work mode into standard taxonomies.
    In Phase 2, this uses simple heuristics.
    """
    
    # Normalize Work Mode
    raw_mode = str(job.get("work_mode", "")).lower()
    if "remote" in raw_mode:
        job["work_mode"] = "remote"
    elif "hybrid" in raw_mode:
        job["work_mode"] = "hybrid"
    else:
        job["work_mode"] = "onsite"
        
    # Normalize Region
    raw_region = str(job.get("region", "")).lower()
    if "india" in raw_region or "blr" in raw_region or "bangalore" in raw_region:
        job["region"] = "India"
        job["work_permit_required"] = False
    elif "germany" in raw_region or "uk" in raw_region or "europe" in raw_region or "berlin" in raw_region or "emea" in raw_region:
        job["region"] = "Europe"
        # If it's Europe, assume work permit required unless stated otherwise
        job.setdefault("work_permit_required", True) 
    else:
        job["region"] = "Other"
        job.setdefault("work_permit_required", True)
        
    return job

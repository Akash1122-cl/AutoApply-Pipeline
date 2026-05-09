from typing import Dict, Any, List
import json
import os

# Load user skills from config file
def load_user_skills():
    """Load user skills from config file."""
    config_path = os.path.join(os.path.dirname(__file__), "../../config/user_skills.json")
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            return set(config.get("core_skills", []))
    except (FileNotFoundError, json.JSONDecodeError):
        # Fallback to default APM skills if config not found
        return {"agile", "sql", "jira", "user research", "python", "data analysis", "a/b testing", "roadmap", "strategy"}

CORE_APM_SKILLS = load_user_skills()

def calculate_fit_score(job: Dict[str, Any]) -> int:
    """
    Calculates a fit score (0-100) based on required skills vs core APM skills.
    In a real scenario, this would use an LLM or more sophisticated ML model.
    """
    required_skills: List[str] = job.get("required_skills", [])
    if not required_skills:
        return 50 # Neutral default if no skills specified
        
    matches = 0
    for skill in required_skills:
        if skill.lower() in CORE_APM_SKILLS:
            matches += 1
            
    # Simple heuristic:
    # 0 matches = 30
    # 1 match = 50
    # 2 matches = 70
    # 3+ matches = 90
    # +10 bonus for "Associate Product Manager" exact title match
    
    base_score = 30
    if matches == 1:
        base_score = 50
    elif matches == 2:
        base_score = 70
    elif matches >= 3:
        base_score = 90
        
    role_title = str(job.get("role_title", "")).lower()
    if "associate product manager" in role_title or role_title == "apm":
        base_score += 10
        
    return min(100, base_score)

def score_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for job in jobs:
        score = calculate_fit_score(job)
        job["score"] = score
    return jobs

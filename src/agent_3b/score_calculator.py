from src.agent_3b.ats_constants import ATS_PASS_THRESHOLD

class ATSScoreCalculator:
    """Calculates the final ATS score based on rule checks and LLM checks."""
    
    def calculate_score(self, structural_results: dict, keyword_results: dict) -> dict:
        structural_passed = structural_results["passed_count"]
        
        keyword_passed = (
            (1 if keyword_results["keyword_coverage_pass"] else 0) +
            (1 if keyword_results["bullet_quality_pass"] else 0)
        )
        
        total_passed = structural_passed + keyword_passed
        total_checks = structural_results["total_count"] + 2  # +2 for keyword + bullet
        
        score = (total_passed / total_checks) * 100
        
        return {
            "ats_score": round(score, 1),
            "ats_pass": score >= ATS_PASS_THRESHOLD,
            "checks_passed": total_passed,
            "total_checks": total_checks,
            "structural_passed": structural_passed,
            "keyword_quality_passed": keyword_passed
        }

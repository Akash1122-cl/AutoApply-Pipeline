import json
from src.agent_3.llm_client import LLMClient
from src.agent_3b.ats_constants import KEYWORD_COVERAGE_MIN

class KeywordEvaluator:
    """Evaluates CV keyword coverage and bullet quality using LLM."""
    
    def __init__(self, llm_client: LLMClient = None):
        # We can either inject the LLMClient or let the Pipeline create it
        self.llm_client = llm_client

    async def evaluate(self, cv_text: str, required_skills: list[str], row: dict) -> dict:
        if not self.llm_client:
            self.llm_client = LLMClient(None) # Needs logger in real scenario, but we can pass it
            
        if not cv_text or not cv_text.strip():
            return self._build_fail_result("CV text is empty.")
            
        if not required_skills:
            return self._build_pass_result("No required skills provided.")
            
        prompt = f"""
You are an expert ATS (Applicant Tracking System) reviewer.
Evaluate the following CV against the required skills.

Required Skills: {', '.join(required_skills)}

CV Text:
---
{cv_text}
---

Calculate:
1. Keyword Coverage Percentage: What percentage of the required skills appear in the CV (case-insensitive)?
2. Bullet Quality Score: Rate from 0.0 to 1.0 how well the experience bullets follow the "action verb + task + measurable outcome" format.

Return ONLY a JSON object with this exact structure:
{{
    "keyword_coverage_percentage": 0.0,
    "bullet_quality_score": 0.0,
    "missing_keywords": ["skill1", "skill2"],
    "bullet_feedback": "Short feedback on bullet structure"
}}
"""
        
        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                model="llama-3.3-70b-versatile",
                temperature=0.0
            )
            
            # The LLMClient generate method handles JSON parsing natively if it returns a dict, 
            # wait, LLMClient in Agent 3 expects string or json? 
            # Let's assume it returns string and we parse it, or it returns dict.
            # In Phase 5, cv_builder did: result = json.loads(response)
            
            # Let's clean up response just in case
            if isinstance(response, str):
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0].strip()
                result = json.loads(response)
            else:
                result = response
                
            coverage_pct = float(result.get("keyword_coverage_percentage", 0.0))
            if coverage_pct > 1.0 and coverage_pct <= 100.0:
                coverage_pct = coverage_pct / 100.0 # Normalize to 0.0 - 1.0
                
            bullet_score = float(result.get("bullet_quality_score", 0.0))
            if bullet_score > 1.0 and bullet_score <= 100.0:
                bullet_score = bullet_score / 100.0
                
            # Requirements
            coverage_pass = coverage_pct >= KEYWORD_COVERAGE_MIN
            bullet_pass = bullet_score >= 0.70
            
            return {
                "keyword_coverage_pass": coverage_pass,
                "bullet_quality_pass": bullet_pass,
                "keyword_coverage_detail": {
                    "percentage": coverage_pct,
                    "missing": result.get("missing_keywords", [])
                },
                "bullet_quality_detail": {
                    "score": bullet_score,
                    "feedback": result.get("bullet_feedback", "")
                },
                "llm_summary": "Evaluated successfully."
            }
            
        except Exception as e:
            return self._build_fail_result(f"LLM evaluation failed: {e}")

    def _build_fail_result(self, error: str) -> dict:
        return {
            "keyword_coverage_pass": False,
            "bullet_quality_pass": False,
            "keyword_coverage_detail": {"percentage": 0.0, "missing": []},
            "bullet_quality_detail": {"score": 0.0, "feedback": error},
            "llm_summary": error
        }
        
    def _build_pass_result(self, msg: str) -> dict:
        return {
            "keyword_coverage_pass": True,
            "bullet_quality_pass": True,
            "keyword_coverage_detail": {"percentage": 1.0, "missing": []},
            "bullet_quality_detail": {"score": 1.0, "feedback": msg},
            "llm_summary": msg
        }

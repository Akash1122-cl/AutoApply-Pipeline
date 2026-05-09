import json
import asyncio
from datetime import datetime, timezone, timedelta

from src.shared.run_logger import RunLogger
from src.agent_3.llm_client import LLMClient
from src.agent_3b.cv_text_extractor import CVTextExtractor
from src.agent_3b.structural_checks import StructuralChecker
from src.agent_3b.keyword_evaluator import KeywordEvaluator
from src.agent_3b.score_calculator import ATSScoreCalculator
from src.agent_3b.feedback_formatter import FeedbackFormatter


def _recently_reviewed(attempted_at_iso: str, window_minutes: int = 60) -> bool:
    """Returns True if the row was reviewed within the last window_minutes."""
    try:
        attempted = datetime.fromisoformat(attempted_at_iso.replace("Z", "+00:00"))
        now = datetime.now(tz=timezone.utc)
        return (now - attempted) < timedelta(minutes=window_minutes)
    except Exception:
        return False


class ATSReviewAgent:
    """
    Phase 7 Agent 3b: Evaluates CV readiness for ATS systems.

    Runs 9 structural rule-based checks + 2 LLM-based checks
    (keyword coverage and bullet quality) then scores as:
        ats_score = (checks_passed / 11) * 100

    Score >= 80 → pass. Otherwise → actionable feedback for regeneration.
    """

    def __init__(self, logger: RunLogger):
        self.logger = logger
        self.llm_client = LLMClient(logger)

    async def review_cv(self, row: dict) -> dict | None:
        """
        Reviews the CV referenced in `row['cv_doc_link']`.
        Returns a result dict, or None if skipped (idempotency).
        """
        job_id = row.get("job_id", "unknown")

        # ── 1. Idempotency guard ─────────────────────────────────────────────
        if row.get("ats_score") is not None and row.get("ats_review_attempted_at"):
            if _recently_reviewed(row["ats_review_attempted_at"]):
                if self.logger:
                    self.logger.record_error(
                        job_id, "ats_review", "Skipped — reviewed within last 60 min"
                    )
                return None

        # ── 2. Extract CV text ───────────────────────────────────────────────
        cv_doc_link = row.get("cv_doc_link", "")
        extractor = CVTextExtractor()
        cv_data = await extractor.extract_text(cv_doc_link)

        if not cv_data["extraction_success"]:
            return {
                "status": "FAILED",
                "error": cv_data.get("extraction_error", "Unknown extraction error"),
                "ats_score": 0,
                "ats_pass": False,
                "ats_review_attempted_at": datetime.now(tz=timezone.utc).isoformat(),
            }

        # ── 3. Structural checks (9 rule-based) ─────────────────────────────
        checker = StructuralChecker()
        structural_results = checker.run_all_checks(cv_data, row)

        # ── 4. Keyword + bullet quality checks (2 LLM-based) ────────────────
        raw_skills = row.get("required_skills", "[]")
        try:
            required_skills = (
                json.loads(raw_skills) if isinstance(raw_skills, str) else raw_skills
            )
        except (json.JSONDecodeError, TypeError):
            required_skills = []

        evaluator = KeywordEvaluator(llm_client=self.llm_client)
        keyword_results = await evaluator.evaluate(
            cv_data["raw_text"], required_skills, row
        )

        # ── 5. Score ─────────────────────────────────────────────────────────
        calculator = ATSScoreCalculator()
        score_result = calculator.calculate_score(structural_results, keyword_results)

        # ── 6. Feedback if failed ────────────────────────────────────────────
        feedback = None
        if not score_result["ats_pass"]:
            formatter = FeedbackFormatter()
            feedback = formatter.format_for_regeneration(
                structural_results,
                keyword_results,
                row.get("revision_count", 0),
            )

        if self.logger:
            self.logger.record_error(
                job_id,
                "ats_review",
                f"Score={score_result['ats_score']} pass={score_result['ats_pass']} "
                f"checks={score_result['checks_passed']}/{score_result['total_checks']}",
            )

        return {
            "ats_score": score_result["ats_score"],
            "ats_pass": score_result["ats_pass"],
            "checks_passed": score_result["checks_passed"],
            "total_checks": score_result["total_checks"],
            "structural_results": structural_results,
            "keyword_results": keyword_results,
            "feedback": feedback,
            "ats_review_attempted_at": datetime.now(tz=timezone.utc).isoformat(),
        }

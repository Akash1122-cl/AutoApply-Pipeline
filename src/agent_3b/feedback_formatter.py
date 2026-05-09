from src.agent_3b.ats_constants import MAX_ATS_REVISIONS


class FeedbackFormatter:
    """Formats ATS check failures into actionable feedback for Agent 3 regeneration."""

    def format_for_regeneration(
        self,
        structural_results: dict,
        keyword_results: dict,
        revision_count: int,
    ) -> str:
        attempt_num = revision_count + 1
        lines = [
            f"[ATS Revision Feedback — Attempt {attempt_num}/{MAX_ATS_REVISIONS}]",
            "The CV failed the ATS quality gate. Specific issues to fix:",
            "",
        ]

        # Structural failures
        failures = structural_results.get("failures", [])
        if failures:
            lines.append("== Structural Fixes Required ==")
            for name, msg in failures:
                lines.append(f"  • [{name}] {msg}")
            lines.append("")

        # Keyword coverage
        kw_detail = keyword_results.get("keyword_coverage_detail", {})
        if not keyword_results.get("keyword_coverage_pass"):
            pct = kw_detail.get("percentage", 0.0)
            missing = kw_detail.get("missing", [])
            lines.append("== Keyword Coverage Fix Required ==")
            lines.append(
                f"  • Coverage is {pct * 100:.0f}% — target is 60%."
            )
            if missing:
                lines.append(
                    f"  • Missing keywords to incorporate: {', '.join(missing)}"
                )
            lines.append("")

        # Bullet quality
        bq_detail = keyword_results.get("bullet_quality_detail", {})
        if not keyword_results.get("bullet_quality_pass"):
            score = bq_detail.get("score", 0.0)
            feedback = bq_detail.get("feedback", "")
            lines.append("== Bullet Quality Fix Required ==")
            lines.append(
                f"  • Quality score is {score:.2f} — target is 0.70."
            )
            lines.append(
                "  • Bullets must follow: [Action Verb] + [Task] + [Measurable Outcome]"
            )
            if feedback:
                lines.append(f"  • LLM feedback: {feedback}")
            lines.append("")

        lines.append(
            "Regenerate the CV addressing ALL issues above before next ATS review."
        )
        return "\n".join(lines)

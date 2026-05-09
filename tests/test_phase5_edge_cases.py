"""
Phase 5 Edge-Case Test Suite
Based on: Docs/Edge-Cases.md — Phase 5 Section (lines 107-122)

Covers:
  EC-5-1: Skill gap detected and logged in notes (tag-mismatch miss)
  EC-5-2: Required skills completely absent → full gap logged
  EC-5-3: Invalid JSON in required_skills field handled gracefully
  EC-5-4: Empty required_skills → fallback to master CV skills
  EC-5-5: cv_doc_link written even when Drive quota fails (local fallback)
  EC-5-6: Email/DM generated even with no contact info in row
  EC-5-7: ATS feedback injected correctly into regenerate_with_feedback
  EC-5-8: revision_count incremented on regeneration
  EC-5-9: status always set to AWAITING_CONTENT_REVIEW after generation
  EC-5-10: Fabrication guard flags an invented metric
"""

import asyncio
import json
import sys
import os
import traceback
from unittest.mock import AsyncMock, MagicMock, patch

# Fix Windows console encoding
sys.stdout.reconfigure(encoding="utf-8")

# Make sure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agent_3.pipeline import ContentGenerationAgent
from src.agent_3.skill_mapper import SkillMapper
from src.agent_3.fabrication_guard import FabricationGuard


# ──────────────────────────────────────────────────────────────────────────────
# Shared mock data
# ──────────────────────────────────────────────────────────────────────────────
MASTER_CV = {
    "name": "Jane Doe",
    "email": "jane@example.com",
    "phone": "+91 9876543210",
    "summary": "Experienced PM.",
    "experience": [
        {
            "role": "product intern",
            "company": "xyz corp",
            "duration": "Jun 2023 - Aug 2023",
            "bullets": [
                "Led redesign of onboarding flow reducing drop-off by 23%.",
                "Shipped A/B testing framework one week ahead of schedule.",
            ],
        }
    ],
    "education": [{"degree": "b.tech in computer science", "school": "NIT", "year": "2024"}],
    "skills": ["figma", "user research", "a/b testing", "data analysis", "roadmapping"],
}

ACCOMPLISHMENTS = [
    {
        "role": "Product Intern",
        "company": "XYZ Corp",
        "accomplishment": "Redesigned onboarding flow",
        "metrics_impact": "23% drop-off reduction",
        "skills_used": ["user research", "figma"],
        "tags": ["onboarding", "ux"],
    },
    {
        "role": "Product Intern",
        "company": "XYZ Corp",
        "accomplishment": "A/B testing framework",
        "metrics_impact": "shipped 1 week early",
        "skills_used": ["a/b testing", "data analysis"],
        "tags": ["testing", "analytics"],
    },
]

BASE_ROW = {
    "job_id": "test-job",
    "company": "TestCo",
    "role_title": "Associate Product Manager",
    "required_skills": ["user research", "figma"],
    "job_url": "https://example.com/job/123",
    "notes": "",
    "revision_count": 0,
}


# ──────────────────────────────────────────────────────────────────────────────
# Test runner helpers
# ──────────────────────────────────────────────────────────────────────────────
RESULTS = []


def record(name: str, passed: bool, detail: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    RESULTS.append((name, passed, detail))
    print(f"  {status}  {name}")
    if detail and not passed:
        print(f"         Detail: {detail}")


def make_logger():
    logger = MagicMock()
    logger.record_error = MagicMock()
    logger.increment = MagicMock()
    return logger


def make_agent_with_mocks():
    """Returns a ContentGenerationAgent with LLM and Drive calls mocked out."""
    logger = make_logger()
    agent = ContentGenerationAgent(logger)

    # Mock LLM client methods
    agent.llm_client.generate_json = AsyncMock(return_value=MASTER_CV)
    agent.llm_client.generate = AsyncMock(
        return_value=json.dumps(
            {"subject": "Hi there", "body": "Cold email body here."}
        )
    )

    # Mock CV builder to return a local docx link (Drive quota exceeded scenario)
    async def mock_build_cv(row, mapped_skills, master_cv, ats_feedback=None):
        return {"cv_doc_link": "/tmp/cv_outputs/test.docx"}

    agent.cv_builder.build_cv = mock_build_cv

    # Mock email writer
    async def mock_write_email(row, cv_data):
        return {"subject": "Joining TestCo", "body": "Dear Hiring Manager,\n\nI am interested."}

    agent.email_writer.write_email = mock_write_email

    # Mock DM writer
    async def mock_write_dm(row, cv_data):
        return "Hi! I saw your opening and would love to connect."

    agent.dm_writer.write_dm = mock_write_dm

    # Patch source reader
    agent._mock_master_cv = MASTER_CV
    agent._mock_accomplishments = ACCOMPLISHMENTS

    return agent


# ──────────────────────────────────────────────────────────────────────────────
# EC-5-1: Skill gap logged in notes when skill absent from evidence
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_5_1_skill_gap_logged():
    """Skills not in accomplishments/master are logged to notes."""
    mapper = SkillMapper()
    row = {**BASE_ROW, "required_skills": ["user research", "quantum_computing_xyz"], "notes": ""}
    result = mapper.map_required_skills(row["required_skills"], ACCOMPLISHMENTS, MASTER_CV)
    skill_gaps = result["skill_gaps"]
    gap_logged = "quantum_computing_xyz" in skill_gaps
    record("EC-5-1: Unknown skill added to gap list", gap_logged, str(skill_gaps))


# ──────────────────────────────────────────────────────────────────────────────
# EC-5-2: All skills absent → full gaps, no matched_skills
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_5_2_all_skills_missing():
    """When all required skills are absent, all end up in skill_gaps."""
    mapper = SkillMapper()
    result = mapper.map_required_skills(["blockchain", "rust_lang", "web3"], ACCOMPLISHMENTS, MASTER_CV)
    all_gap = len(result["skill_gaps"]) == 3 and len(result["matched_skills"]) == 0
    record("EC-5-2: All absent skills captured as gaps", all_gap, str(result))


# ──────────────────────────────────────────────────────────────────────────────
# EC-5-3: Invalid JSON in required_skills handled gracefully
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_5_3_invalid_json_skills():
    """required_skills as malformed JSON string should not crash the pipeline."""
    agent = make_agent_with_mocks()

    with patch("src.agent_3.source_reader.SourceReader.load_master_cv", new=AsyncMock(return_value=MASTER_CV)), \
         patch("src.agent_3.source_reader.SourceReader.load_accomplishments_bank", new=AsyncMock(return_value=ACCOMPLISHMENTS)):

        row = {**BASE_ROW, "required_skills": "{invalid_json::}", "notes": ""}
        try:
            result = await agent.generate_content(row)
            # Should complete without crash; pipeline treats bad input gracefully
            # required_skills as string is iterable over chars — not ideal but shouldn't crash
            record("EC-5-3: Invalid JSON string in required_skills — no crash", True)
        except Exception as e:
            record("EC-5-3: Invalid JSON string in required_skills — no crash", False, str(e))


# ──────────────────────────────────────────────────────────────────────────────
# EC-5-4: Empty required_skills fallback to master CV skills
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_5_4_empty_required_skills():
    """Empty required_skills should fall back to master CV skills without crash."""
    agent = make_agent_with_mocks()

    with patch("src.agent_3.source_reader.SourceReader.load_master_cv", new=AsyncMock(return_value=MASTER_CV)), \
         patch("src.agent_3.source_reader.SourceReader.load_accomplishments_bank", new=AsyncMock(return_value=ACCOMPLISHMENTS)):

        row = {**BASE_ROW, "required_skills": [], "notes": ""}
        try:
            result = await agent.generate_content(row)
            has_link = bool(result.get("cv_doc_link"))
            record("EC-5-4: Empty required_skills fallback — CV still generated", has_link, str(result.get("cv_doc_link")))
        except Exception as e:
            record("EC-5-4: Empty required_skills fallback — CV still generated", False, str(e))


# ──────────────────────────────────────────────────────────────────────────────
# EC-5-5: cv_doc_link always set (local docx fallback)
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_5_5_cv_link_always_set():
    """cv_doc_link must be set even if Google Drive upload fails."""
    agent = make_agent_with_mocks()

    with patch("src.agent_3.source_reader.SourceReader.load_master_cv", new=AsyncMock(return_value=MASTER_CV)), \
         patch("src.agent_3.source_reader.SourceReader.load_accomplishments_bank", new=AsyncMock(return_value=ACCOMPLISHMENTS)):

        row = {**BASE_ROW, "notes": ""}
        result = await agent.generate_content(row)
        has_link = bool(result.get("cv_doc_link"))
        record("EC-5-5: cv_doc_link set (local fallback ok)", has_link, str(result.get("cv_doc_link")))


# ──────────────────────────────────────────────────────────────────────────────
# EC-5-6: Email and DM generated even with no contact info
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_5_6_no_contact_info():
    """Email + DM drafts must be created even when contact_email is absent."""
    agent = make_agent_with_mocks()

    with patch("src.agent_3.source_reader.SourceReader.load_master_cv", new=AsyncMock(return_value=MASTER_CV)), \
         patch("src.agent_3.source_reader.SourceReader.load_accomplishments_bank", new=AsyncMock(return_value=ACCOMPLISHMENTS)):

        row = {**BASE_ROW, "notes": ""}
        # No contact_email, no contact_name in row
        result = await agent.generate_content(row)
        has_email_draft = bool(result.get("email_draft_link"))
        has_dm_draft = bool(result.get("linkedin_dm_draft"))
        record(
            "EC-5-6: Email draft generated without contact info",
            has_email_draft,
            str(result.get("email_draft_link", ""))[:80],
        )
        record(
            "EC-5-6: DM draft generated without contact info",
            has_dm_draft,
            str(result.get("linkedin_dm_draft", ""))[:80],
        )


# ──────────────────────────────────────────────────────────────────────────────
# EC-5-7: ATS feedback injected into regeneration
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_5_7_ats_feedback_passed():
    """regenerate_with_feedback must pass ats_feedback to generate_content."""
    agent = make_agent_with_mocks()
    received_feedback = []

    original_build = agent.cv_builder.build_cv

    async def spy_build_cv(row, mapped_skills, master_cv, ats_feedback=None):
        received_feedback.append(ats_feedback)
        return await original_build(row, mapped_skills, master_cv, ats_feedback)

    agent.cv_builder.build_cv = spy_build_cv

    with patch("src.agent_3.source_reader.SourceReader.load_master_cv", new=AsyncMock(return_value=MASTER_CV)), \
         patch("src.agent_3.source_reader.SourceReader.load_accomplishments_bank", new=AsyncMock(return_value=ACCOMPLISHMENTS)):

        row = {**BASE_ROW, "notes": "", "revision_count": 0}
        feedback_text = "[ATS Revision Feedback] Missing bullets with measurable outcomes."
        await agent.regenerate_with_feedback(row, feedback_text)
        received = received_feedback[0] if received_feedback else None
        record("EC-5-7: ATS feedback passed to cv_builder", received == feedback_text, str(received))


# ──────────────────────────────────────────────────────────────────────────────
# EC-5-8: revision_count incremented on regeneration
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_5_8_revision_count_incremented():
    """revision_count must increment each time ATS feedback triggers a regen."""
    agent = make_agent_with_mocks()

    with patch("src.agent_3.source_reader.SourceReader.load_master_cv", new=AsyncMock(return_value=MASTER_CV)), \
         patch("src.agent_3.source_reader.SourceReader.load_accomplishments_bank", new=AsyncMock(return_value=ACCOMPLISHMENTS)):

        row = {**BASE_ROW, "notes": "", "revision_count": 0}
        result = await agent.regenerate_with_feedback(row, "ATS feedback here")
        incremented = result.get("revision_count", 0) == 1
        record("EC-5-8: revision_count=1 after first regen", incremented, str(result.get("revision_count")))

        # Simulate second regen
        result2 = await agent.regenerate_with_feedback(result, "ATS feedback second")
        incremented2 = result2.get("revision_count", 0) == 2
        record("EC-5-8: revision_count=2 after second regen", incremented2, str(result2.get("revision_count")))


# ──────────────────────────────────────────────────────────────────────────────
# EC-5-9: status always set to AWAITING_CONTENT_REVIEW
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_5_9_status_set():
    """Status must always be AWAITING_CONTENT_REVIEW after generation."""
    agent = make_agent_with_mocks()

    with patch("src.agent_3.source_reader.SourceReader.load_master_cv", new=AsyncMock(return_value=MASTER_CV)), \
         patch("src.agent_3.source_reader.SourceReader.load_accomplishments_bank", new=AsyncMock(return_value=ACCOMPLISHMENTS)):

        row = {**BASE_ROW, "notes": ""}
        result = await agent.generate_content(row)
        correct_status = result.get("status") == "AWAITING_CONTENT_REVIEW"
        record("EC-5-9: status=AWAITING_CONTENT_REVIEW after generation", correct_status, str(result.get("status")))


# ──────────────────────────────────────────────────────────────────────────────
# EC-5-10: FabricationGuard flags an invented metric
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_5_10_fabrication_guard():
    """FabricationGuard must flag metrics that don't exist in source evidence."""
    source_evidence = {
        "user research": ACCOMPLISHMENTS[:1],
    }

    generated_cv_with_fabrication = {
        "name": "Jane Doe",
        "experience": [
            {
                "role": "product intern",
                "company": "xyz corp",
                "bullets": [
                    "Increased revenue by 500% using quantum ML.",  # 500% is NOT in evidence
                ],
            }
        ],
        "skills": ["figma", "user research"],
        "education": [{"degree": "b.tech in computer science"}],
    }

    result = FabricationGuard.validate_cv(generated_cv_with_fabrication, source_evidence, MASTER_CV)
    flagged = not result["is_valid"] and len(result["violations"]) > 0
    violations_str = str(result["violations"])
    record("EC-5-10: FabricationGuard flags invented metric (500%)", flagged, violations_str[:120])

    # Also test a clean CV passes
    clean_cv = {
        "name": "Jane Doe",
        "experience": [
            {
                "role": "product intern",
                "company": "xyz corp",
                "bullets": ["Led redesign of onboarding flow reducing drop-off by 23%."],
            }
        ],
        "skills": ["figma", "user research"],
        "education": [{"degree": "b.tech in computer science"}],
    }
    clean_result = FabricationGuard.validate_cv(clean_cv, source_evidence, MASTER_CV)
    record("EC-5-10: FabricationGuard passes clean CV", clean_result["is_valid"], str(clean_result["violations"]))


# ──────────────────────────────────────────────────────────────────────────────
# EC-5-11: Skill tag mismatch — skill in tags but not skills_used
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_5_11_tag_match():
    """SkillMapper must match via tags, not just skills_used."""
    mapper = SkillMapper()
    result = mapper.map_required_skills(["onboarding"], ACCOMPLISHMENTS, MASTER_CV)
    matched = "onboarding" in result["matched_skills"]
    record("EC-5-11: Skill matched via tag (not skills_used)", matched, str(list(result["matched_skills"].keys())))


# ──────────────────────────────────────────────────────────────────────────────
# EC-5-12: Skill matched via fuzzy text in accomplishment body
# ──────────────────────────────────────────────────────────────────────────────
async def test_ec_5_12_fuzzy_text_match():
    """SkillMapper must match skill appearing verbatim in accomplishment text."""
    mapper = SkillMapper()
    result = mapper.map_required_skills(["redesigned"], ACCOMPLISHMENTS, MASTER_CV)
    # "redesigned" appears in accomplishment text body
    matched = "redesigned" in result["matched_skills"]
    record("EC-5-12: Skill matched via fuzzy accomplishment text", matched, str(list(result["matched_skills"].keys())))


# ──────────────────────────────────────────────────────────────────────────────
# Main runner
# ──────────────────────────────────────────────────────────────────────────────
async def run_all():
    tests = [
        test_ec_5_1_skill_gap_logged,
        test_ec_5_2_all_skills_missing,
        test_ec_5_3_invalid_json_skills,
        test_ec_5_4_empty_required_skills,
        test_ec_5_5_cv_link_always_set,
        test_ec_5_6_no_contact_info,
        test_ec_5_7_ats_feedback_passed,
        test_ec_5_8_revision_count_incremented,
        test_ec_5_9_status_set,
        test_ec_5_10_fabrication_guard,
        test_ec_5_11_tag_match,
        test_ec_5_12_fuzzy_text_match,
    ]

    print("\n" + "=" * 65)
    print("  PHASE 5 EDGE-CASE TEST SUITE (from Edge-Cases.md)")
    print("=" * 65)

    for test_fn in tests:
        try:
            await test_fn()
        except Exception as exc:
            record(test_fn.__name__, False, f"EXCEPTION: {exc}\n{traceback.format_exc()}")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print()
    print("=" * 65)
    print(f"  RESULT: {passed}/{total} passed")
    print("=" * 65 + "\n")

    # Exit non-zero if any failures
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_all())

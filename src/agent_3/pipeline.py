import json
from typing import Dict, Any

from src.shared.run_logger import RunLogger
from src.agent_3.llm_client import LLMClient
from src.agent_3.source_reader import SourceReader
from src.agent_3.skill_mapper import SkillMapper
from src.agent_3.cv_builder import CVBuilder
from src.agent_3.email_writer import EmailWriter
from src.agent_3.dm_writer import DMWriter
from src.agent_3.fabrication_guard import FabricationError

class ContentGenerationAgent:
    """Main pipeline for Phase 5 Content Generation."""
    
    def __init__(self, logger: RunLogger):
        self.logger = logger
        self.llm_client = LLMClient(logger)
        self.skill_mapper = SkillMapper()
        self.cv_builder = CVBuilder(self.llm_client)
        self.email_writer = EmailWriter(self.llm_client)
        self.dm_writer = DMWriter(self.llm_client)

    async def generate_content(self, row: Dict[str, Any], ats_feedback: str = None) -> Dict[str, Any]:
        """
        Attempts to generate CV, email, and DM for the given row.
        Returns the updated row dict.
        """
        # 1. Load Master CV and Accomplishments Bank
        master_cv = await SourceReader.load_master_cv(self.llm_client)
        accomplishments = await SourceReader.load_accomplishments_bank()
        
        # 2. Map required skills
        required_skills = row.get("required_skills", [])
        if not required_skills:
            # If no skills provided, fallback to master skills just to have something
            required_skills = master_cv.get("skills", [])[:5]
            
        mapping_result = self.skill_mapper.map_required_skills(required_skills, accomplishments, master_cv)
        skill_gaps = mapping_result["skill_gaps"]
        mapped_skills = mapping_result["matched_skills"]
        
        # 3. Handle skill gaps
        if skill_gaps:
            self.logger.increment("agent3_skill_gaps_detected", len(skill_gaps))
            gap_note = f" skill_gap: {', '.join(skill_gaps)}"
            row["notes"] = row.get("notes", "") + gap_note
            
        # 4. Generate CV
        cv_result = await self.cv_builder.build_cv(row, mapped_skills, master_cv, ats_feedback)
        row["cv_doc_link"] = cv_result["cv_doc_link"]
        
        # Use the tailored generated CV for email/DM (not the untailored master CV).
        # cv_builder now returns the generated_cv dict alongside the doc link.
        cv_data_for_email = cv_result.get("generated_cv", master_cv)
        
        # 5. Generate Email
        email_result = await self.email_writer.write_email(row, cv_data_for_email)
        # Store draft inline
        row["email_draft_link"] = f"Subject: {email_result['subject']}\n\n{email_result['body']}"
        
        # 6. Generate DM
        dm_result = await self.dm_writer.write_dm(row, cv_data_for_email)
        row["linkedin_dm_draft"] = dm_result
        
        # 7. Update status
        row["status"] = "AWAITING_CONTENT_REVIEW"
        
        if ats_feedback:
            row["revision_count"] = row.get("revision_count", 0) + 1
            
        return row

    async def regenerate_with_feedback(self, row: dict, ats_feedback: str) -> dict:
        return await self.generate_content(row, ats_feedback)

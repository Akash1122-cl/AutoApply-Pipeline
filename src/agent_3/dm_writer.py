from src.agent_3.llm_client import LLMClient
from src.agent_3.templates.dm_template import DM_PROMPT_TEMPLATE

class DMWriter:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    async def write_dm(self, row: dict, cv_data: dict) -> str:
        contact_name = row.get("contact_name", "Team")
        if not contact_name:
             contact_name = "Team"
             
        # Pick one top accomplishment
        top_acc = ""
        for exp in cv_data.get("experience", []):
            if exp.get("bullets"):
                top_acc = exp["bullets"][0]
                break

        prompt = DM_PROMPT_TEMPLATE.format(
            company=row.get("company", ""),
            role_title=row.get("role_title", ""),
            contact_name=contact_name,
            accomplishment=top_acc
        )
        
        response = await self.llm_client.generate(prompt, max_tokens=100)
        return response.strip()

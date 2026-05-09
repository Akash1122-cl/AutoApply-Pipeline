import json
from src.agent_3.llm_client import LLMClient
from src.agent_3.templates.email_template import EMAIL_PROMPT_TEMPLATE

class EmailWriter:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    async def write_email(self, row: dict, cv_data: dict) -> dict:
        contact_name = row.get("contact_name")
        if not contact_name:
            contact_name = "there" # "Hi there" or "Hi Team" handled
            
        # Get top 3 accomplishments from cv_data (the generated CV)
        top_accs = []
        for exp in cv_data.get("experience", []):
            top_accs.extend(exp.get("bullets", []))
            if len(top_accs) >= 3:
                break
        
        prompt = EMAIL_PROMPT_TEMPLATE.format(
            company=row.get("company", ""),
            role_title=row.get("role_title", ""),
            contact_name=contact_name,
            contact_role=row.get("contact_role", ""),
            candidate_name=cv_data.get("name", "Jane Doe"),
            accomplishments=json.dumps(top_accs[:3], indent=2)
        )
        
        response = await self.llm_client.generate(prompt, max_tokens=300)
        
        # Parse subject and body
        lines = response.strip().split("\n")
        subject = "Application"
        body_lines = []
        
        for line in lines:
            if line.lower().startswith("subject:"):
                subject = line.split(":", 1)[1].strip()
            elif line.lower().startswith("body:"):
                continue
            else:
                body_lines.append(line)
                
        body = "\n".join(body_lines).strip()
        
        return {
            "subject": subject,
            "body": body
        }

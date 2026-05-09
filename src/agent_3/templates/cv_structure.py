CV_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "email": {"type": "string"},
        "phone": {"type": "string"},
        "linkedin": {"type": "string"},
        "summary": {"type": "string"},
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string"},
                    "company": {"type": "string"},
                    "duration": {"type": "string"},
                    "bullets": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["role", "company", "duration", "bullets"]
            }
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "degree": {"type": "string"},
                    "school": {"type": "string"},
                    "year": {"type": "string"}
                },
                "required": ["degree", "school", "year"]
            }
        },
        "skills": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["name", "email", "phone", "linkedin", "summary", "experience", "education", "skills"]
}

CV_PROMPT_TEMPLATE = """
You are an elite executive resume writer. Your task is to tailor a CV for a candidate applying to a specific role.

### STRICT RULES:
1. NEVER invent or fabricate experience, companies, roles, durations, skills, or metrics.
2. You may ONLY use facts, metrics, and bullets present in the Master CV and Accomplishments Bank provided below.
3. You may reorder bullets to put the most relevant accomplishments first.
4. You may slightly rephrase bullets to naturally embed the Required Skills (JD keywords), but you MUST retain the exact metrics and core truth.
5. Do NOT add new skills to the Skills list that are not in the Master CV or Accomplishments.
6. Rewrite the Summary to mirror the role language using the provided facts.
7. Output exactly matching the required JSON schema.

### ROLE CONTEXT
Company: {company}
Role Title: {role_title}
Job Link: {job_url}
Required Skills: {required_skills}
Job Description: {job_description}

### ATS FEEDBACK (If any)
{ats_feedback}

### MASTER CV (Baseline)
{master_cv}

### MAPPED ACCOMPLISHMENTS (Highly Relevant)
{mapped_accomplishments}

Output the tailored CV as JSON.
"""

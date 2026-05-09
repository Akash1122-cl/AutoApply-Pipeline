DM_PROMPT_TEMPLATE = """
You are an expert at LinkedIn networking. Write a direct message to a hiring manager or recruiter.

### STRICT RULES:
1. Max 300 characters.
2. Direct, not salesy.
3. One line about background MUST reference a specific accomplishment provided. Do not invent metrics.
4. Do not include placeholders except the ones provided.

### FORMAT:
Hi [Contact Name] — saw [Company] is hiring an [Role]. [One relevant line about background].
Would love to connect — happy to share my CV.

### INPUTS:
Company: {company}
Role: {role_title}
Contact Name: {contact_name}
Top Accomplishment:
{accomplishment}

Output ONLY the DM text.
"""

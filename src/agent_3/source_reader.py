"""Read-only data access for Master CV and Accomplishments Bank."""

import os
import json
from src.shared.google_auth import GoogleDriveAuth
from src.agent_3.llm_client import LLMClient

class SourceReader:
    """Provides access to the user's master CV and accomplishments."""
    
    @staticmethod
    async def load_master_cv(llm_client: LLMClient = None) -> dict:
        """Loads the Master CV from PDF (if available) or Google Docs and parses it into JSON."""
        # 1. Try local PDF first (synced from Drive)
        pdf_path = os.environ.get('LOCAL_MASTER_CV_PDF', 'data/master_cv.pdf')
        if os.path.exists(pdf_path):
            try:
                import PyPDF2
                with open(pdf_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    raw_text = ""
                    for page in reader.pages:
                        raw_text += page.extract_text()
                
                print(f"INFO: Loaded Master CV from local PDF: {pdf_path}")
                if llm_client:
                    from src.agent_3.templates.cv_structure import CV_JSON_SCHEMA
                    prompt = f"Parse this raw CV text into the requested JSON schema. Extract all facts faithfully.\n\n{raw_text}"
                    parsed_json = await llm_client.generate_json(prompt, CV_JSON_SCHEMA)
                    return parsed_json
            except Exception as e:
                print(f"WARNING: Failed to parse local PDF: {e}. Falling back to Google Docs.")

        # 2. Fallback to Google Docs
        doc_id = os.environ.get('GOOGLE_MASTER_CV_DOC_ID', 'your_master_cv_doc_id')
        
        if doc_id == 'your_master_cv_doc_id' or not doc_id:
            # Fallback to mock data if not configured
            return SourceReader._get_mock_master_cv()
            
        auth = GoogleDriveAuth()
        docs_service = auth.get_docs_service()
        if not docs_service:
            return SourceReader._get_mock_master_cv()
            
        try:
            document = docs_service.documents().get(documentId=doc_id).execute()
            raw_text = SourceReader._extract_text_from_doc(document)
            
            if llm_client:
                from src.agent_3.templates.cv_structure import CV_JSON_SCHEMA
                prompt = f"Parse this raw CV text into the requested JSON schema. Extract all facts faithfully.\n\n{raw_text}"
                parsed_json = await llm_client.generate_json(prompt, CV_JSON_SCHEMA)
                return parsed_json
            else:
                return SourceReader._get_mock_master_cv()
        except Exception as e:
            print(f"Error reading Master CV from Docs: {e}")
            return SourceReader._get_mock_master_cv()

    @staticmethod
    async def load_accomplishments_bank() -> list[dict]:
        """Loads the Accomplishments Bank from Google Sheets."""
        sheet_id = os.environ.get('GOOGLE_ACCOMPLISHMENTS_SHEET_ID', 'your_accomplishments_sheet_id')
        
        if sheet_id == 'your_accomplishments_sheet_id' or not sheet_id:
            return SourceReader._get_mock_accomplishments()
            
        auth = GoogleDriveAuth()
        sheets_service = auth.get_sheets_service()
        if not sheets_service:
            return SourceReader._get_mock_accomplishments()
            
        try:
            result = sheets_service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range="A:G" # Role | Company | Duration | Accomplishment | Skills Used | Metrics/Impact | Tags
            ).execute()
            
            values = result.get('values', [])
            if not values or len(values) < 2:
                return SourceReader._get_mock_accomplishments()
                
            headers = [h.lower().strip() for h in values[0]]
            accs = []
            for row in values[1:]:
                # Pad row to match headers
                row += [''] * (len(headers) - len(row))
                row_dict = dict(zip(headers, row))
                
                acc = {
                    "role": row_dict.get("role", ""),
                    "company": row_dict.get("company", ""),
                    "duration": row_dict.get("duration", ""),
                    "accomplishment": row_dict.get("accomplishment", ""),
                    "skills_used": [s.strip() for s in row_dict.get("skills used", "").split(",") if s.strip()],
                    "metrics_impact": row_dict.get("metrics/impact", row_dict.get("metrics", "")),
                    "tags": [t.strip() for t in row_dict.get("tags", "").split(",") if t.strip()]
                }
                if acc["accomplishment"]:
                    accs.append(acc)
            return accs
        except Exception as e:
            print(f"Error reading Accomplishments from Sheets: {e}")
            return SourceReader._get_mock_accomplishments()

    @staticmethod
    def _extract_text_from_doc(document: dict) -> str:
        text = ""
        for element in document.get('body', {}).get('content', []):
            if 'paragraph' in element:
                for obj in element.get('paragraph', {}).get('elements', []):
                    if 'textRun' in obj:
                        text += obj.get('textRun', {}).get('content', '')
        return text

    @staticmethod
    def _get_mock_master_cv() -> dict:
        return {
            "name": "Jane Doe",
            "email": "jane.doe@example.com",
            "phone": "+91 9876543210",
            "linkedin": "https://linkedin.com/in/janedoe",
            "summary": "Data-driven Product Manager with experience in B2B SaaS and consumer tech. Adept at cross-functional leadership, agile methodologies, and delivering impactful features.",
            "experience": [
                {
                    "role": "Product Intern",
                    "company": "XYZ Corp",
                    "duration": "Jun 2023 - Aug 2023",
                    "bullets": [
                        "Led redesign of onboarding flow using Figma and user research.",
                        "Implemented A/B testing strategy that decreased drop-off rate by 23%.",
                        "Collaborated with engineering to ship the feature 1 week ahead of schedule."
                    ]
                },
                {
                    "role": "Software Engineer",
                    "company": "TechStart",
                    "duration": "Jan 2022 - May 2023",
                    "bullets": [
                        "Built scalable backend services using Python and SQL.",
                        "Reduced API latency by 40% through query optimization."
                    ]
                }
            ],
            "education": [
                {
                    "degree": "B.Tech in Computer Science",
                    "school": "National Institute of Technology",
                    "year": "2024"
                }
            ],
            "skills": [
                "Python", "SQL", "Figma", "A/B Testing", "Agile", "User Research", "Data Analysis", "Roadmapping"
            ]
        }
        
    @staticmethod
    def _get_mock_accomplishments() -> list[dict]:
        return [
            {
                "role": "Product Intern",
                "company": "XYZ Corp",
                "duration": "Jun 2023 - Aug 2023",
                "accomplishment": "Led redesign of onboarding flow.",
                "skills_used": ["Figma", "User Research", "A/B Testing", "Data Analysis"],
                "metrics_impact": "23% drop in drop-off rate",
                "tags": ["onboarding", "ux", "retention", "consumer"]
            },
            {
                "role": "Software Engineer",
                "company": "TechStart",
                "duration": "Jan 2022 - May 2023",
                "accomplishment": "Built scalable backend services and optimized queries.",
                "skills_used": ["Python", "SQL", "Backend", "Performance"],
                "metrics_impact": "Reduced API latency by 40%",
                "tags": ["infrastructure", "engineering", "b2b saas"]
            },
            {
                "role": "Academic Project",
                "company": "University",
                "duration": "Jan 2024 - Apr 2024",
                "accomplishment": "Developed market entry strategy for a fintech startup.",
                "skills_used": ["Market Research", "Roadmapping", "Stakeholder Management"],
                "metrics_impact": "Awarded 1st place in university competition",
                "tags": ["fintech", "strategy", "presentation"]
            }
        ]

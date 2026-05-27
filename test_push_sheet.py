import os
import sys
import uuid
from dotenv import load_dotenv

# Set UTF-8 encoding for Windows terminals
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Load environment variables
load_dotenv()

from src.shared.sheets_gateway import SheetsGateway

def push_test_row():
    print("=" * 60)
    print("PUSHING TEST ROW TO GOOGLE SHEET")
    print("=" * 60)

    try:
        # Initialize SheetsGateway (this will pull existing rows first)
        print("Connecting to Google Sheets...")
        gateway = SheetsGateway.from_seed_rows([])
        
        if not gateway.use_live_sheets:
            print("✗ Error: SheetsGateway is in fallback in-memory mode. Check your credentials/sheet ID in .env.")
            return

        test_job_id = f"test-{uuid.uuid4().hex[:6]}"
        test_row = {
            "job_id": test_job_id,
            "company": "AI Agent Sourcing Test",
            "role_title": "Associate Product Manager",
            "job_url": "https://example.com/test-sourcing",
            "source_platform": "SearchApi",
            "date_scraped": "2026-05-26",
            "region": "India",
            "work_mode": "remote",
            "work_permit_required": "FALSE",
            "fit_score": "95",
            "status": "SCRAPED",
            "notes": "Verified connection successfully at 10:13 PM IST."
        }

        print(f"\nAdding test row (Job ID: {test_job_id})...")
        gateway.add_rows([test_row])
        
        print("✓ Committing and syncing to Google Sheets...")
        gateway.commit()
        
        print("\n🎉 Success! The test row 'AI Agent Sourcing Test' has been pushed to the Google Sheet.")
        print("Please check your Google Sheet now. You should see it at the bottom of the table!")

    except Exception as e:
        print(f"✗ Failed to push row: {e}")

if __name__ == "__main__":
    push_test_row()

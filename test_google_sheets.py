import os
import sys
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

def test_sheets():
    print("=" * 60)
    print("TESTING GOOGLE SHEETS INTEGRATION")
    print("=" * 60)

    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'secrets/google_service_account.json')
    sheet_id = os.environ.get('GOOGLE_PIPELINE_TRACKER_SHEET_ID')

    print(f"Credentials Path: {creds_path} ({'Exists' if os.path.exists(creds_path) else 'Missing'})")
    print(f"Sheet ID: {sheet_id}")

    if not os.path.exists(creds_path):
        print("✗ Google service account JSON missing. Cannot test sheets.")
        return

    if not sheet_id:
        print("✗ GOOGLE_PIPELINE_TRACKER_SHEET_ID not set in .env. Cannot test sheets.")
        return

    try:
        # We initialize with a simple test row
        test_row = {
            "job_id": "test_id_123",
            "company": "Test Company",
            "role_title": "Test APM",
            "job_url": "https://example.com/test-apm-job",
            "source_platform": "TestPlatform",
            "date_scraped": "2026-05-26",
            "region": "India",
            "work_mode": "remote",
            "work_permit_required": "FALSE",
            "fit_score": "95",
            "status": "SCRAPED"
        }
        
        print("\nInitializing SheetsGateway...")
        gateway = SheetsGateway.from_seed_rows([test_row])
        
        print(f"Use Live Sheets: {gateway.use_live_sheets}")
        if not gateway.use_live_sheets:
            print("✗ SheetsGateway initialized in in-memory fallback mode.")
            return

        print("\nListing rows from Google Sheet...")
        rows = gateway.list_rows()
        print(f"✓ Found {len(rows)} rows in the Google Sheet!")
        if rows:
            print(f"First row: {rows[0].get('company')} - {rows[0].get('role_title')} ({rows[0].get('status')})")
            
    except Exception as e:
        print(f"✗ Google Sheets test failed: {e}")

if __name__ == "__main__":
    test_sheets()

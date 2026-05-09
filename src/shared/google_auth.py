import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

class GoogleDriveAuth:
    """Provides authenticated clients for Google Drive, Docs, and Sheets APIs."""
    
    SCOPES = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/documents',
        'https://www.googleapis.com/auth/spreadsheets'
    ]

    def __init__(self):
        self.creds = None
        creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'secrets/google_service_account.json')
        
        if os.path.exists(creds_path):
            self.creds = service_account.Credentials.from_service_account_file(
                creds_path, scopes=self.SCOPES)
        else:
            # Fallback for testing/mocking if file doesn't exist
            pass

    def get_drive_service(self):
        if not self.creds: return None
        return build('drive', 'v3', credentials=self.creds)

    def get_docs_service(self):
        if not self.creds: return None
        return build('docs', 'v1', credentials=self.creds)

    def get_sheets_service(self):
        if not self.creds: return None
        return build('sheets', 'v4', credentials=self.creds)

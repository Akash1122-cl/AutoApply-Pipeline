from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
import os

from src.orchestrator.state_engine import validate_transition, StateTransitionError

try:
    from src.shared.google_auth import GoogleDriveAuth
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class SheetsGateway:
    """
    Pipeline Tracker adapter with Google Sheets API support.
    Falls back to in-memory mode if Google Sheets credentials not configured.
    """

    rows: List[Dict[str, Any]]
    spreadsheet_id: Optional[str] = None
    use_live_sheets: bool = False
    _sheet_service: Optional[Any] = None

    @classmethod
    def from_seed_rows(cls, rows: Optional[Iterable[Dict[str, Any]]] = None) -> "SheetsGateway":
        seeded = list(rows or [])
        for row in seeded:
            row.setdefault("updated_at", _utc_now_iso())
            row.setdefault("row_version", 1)
        
        # Try to initialize Google Sheets API
        spreadsheet_id = os.getenv("GOOGLE_PIPELINE_TRACKER_SHEET_ID")
        use_live = GOOGLE_SHEETS_AVAILABLE and spreadsheet_id is not None
        
        gateway = cls(rows=seeded, spreadsheet_id=spreadsheet_id, use_live_sheets=use_live)
        if use_live:
            try:
                gateway._initialize_sheets_service()
                gateway._sync_from_sheets()  # SYNC ON INIT
                print(f"INFO: Using Google Sheets API for Pipeline Tracker (ID: {spreadsheet_id})")
            except Exception as e:
                print(f"WARNING: Failed to initialize Google Sheets API: {e}. Falling back to in-memory mode.")
                gateway.use_live_sheets = False
        else:
            print("INFO: Google Sheets API not configured. Using in-memory mode.")
        
        return gateway

    def commit(self) -> None:
        """Explicitly sync in-memory state to Google Sheets."""
        if self.use_live_sheets:
            self._sync_to_sheets()

    def list_rows(self) -> List[Dict[str, Any]]:
        return [dict(row) for row in self.rows]

    def get_rows_by_status(self, status: str) -> List[Dict[str, Any]]:
        return [dict(r) for r in self.rows if r.get("status") == status]

    def get_row(self, job_id: str) -> Dict[str, Any]:
        for row in self.rows:
            if row.get("job_id") == job_id:
                return row
        raise KeyError(f"job_id '{job_id}' not found")

    def update_row(
        self,
        job_id: str,
        patch: Dict[str, Any],
        *,
        expected_updated_at: Optional[str] = None,
        expected_row_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        row = self.get_row(job_id)
        
        # Optimistic locking checks
        if expected_updated_at and row.get("updated_at") != expected_updated_at:
            raise ValueError(
                f"Write conflict for {job_id}: expected updated_at={expected_updated_at},"
                f" actual={row.get('updated_at')}"
            )
        if expected_row_version and row.get("row_version") != expected_row_version:
            raise ValueError(
                f"Write conflict for {job_id}: expected row_version={expected_row_version},"
                f" actual={row.get('row_version')}"
            )

        row.update(patch)
        row["updated_at"] = _utc_now_iso()
        row["row_version"] = int(row.get("row_version", 1)) + 1
        return dict(row)

    def set_failed(self, job_id: str, agent_name: str, error_message: str) -> Dict[str, Any]:
        row = self.get_row(job_id)
        current_status = row.get("status", "")
        
        # Route FAILED transition through state engine validator for safety
        try:
            validate_transition(current_status, "FAILED")
        except StateTransitionError as e:
            # If transition is invalid, return current state unchanged
            return dict(row)
        
        row["status"] = "FAILED"
        existing_notes = row.get("notes", "")
        extra = f"[{_utc_now_iso()}] {agent_name}: {error_message}"
        row["notes"] = f"{existing_notes}\n{extra}".strip()
        row["updated_at"] = _utc_now_iso()
        row["row_version"] = int(row.get("row_version", 1)) + 1
        return dict(row)

    def add_rows(self, new_rows: List[Dict[str, Any]]) -> None:
        for row in new_rows:
            row.setdefault("updated_at", _utc_now_iso())
            row.setdefault("row_version", 1)
            self.rows.append(row)
        self.commit()  # SYNC TO SHEETS AFTER ADDING NEW ROWS

    def get_existing_dedup_keys(self) -> set[tuple[str, str, str]]:
        keys = set()
        for row in self.rows:
            company = str(row.get("company", "")).strip().lower()
            role_title = str(row.get("role_title", "")).strip().lower()
            job_url = str(row.get("job_url", "")).strip().lower()
            if company or role_title or job_url:
                keys.add((company, role_title, job_url))
        return keys

    def _initialize_sheets_service(self) -> None:
        """Initialize Google Sheets API service."""
        if not GOOGLE_SHEETS_AVAILABLE:
            raise ImportError("Google Sheets API not available. Install google-api-python-client and configure credentials.")
        
        auth = GoogleDriveAuth()
        self._sheet_service = auth.get_sheets_service()

    def _sync_from_sheets(self) -> None:
        """Sync rows from Google Sheety to in-memory cache."""
        if not self.use_live_sheets or not self._sheet_service:
            return
        
        try:
            result = self._sheet_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range="A:Z"  # Adjust range as needed
            ).execute()
            
            values = result.get('values', [])
            if not values:
                return
            
            # Parse header row
            headers = values[0]
            self.rows = []
            
            for row in values[1:]:
                row_dict = {}
                for i, header in enumerate(headers):
                    if i < len(row):
                        row_dict[header] = row[i]
                self.rows.append(row_dict)
                
        except Exception as e:
            print(f"ERROR: Failed to sync from Google Sheets: {e}")

    def _sync_to_sheets(self) -> None:
        """Sync in-memory rows to Google Sheets."""
        if not self.use_live_sheets or not self._sheet_service:
            return
        
        try:
            if not self.rows:
                return
            
            # Prepare data for sheets
            headers = list(self.rows[0].keys())
            values = [headers]
            
            for row in self.rows:
                values.append([row.get(h, "") for h in headers])
            
            # Update sheet
            body = {'values': values}
            self._sheet_service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range="A:Z",
                valueInputOption="RAW",
                body=body
            ).execute()
            
        except Exception as e:
            print(f"ERROR: Failed to sync to Google Sheets: {e}")

"""Google Sheets connector - sync leads from/to spreadsheets."""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx
import structlog

from backend.services.connectors.base import BaseConnector, SyncResult

logger = structlog.get_logger()


class GoogleSheetsConnector(BaseConnector):
    """
    Google Sheets connector supporting:
    - Read leads from a spreadsheet
    - Write/append leads to a spreadsheet
    - Auto-detect column headers
    - Scheduled sync (poll for changes)
    - Multiple sheet support
    """

    SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"

    @property
    def connector_type(self) -> str:
        return "google_sheets"

    def default_field_mapping(self) -> Dict[str, str]:
        return {
            "Email": "email",
            "First Name": "first_name",
            "Last Name": "last_name",
            "Phone": "phone",
            "Job Title": "job_title",
            "Company": "company_name",
            "City": "city",
            "Country": "country",
            "Website": "website",
            "LinkedIn": "linkedin_url",
            "Source": "source_detail",
            "Notes": "custom_fields.notes",
        }

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.credentials.get('access_token', '')}",
            "Content-Type": "application/json",
        }

    @property
    def spreadsheet_id(self) -> str:
        return self.config.get("spreadsheet_id", "")

    @property
    def sheet_name(self) -> str:
        return self.config.get("sheet_name", "Sheet1")

    @property
    def header_row(self) -> int:
        return self.config.get("header_row", 1)

    async def test_connection(self) -> bool:
        """Test Google Sheets API access."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.SHEETS_API}/{self.spreadsheet_id}",
                    headers=self._get_headers(),
                )
                return response.status_code == 200
        except:
            return False

    async def sync_inbound(self, since: Optional[datetime] = None) -> SyncResult:
        """Read leads from Google Sheets."""
        result = SyncResult(success=True, direction="inbound", started_at=datetime.utcnow())

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Get all data from sheet
                range_notation = f"{self.sheet_name}!A{self.header_row}:Z"
                response = await client.get(
                    f"{self.SHEETS_API}/{self.spreadsheet_id}/values/{range_notation}",
                    headers=self._get_headers(),
                )

                if response.status_code != 200:
                    result.success = False
                    result.errors.append({"message": f"API error: {response.status_code}"})
                    return result

                data = response.json()
                rows = data.get("values", [])

                if not rows:
                    result.metadata = {"message": "Sheet is empty"}
                    return result

                # First row is headers
                headers = [h.strip() for h in rows[0]]
                data_rows = rows[1:]

                # Auto-detect field mapping if not configured
                if not self.field_mapping:
                    self.field_mapping = self._auto_detect_mapping(headers)

                leads = []
                for row_idx, row in enumerate(data_rows):
                    # Pad row to match header length
                    while len(row) < len(headers):
                        row.append("")

                    record = dict(zip(headers, row))

                    # Skip empty rows
                    if not any(v.strip() for v in row):
                        continue

                    mapped = self.map_fields(record, "inbound")
                    mapped["custom_fields"] = mapped.get("custom_fields", {})
                    mapped["custom_fields"]["sheet_row"] = row_idx + self.header_row + 1
                    mapped["custom_fields"]["spreadsheet_id"] = self.spreadsheet_id

                    leads.append(mapped)
                    result.records_processed += 1

                result.data = leads
                result.records_created = len(leads)
                result.metadata = {
                    "headers": headers,
                    "total_rows": len(data_rows),
                    "sheet_name": self.sheet_name,
                }

        except Exception as e:
            result.success = False
            result.errors.append({"message": str(e)})

        result.completed_at = datetime.utcnow()
        return result

    async def sync_outbound(self, leads: List[Dict]) -> SyncResult:
        """Write/append leads to Google Sheets."""
        result = SyncResult(success=True, direction="outbound", started_at=datetime.utcnow())

        try:
            # Get current headers
            headers = list(self.field_mapping.keys())

            # Convert leads to rows
            rows = []
            for lead in leads:
                mapped = self.map_fields(lead, "outbound")
                row = [str(mapped.get(h, "")) for h in headers]
                rows.append(row)

            async with httpx.AsyncClient(timeout=30) as client:
                # Append to sheet
                range_notation = f"{self.sheet_name}!A:Z"
                payload = {
                    "values": rows,
                    "majorDimension": "ROWS",
                }

                response = await client.post(
                    f"{self.SHEETS_API}/{self.spreadsheet_id}/values/{range_notation}:append",
                    headers=self._get_headers(),
                    params={"valueInputOption": "USER_ENTERED"},
                    json=payload,
                )

                if response.status_code == 200:
                    result.records_created = len(rows)
                else:
                    result.success = False
                    result.errors.append({"message": f"Append failed: {response.status_code}"})

                result.records_processed = len(leads)

        except Exception as e:
            result.success = False
            result.errors.append({"message": str(e)})

        result.completed_at = datetime.utcnow()
        return result

    def _auto_detect_mapping(self, headers: List[str]) -> Dict[str, str]:
        """Auto-detect column mapping from header names."""
        # Common header variations -> internal field
        detection_rules = {
            "email": ["email", "e-mail", "email address", "mail"],
            "first_name": ["first name", "firstname", "first", "given name"],
            "last_name": ["last name", "lastname", "last", "surname", "family name"],
            "phone": ["phone", "telephone", "tel", "mobile", "cell", "phone number"],
            "job_title": ["title", "job title", "position", "role", "designation"],
            "company_name": ["company", "organization", "org", "company name", "business"],
            "city": ["city", "town"],
            "country": ["country", "nation"],
            "website": ["website", "url", "web", "site"],
            "linkedin_url": ["linkedin", "linkedin url", "linkedin profile"],
            "source_detail": ["source", "lead source", "how found"],
        }

        mapping = {}
        for header in headers:
            header_lower = header.lower().strip()
            for internal_field, variations in detection_rules.items():
                if header_lower in variations:
                    mapping[header] = internal_field
                    break

        return mapping

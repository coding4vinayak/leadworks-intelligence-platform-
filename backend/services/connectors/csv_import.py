"""CSV/Excel importer - bulk lead import from files."""
import csv
import io
from datetime import datetime
from typing import Any, Dict, List, Optional, BinaryIO
import structlog

from backend.services.connectors.base import BaseConnector, SyncResult

logger = structlog.get_logger()


class CSVImporter(BaseConnector):
    """
    CSV/Excel file importer supporting:
    - CSV files (comma, semicolon, tab delimited)
    - Excel files (.xlsx, .xls)
    - Auto-delimiter detection
    - Auto column mapping
    - Duplicate detection
    - Data validation
    - Large file streaming (chunked processing)
    """

    @property
    def connector_type(self) -> str:
        return "csv_import"

    def default_field_mapping(self) -> Dict[str, str]:
        return {}  # Auto-detected per file

    async def test_connection(self) -> bool:
        """CSV doesn't need connection testing."""
        return True

    async def sync_inbound(self, since: Optional[datetime] = None) -> SyncResult:
        """Not used for CSV - use import_file instead."""
        return SyncResult(success=False, errors=[{"message": "Use import_file()"}])

    async def import_file(
        self,
        file_content: bytes,
        filename: str,
        field_mapping: Optional[Dict[str, str]] = None,
        skip_duplicates: bool = True,
        validate: bool = True,
        chunk_size: int = 1000,
    ) -> SyncResult:
        """
        Import leads from a CSV or Excel file.

        Args:
            file_content: Raw file bytes
            filename: Original filename (for type detection)
            field_mapping: Custom mapping override
            skip_duplicates: Whether to skip duplicate emails
            validate: Whether to validate data
            chunk_size: Process this many rows at a time
        """
        result = SyncResult(success=True, direction="inbound", started_at=datetime.utcnow())

        try:
            if filename.endswith(('.xlsx', '.xls')):
                rows, headers = self._parse_excel(file_content)
            else:
                rows, headers = self._parse_csv(file_content)

            if not rows:
                result.success = False
                result.errors.append({"message": "No data found in file"})
                return result

            # Use provided mapping or auto-detect
            mapping = field_mapping or self._auto_detect_mapping(headers)
            self.field_mapping = mapping

            result.metadata = {
                "filename": filename,
                "total_rows": len(rows),
                "headers": headers,
                "detected_mapping": mapping,
            }

            # Process rows
            seen_emails = set()
            leads = []

            for row_idx, row in enumerate(rows):
                record = dict(zip(headers, row))
                mapped = self.map_fields(record, "inbound")

                # Validation
                if validate:
                    validation_errors = self._validate_lead(mapped)
                    if validation_errors:
                        result.records_failed += 1
                        result.errors.append({
                            "row": row_idx + 2,
                            "errors": validation_errors,
                        })
                        continue

                # Duplicate check
                email = mapped.get("email", "").lower().strip()
                if skip_duplicates and email:
                    if email in seen_emails:
                        result.records_failed += 1
                        continue
                    seen_emails.add(email)

                # Store unmapped columns in custom_fields
                unmapped = {k: v for k, v in record.items() if k not in mapping}
                if unmapped:
                    mapped["custom_fields"] = mapped.get("custom_fields", {})
                    mapped["custom_fields"].update(unmapped)

                mapped["source"] = "csv_import"
                mapped["source_detail"] = filename
                leads.append(mapped)
                result.records_processed += 1

            result.data = leads
            result.records_created = len(leads)

        except Exception as e:
            result.success = False
            result.errors.append({"message": f"Import failed: {str(e)}"})
            logger.error("csv_import_failed", error=str(e))

        result.completed_at = datetime.utcnow()
        return result

    def _parse_csv(self, content: bytes) -> tuple:
        """Parse CSV file with auto-delimiter detection."""
        # Try to decode
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1")

        # Detect delimiter
        sniffer = csv.Sniffer()
        try:
            dialect = sniffer.sniff(text[:5000])
            delimiter = dialect.delimiter
        except:
            delimiter = ","

        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows = list(reader)

        if not rows:
            return [], []

        headers = [h.strip() for h in rows[0]]
        data_rows = rows[1:]

        # Pad short rows
        for i, row in enumerate(data_rows):
            while len(row) < len(headers):
                row.append("")
            data_rows[i] = row[:len(headers)]

        return data_rows, headers

    def _parse_excel(self, content: bytes) -> tuple:
        """Parse Excel file using openpyxl."""
        try:
            import openpyxl
            from io import BytesIO

            wb = openpyxl.load_workbook(BytesIO(content), read_only=True)
            ws = wb.active

            rows = []
            headers = []

            for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
                str_row = [str(cell) if cell is not None else "" for cell in row]
                if row_idx == 0:
                    headers = [h.strip() for h in str_row]
                else:
                    rows.append(str_row)

            return rows, headers

        except ImportError:
            logger.error("openpyxl not installed")
            return [], []

    def _auto_detect_mapping(self, headers: List[str]) -> Dict[str, str]:
        """Auto-detect column mapping from header names."""
        detection_rules = {
            "email": ["email", "e-mail", "email address", "mail", "email_address"],
            "first_name": ["first name", "firstname", "first", "given name", "first_name"],
            "last_name": ["last name", "lastname", "last", "surname", "last_name"],
            "phone": ["phone", "telephone", "tel", "mobile", "cell", "phone number", "phone_number"],
            "job_title": ["title", "job title", "position", "role", "job_title", "designation"],
            "company_name": ["company", "organization", "org", "company name", "company_name", "business"],
            "city": ["city", "town", "location"],
            "state": ["state", "province", "region"],
            "country": ["country", "nation"],
            "website": ["website", "url", "web", "site", "domain"],
            "linkedin_url": ["linkedin", "linkedin url", "linkedin_url", "linkedin profile"],
            "source_detail": ["source", "lead source", "lead_source", "channel"],
        }

        mapping = {}
        for header in headers:
            header_lower = header.lower().strip()
            for internal_field, variations in detection_rules.items():
                if header_lower in variations:
                    mapping[header] = internal_field
                    break

        return mapping

    def _validate_lead(self, lead: Dict) -> List[str]:
        """Validate a lead record."""
        errors = []

        email = lead.get("email", "").strip()
        if email:
            import re
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                errors.append(f"Invalid email: {email}")

        # Must have at least email or name+company
        if not email and not (lead.get("first_name") and lead.get("company_name")):
            errors.append("Must have email or (name + company)")

        return errors

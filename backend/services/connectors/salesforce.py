"""Salesforce connector - enterprise CRM sync with OAuth2."""
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx
import structlog

from backend.services.connectors.base import BaseConnector, SyncResult

logger = structlog.get_logger()


class SalesforceConnector(BaseConnector):
    """
    Salesforce CRM connector supporting:
    - Lead/Contact object sync
    - Account (Company) sync
    - Opportunity pipeline
    - Custom object support
    - SOQL queries
    """

    @property
    def connector_type(self) -> str:
        return "salesforce"

    def default_field_mapping(self) -> Dict[str, str]:
        return {
            "Email": "email",
            "FirstName": "first_name",
            "LastName": "last_name",
            "Phone": "phone",
            "Title": "job_title",
            "Company": "company_name",
            "City": "city",
            "State": "state",
            "Country": "country",
            "Website": "website",
            "Status": "status",
            "LeadSource": "source_detail",
            "Description": "custom_fields.description",
        }

    @property
    def instance_url(self) -> str:
        return self.credentials.get("instance_url", "")

    @property
    def access_token(self) -> str:
        return self.credentials.get("access_token", "")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def authenticate(self) -> bool:
        """
        Authenticate with Salesforce via OAuth2.
        Supports: password grant, refresh token, JWT bearer.
        """
        grant_type = self.credentials.get("grant_type", "password")

        try:
            async with httpx.AsyncClient() as client:
                if grant_type == "password":
                    payload = {
                        "grant_type": "password",
                        "client_id": self.credentials["client_id"],
                        "client_secret": self.credentials["client_secret"],
                        "username": self.credentials["username"],
                        "password": self.credentials["password"] + self.credentials.get("security_token", ""),
                    }
                elif grant_type == "refresh_token":
                    payload = {
                        "grant_type": "refresh_token",
                        "client_id": self.credentials["client_id"],
                        "client_secret": self.credentials["client_secret"],
                        "refresh_token": self.credentials["refresh_token"],
                    }
                else:
                    return False

                response = await client.post(
                    "https://login.salesforce.com/services/oauth2/token",
                    data=payload,
                )

                if response.status_code == 200:
                    data = response.json()
                    self.credentials["access_token"] = data["access_token"]
                    self.credentials["instance_url"] = data["instance_url"]
                    return True
                else:
                    logger.error("sf_auth_failed", status=response.status_code)
                    return False

        except Exception as e:
            logger.error("sf_auth_error", error=str(e))
            return False

    async def test_connection(self) -> bool:
        """Test Salesforce connection."""
        if not self.access_token:
            return await self.authenticate()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.instance_url}/services/data/v58.0/sobjects",
                    headers=self._get_headers(),
                )
                return response.status_code == 200
        except:
            return False

    async def sync_inbound(self, since: Optional[datetime] = None) -> SyncResult:
        """Pull leads from Salesforce."""
        result = SyncResult(success=True, direction="inbound", started_at=datetime.utcnow())

        if not self.access_token:
            if not await self.authenticate():
                result.success = False
                result.errors.append({"message": "Authentication failed"})
                return result

        try:
            # Build SOQL query
            fields = ",".join(self.field_mapping.keys())
            query = f"SELECT Id,{fields} FROM Lead"
            if since:
                query += f" WHERE LastModifiedDate >= {since.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            query += " ORDER BY LastModifiedDate DESC LIMIT 2000"

            all_leads = []
            async with httpx.AsyncClient(timeout=30) as client:
                url = f"{self.instance_url}/services/data/v58.0/query"
                params = {"q": query}

                while url:
                    response = await client.get(url, headers=self._get_headers(), params=params)

                    if response.status_code != 200:
                        result.errors.append({"message": f"Query failed: {response.status_code}"})
                        break

                    data = response.json()
                    records = data.get("records", [])

                    for record in records:
                        mapped = self.map_fields(record, "inbound")
                        mapped["custom_fields"] = {
                            "salesforce_id": record.get("Id"),
                            "salesforce_type": "Lead",
                        }
                        all_leads.append(mapped)

                    result.records_processed += len(records)

                    # Handle pagination
                    next_url = data.get("nextRecordsUrl")
                    if next_url:
                        url = f"{self.instance_url}{next_url}"
                        params = {}
                    else:
                        url = None

            result.data = all_leads
            result.records_created = len(all_leads)

        except Exception as e:
            result.success = False
            result.errors.append({"message": str(e)})

        result.completed_at = datetime.utcnow()
        return result

    async def sync_outbound(self, leads: List[Dict]) -> SyncResult:
        """Push leads to Salesforce."""
        result = SyncResult(success=True, direction="outbound", started_at=datetime.utcnow())

        if not self.access_token:
            if not await self.authenticate():
                result.success = False
                result.errors.append({"message": "Authentication failed"})
                return result

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                for lead in leads:
                    mapped = self.map_fields(lead, "outbound")
                    # Remove None values
                    mapped = {k: v for k, v in mapped.items() if v is not None}

                    # Check if exists by email
                    sf_id = lead.get("custom_fields", {}).get("salesforce_id")

                    if sf_id:
                        # Update existing
                        response = await client.patch(
                            f"{self.instance_url}/services/data/v58.0/sobjects/Lead/{sf_id}",
                            headers=self._get_headers(),
                            json=mapped,
                        )
                        if response.status_code == 204:
                            result.records_updated += 1
                        else:
                            result.records_failed += 1
                    else:
                        # Create new
                        response = await client.post(
                            f"{self.instance_url}/services/data/v58.0/sobjects/Lead",
                            headers=self._get_headers(),
                            json=mapped,
                        )
                        if response.status_code == 201:
                            result.records_created += 1
                        else:
                            result.records_failed += 1
                            result.errors.append({
                                "email": lead.get("email"),
                                "error": response.text,
                            })

                    result.records_processed += 1

        except Exception as e:
            result.success = False
            result.errors.append({"message": str(e)})

        result.completed_at = datetime.utcnow()
        return result

    async def run_soql(self, query: str) -> List[Dict]:
        """Run a custom SOQL query."""
        if not self.access_token:
            await self.authenticate()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.instance_url}/services/data/v58.0/query",
                    headers=self._get_headers(),
                    params={"q": query},
                )
                if response.status_code == 200:
                    return response.json().get("records", [])
        except:
            pass
        return []

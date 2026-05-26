"""HubSpot connector - bi-directional CRM sync."""
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx
import structlog

from backend.services.connectors.base import BaseConnector, SyncResult

logger = structlog.get_logger()


class HubSpotConnector(BaseConnector):
    """
    HubSpot CRM connector supporting:
    - Contact sync (inbound/outbound)
    - Company sync
    - Deal pipeline sync
    - Activity/engagement tracking
    - List membership
    """

    BASE_URL = "https://api.hubapi.com"

    @property
    def connector_type(self) -> str:
        return "hubspot"

    def default_field_mapping(self) -> Dict[str, str]:
        return {
            "email": "email",
            "firstname": "first_name",
            "lastname": "last_name",
            "phone": "phone",
            "jobtitle": "job_title",
            "company": "company_name",
            "city": "city",
            "state": "state",
            "country": "country",
            "website": "website",
            "linkedin_url": "linkedin_url",
            "lifecyclestage": "status",
            "hs_lead_status": "status",
        }

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.credentials.get('access_token', '')}",
            "Content-Type": "application/json",
        }

    async def test_connection(self) -> bool:
        """Test HubSpot API connection."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/crm/v3/objects/contacts",
                    headers=self._get_headers(),
                    params={"limit": 1},
                )
                return response.status_code == 200
        except Exception as e:
            logger.error("hubspot_connection_test_failed", error=str(e))
            return False

    async def sync_inbound(self, since: Optional[datetime] = None) -> SyncResult:
        """Pull contacts from HubSpot."""
        result = SyncResult(
            success=True,
            direction="inbound",
            started_at=datetime.utcnow(),
        )
        all_contacts = []
        after = None

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                while True:
                    params = {
                        "limit": 100,
                        "properties": ",".join(self.field_mapping.keys()),
                    }
                    if after:
                        params["after"] = after
                    if since:
                        params["filterGroups"] = [{
                            "filters": [{
                                "propertyName": "lastmodifieddate",
                                "operator": "GTE",
                                "value": int(since.timestamp() * 1000),
                            }]
                        }]

                    response = await client.get(
                        f"{self.BASE_URL}/crm/v3/objects/contacts",
                        headers=self._get_headers(),
                        params=params,
                    )

                    if response.status_code != 200:
                        result.errors.append({
                            "message": f"API error: {response.status_code}",
                            "details": response.text,
                        })
                        break

                    data = response.json()
                    contacts = data.get("results", [])

                    for contact in contacts:
                        props = contact.get("properties", {})
                        props["hubspot_id"] = contact.get("id")
                        mapped = self.map_fields(props, "inbound")
                        mapped["custom_fields"] = {
                            "hubspot_id": contact.get("id"),
                            "hubspot_created": contact.get("createdAt"),
                        }
                        all_contacts.append(mapped)

                    result.records_processed += len(contacts)

                    # Pagination
                    paging = data.get("paging", {})
                    next_page = paging.get("next", {})
                    after = next_page.get("after")
                    if not after:
                        break

            result.data = all_contacts
            result.records_created = len(all_contacts)

        except Exception as e:
            result.success = False
            result.errors.append({"message": str(e)})
            logger.error("hubspot_sync_failed", error=str(e))

        result.completed_at = datetime.utcnow()
        return result

    async def sync_outbound(self, leads: List[Dict]) -> SyncResult:
        """Push leads to HubSpot as contacts."""
        result = SyncResult(
            success=True,
            direction="outbound",
            started_at=datetime.utcnow(),
        )

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Batch create/update (max 100 per batch)
                batch_size = 100
                for i in range(0, len(leads), batch_size):
                    batch = leads[i:i + batch_size]
                    inputs = []

                    for lead in batch:
                        mapped = self.map_fields(lead, "outbound")
                        inputs.append({"properties": mapped})

                    payload = {"inputs": inputs}
                    response = await client.post(
                        f"{self.BASE_URL}/crm/v3/objects/contacts/batch/create",
                        headers=self._get_headers(),
                        json=payload,
                    )

                    if response.status_code in (200, 201):
                        created = response.json().get("results", [])
                        result.records_created += len(created)
                    elif response.status_code == 409:
                        # Contacts exist, try update
                        for lead in batch:
                            await self._upsert_contact(client, lead, result)
                    else:
                        result.records_failed += len(batch)
                        result.errors.append({
                            "message": f"Batch create failed: {response.status_code}",
                            "batch_index": i,
                        })

                    result.records_processed += len(batch)

        except Exception as e:
            result.success = False
            result.errors.append({"message": str(e)})

        result.completed_at = datetime.utcnow()
        return result

    async def _upsert_contact(self, client: httpx.AsyncClient, lead: Dict, result: SyncResult):
        """Update existing contact or create new one."""
        email = lead.get("email")
        if not email:
            result.records_failed += 1
            return

        mapped = self.map_fields(lead, "outbound")

        # Search by email first
        search_payload = {
            "filterGroups": [{
                "filters": [{
                    "propertyName": "email",
                    "operator": "EQ",
                    "value": email,
                }]
            }],
            "limit": 1,
        }

        response = await client.post(
            f"{self.BASE_URL}/crm/v3/objects/contacts/search",
            headers=self._get_headers(),
            json=search_payload,
        )

        if response.status_code == 200:
            results = response.json().get("results", [])
            if results:
                # Update existing
                contact_id = results[0]["id"]
                update_response = await client.patch(
                    f"{self.BASE_URL}/crm/v3/objects/contacts/{contact_id}",
                    headers=self._get_headers(),
                    json={"properties": mapped},
                )
                if update_response.status_code == 200:
                    result.records_updated += 1
                else:
                    result.records_failed += 1
            else:
                # Create new
                create_response = await client.post(
                    f"{self.BASE_URL}/crm/v3/objects/contacts",
                    headers=self._get_headers(),
                    json={"properties": mapped},
                )
                if create_response.status_code in (200, 201):
                    result.records_created += 1
                else:
                    result.records_failed += 1

    async def get_deals(self, contact_id: str) -> List[Dict]:
        """Get deals associated with a contact."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/crm/v3/objects/contacts/{contact_id}/associations/deals",
                    headers=self._get_headers(),
                )
                if response.status_code == 200:
                    return response.json().get("results", [])
        except:
            pass
        return []

    async def get_engagement_history(self, contact_id: str) -> List[Dict]:
        """Get engagement/activity history for a contact."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/crm/v3/objects/contacts/{contact_id}/associations/engagements",
                    headers=self._get_headers(),
                )
                if response.status_code == 200:
                    return response.json().get("results", [])
        except:
            pass
        return []

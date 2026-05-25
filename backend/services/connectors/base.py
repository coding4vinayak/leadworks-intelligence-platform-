"""Base connector with standardized sync interface."""
import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger()


class SyncDirection(str, enum.Enum):
    INBOUND = "inbound"    # External -> Leadworks
    OUTBOUND = "outbound"  # Leadworks -> External
    BIDIRECTIONAL = "bidirectional"


@dataclass
class SyncResult:
    """Standard result for all connector sync operations."""
    success: bool
    direction: str = "inbound"
    records_processed: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_failed: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    data: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class BaseConnector(ABC):
    """
    Base class for all connectors.
    Provides: auth management, field mapping, error handling.
    """

    def __init__(
        self,
        credentials: Dict[str, Any],
        config: Dict[str, Any] = None,
        field_mapping: Dict[str, str] = None,
    ):
        self.credentials = credentials
        self.config = config or {}
        self.field_mapping = field_mapping or self.default_field_mapping()

    @property
    @abstractmethod
    def connector_type(self) -> str:
        """Return the connector type identifier."""
        pass

    @abstractmethod
    def default_field_mapping(self) -> Dict[str, str]:
        """Return default field mapping: {external_field: internal_field}."""
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the connection/credentials are valid."""
        pass

    @abstractmethod
    async def sync_inbound(self, since: Optional[datetime] = None) -> SyncResult:
        """Pull data from external system into Leadworks."""
        pass

    async def sync_outbound(self, leads: List[Dict]) -> SyncResult:
        """Push data from Leadworks to external system."""
        return SyncResult(success=False, errors=[{"message": "Outbound not supported"}])

    def map_fields(self, record: Dict[str, Any], direction: str = "inbound") -> Dict[str, Any]:
        """Map fields between external and internal formats."""
        mapped = {}
        if direction == "inbound":
            for ext_field, int_field in self.field_mapping.items():
                if ext_field in record:
                    mapped[int_field] = record[ext_field]
        else:
            # Reverse mapping for outbound
            reverse = {v: k for k, v in self.field_mapping.items()}
            for int_field, ext_field in reverse.items():
                if int_field in record:
                    mapped[ext_field] = record[int_field]
        return mapped

    def map_batch(self, records: List[Dict], direction: str = "inbound") -> List[Dict]:
        """Map a batch of records."""
        return [self.map_fields(r, direction) for r in records]

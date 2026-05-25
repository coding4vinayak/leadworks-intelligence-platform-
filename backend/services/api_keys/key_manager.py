"""API Key management - create, rotate, revoke keys for external access."""
import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
import structlog

logger = structlog.get_logger()


@dataclass
class APIKey:
    """Represents an API key."""
    id: str
    name: str
    key_prefix: str  # First 8 chars (visible)
    key_hash: str  # SHA-256 of full key (stored)
    team_id: str
    created_by: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True
    permissions: List[str] = field(default_factory=lambda: ["read", "write"])
    rate_limit_rpm: int = 1000
    allowed_ips: List[str] = field(default_factory=list)  # Empty = all IPs
    allowed_endpoints: List[str] = field(default_factory=list)  # Empty = all
    usage_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class APIKeyManager:
    """
    API key management for external integrations.

    Features:
    - Generate secure API keys (lw_sk_... format)
    - Scoped permissions (read-only, write, admin)
    - IP allowlisting
    - Endpoint restrictions
    - Automatic expiration
    - Usage tracking
    - Key rotation (create new before revoking old)
    - Rate limiting per key
    """

    KEY_PREFIX = "lw_sk_"

    def __init__(self):
        self._keys: Dict[str, APIKey] = {}  # key_hash -> APIKey
        self._prefix_index: Dict[str, str] = {}  # prefix -> key_hash

    def create_key(
        self,
        name: str,
        team_id: str,
        created_by: str,
        permissions: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None,
        allowed_ips: Optional[List[str]] = None,
        allowed_endpoints: Optional[List[str]] = None,
        rate_limit_rpm: int = 1000,
    ) -> Dict[str, Any]:
        """
        Create a new API key.

        Returns the full key (only shown once) and key metadata.
        """
        # Generate secure random key
        raw_key = secrets.token_urlsafe(32)
        full_key = f"{self.KEY_PREFIX}{raw_key}"
        key_prefix = full_key[:12]
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()

        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        api_key = APIKey(
            id=secrets.token_hex(8),
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            team_id=team_id,
            created_by=created_by,
            expires_at=expires_at,
            permissions=permissions or ["read", "write"],
            rate_limit_rpm=rate_limit_rpm,
            allowed_ips=allowed_ips or [],
            allowed_endpoints=allowed_endpoints or [],
        )

        self._keys[key_hash] = api_key
        self._prefix_index[key_prefix] = key_hash

        logger.info("api_key_created", name=name, team_id=team_id, prefix=key_prefix)

        return {
            "key": full_key,  # Only returned on creation!
            "key_id": api_key.id,
            "key_prefix": key_prefix,
            "name": name,
            "permissions": api_key.permissions,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "rate_limit_rpm": rate_limit_rpm,
            "message": "Save this key securely - it won't be shown again.",
        }

    def validate_key(
        self,
        key: str,
        ip_address: Optional[str] = None,
        endpoint: Optional[str] = None,
        required_permission: str = "read",
    ) -> Dict[str, Any]:
        """
        Validate an API key and check permissions.

        Returns:
            {"valid": bool, "team_id": str, "error": str, ...}
        """
        if not key.startswith(self.KEY_PREFIX):
            return {"valid": False, "error": "Invalid key format"}

        key_hash = hashlib.sha256(key.encode()).hexdigest()
        api_key = self._keys.get(key_hash)

        if not api_key:
            return {"valid": False, "error": "Key not found"}

        if not api_key.is_active:
            return {"valid": False, "error": "Key revoked"}

        if api_key.expires_at and datetime.utcnow() > api_key.expires_at:
            return {"valid": False, "error": "Key expired"}

        # Check IP allowlist
        if api_key.allowed_ips and ip_address:
            if ip_address not in api_key.allowed_ips:
                return {"valid": False, "error": "IP not allowed"}

        # Check endpoint restrictions
        if api_key.allowed_endpoints and endpoint:
            if not any(endpoint.startswith(ep) for ep in api_key.allowed_endpoints):
                return {"valid": False, "error": "Endpoint not allowed"}

        # Check permission
        if required_permission not in api_key.permissions:
            return {"valid": False, "error": f"Missing permission: {required_permission}"}

        # Update usage
        api_key.last_used_at = datetime.utcnow()
        api_key.usage_count += 1

        return {
            "valid": True,
            "team_id": api_key.team_id,
            "key_id": api_key.id,
            "name": api_key.name,
            "permissions": api_key.permissions,
            "rate_limit_rpm": api_key.rate_limit_rpm,
        }

    def revoke_key(self, key_id: str, team_id: str) -> bool:
        """Revoke an API key."""
        for api_key in self._keys.values():
            if api_key.id == key_id and api_key.team_id == team_id:
                api_key.is_active = False
                logger.info("api_key_revoked", key_id=key_id, team_id=team_id)
                return True
        return False

    def rotate_key(self, key_id: str, team_id: str, created_by: str) -> Optional[Dict[str, Any]]:
        """
        Rotate a key: create new one, schedule old one for revocation.
        Old key remains valid for 24h to allow migration.
        """
        old_key = None
        for api_key in self._keys.values():
            if api_key.id == key_id and api_key.team_id == team_id:
                old_key = api_key
                break

        if not old_key:
            return None

        # Create new key with same settings
        new_key_result = self.create_key(
            name=f"{old_key.name} (rotated)",
            team_id=team_id,
            created_by=created_by,
            permissions=old_key.permissions,
            allowed_ips=old_key.allowed_ips,
            allowed_endpoints=old_key.allowed_endpoints,
            rate_limit_rpm=old_key.rate_limit_rpm,
        )

        # Schedule old key expiration (24h grace period)
        old_key.expires_at = datetime.utcnow() + timedelta(hours=24)
        old_key.name = f"{old_key.name} (deprecated - expires in 24h)"

        new_key_result["old_key_expires_at"] = old_key.expires_at.isoformat()
        new_key_result["message"] = "New key created. Old key expires in 24 hours."

        return new_key_result

    def list_keys(self, team_id: str) -> List[Dict[str, Any]]:
        """List all API keys for a team (without revealing full keys)."""
        keys = []
        for api_key in self._keys.values():
            if api_key.team_id == team_id:
                keys.append({
                    "id": api_key.id,
                    "name": api_key.name,
                    "key_prefix": api_key.key_prefix,
                    "is_active": api_key.is_active,
                    "permissions": api_key.permissions,
                    "created_at": api_key.created_at.isoformat(),
                    "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
                    "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
                    "usage_count": api_key.usage_count,
                    "rate_limit_rpm": api_key.rate_limit_rpm,
                })
        return sorted(keys, key=lambda k: k["created_at"], reverse=True)

    def get_usage_stats(self, key_id: str, team_id: str) -> Optional[Dict[str, Any]]:
        """Get usage statistics for a specific key."""
        for api_key in self._keys.values():
            if api_key.id == key_id and api_key.team_id == team_id:
                return {
                    "key_id": api_key.id,
                    "name": api_key.name,
                    "total_requests": api_key.usage_count,
                    "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
                    "created_at": api_key.created_at.isoformat(),
                    "is_active": api_key.is_active,
                }
        return None

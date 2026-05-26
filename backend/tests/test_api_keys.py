"""Tests for API key management."""
import pytest
from backend.services.api_keys.key_manager import APIKeyManager


class TestAPIKeyManager:
    """Test API key creation, validation, and lifecycle."""

    def setup_method(self):
        self.manager = APIKeyManager()

    def test_create_key(self):
        """Create a new API key."""
        result = self.manager.create_key(
            name="Test Key",
            team_id="team_1",
            created_by="user_1",
        )
        assert result["key"].startswith("lw_sk_")
        assert result["key_prefix"] == result["key"][:12]
        assert result["name"] == "Test Key"
        assert "read" in result["permissions"]
        assert "write" in result["permissions"]

    def test_validate_key(self):
        """Validate a valid API key."""
        created = self.manager.create_key(
            name="Valid Key",
            team_id="team_1",
            created_by="user_1",
        )
        result = self.manager.validate_key(created["key"])
        assert result["valid"] is True
        assert result["team_id"] == "team_1"

    def test_validate_invalid_key(self):
        """Invalid key should fail validation."""
        result = self.manager.validate_key("lw_sk_invalid_key_here")
        assert result["valid"] is False
        assert result["error"] == "Key not found"

    def test_validate_bad_format(self):
        """Non-prefixed key should fail."""
        result = self.manager.validate_key("not_a_valid_key")
        assert result["valid"] is False
        assert result["error"] == "Invalid key format"

    def test_revoke_key(self):
        """Revoked key should fail validation."""
        created = self.manager.create_key(
            name="Revoke Me", team_id="team_1", created_by="user_1",
        )
        key_id = created["key_id"]

        # Revoke
        success = self.manager.revoke_key(key_id, "team_1")
        assert success is True

        # Validate should fail
        result = self.manager.validate_key(created["key"])
        assert result["valid"] is False
        assert result["error"] == "Key revoked"

    def test_ip_allowlist(self):
        """Key with IP allowlist should reject other IPs."""
        created = self.manager.create_key(
            name="IP Restricted",
            team_id="team_1",
            created_by="user_1",
            allowed_ips=["192.168.1.1", "10.0.0.1"],
        )
        # Valid IP
        result = self.manager.validate_key(created["key"], ip_address="192.168.1.1")
        assert result["valid"] is True

        # Invalid IP
        result = self.manager.validate_key(created["key"], ip_address="8.8.8.8")
        assert result["valid"] is False
        assert result["error"] == "IP not allowed"

    def test_permission_check(self):
        """Key with limited permissions should reject unauthorized ops."""
        created = self.manager.create_key(
            name="Read Only",
            team_id="team_1",
            created_by="user_1",
            permissions=["read"],
        )
        # Read should pass
        result = self.manager.validate_key(created["key"], required_permission="read")
        assert result["valid"] is True

        # Write should fail
        result = self.manager.validate_key(created["key"], required_permission="write")
        assert result["valid"] is False
        assert "Missing permission" in result["error"]

    def test_key_expiration(self):
        """Expired key should fail validation."""
        created = self.manager.create_key(
            name="Expires Soon",
            team_id="team_1",
            created_by="user_1",
            expires_in_days=0,  # Already expired (0 days)
        )
        # Manually expire it
        from datetime import datetime, timedelta
        key_hash = None
        for h, k in self.manager._keys.items():
            if k.name == "Expires Soon":
                k.expires_at = datetime.utcnow() - timedelta(hours=1)
                break

        result = self.manager.validate_key(created["key"])
        assert result["valid"] is False
        assert result["error"] == "Key expired"

    def test_rotate_key(self):
        """Key rotation should create new key and deprecate old."""
        created = self.manager.create_key(
            name="Original", team_id="team_1", created_by="user_1",
        )
        rotated = self.manager.rotate_key(created["key_id"], "team_1", "user_1")
        assert rotated is not None
        assert rotated["key"].startswith("lw_sk_")
        assert "rotated" in rotated["name"].lower() or "expires" in rotated.get("message", "").lower()

        # Old key should still work (grace period)
        result = self.manager.validate_key(created["key"])
        assert result["valid"] is True

    def test_list_keys(self):
        """List keys for a team (without revealing full keys)."""
        self.manager.create_key(name="Key 1", team_id="team_1", created_by="user_1")
        self.manager.create_key(name="Key 2", team_id="team_1", created_by="user_1")
        self.manager.create_key(name="Key 3", team_id="team_2", created_by="user_2")

        keys = self.manager.list_keys("team_1")
        assert len(keys) == 2
        # Should not contain full key
        assert all("lw_sk_" not in str(k.get("key", "")) for k in keys)
        assert all(k.get("key_prefix", "").startswith("lw_sk_") for k in keys)

    def test_usage_tracking(self):
        """Validation should increment usage count."""
        created = self.manager.create_key(
            name="Track Usage", team_id="team_1", created_by="user_1",
        )
        self.manager.validate_key(created["key"])
        self.manager.validate_key(created["key"])
        self.manager.validate_key(created["key"])

        stats = self.manager.get_usage_stats(created["key_id"], "team_1")
        assert stats["total_requests"] == 3

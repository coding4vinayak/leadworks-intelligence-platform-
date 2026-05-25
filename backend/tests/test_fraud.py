"""Tests for fraud detection engine."""
import pytest
from backend.services.fraud.email_validator import EmailValidator
from backend.services.fraud.duplicate_detector import DuplicateDetector


class TestEmailValidator:
    """Test email validation."""

    def setup_method(self):
        self.validator = EmailValidator(check_mx=False, check_smtp=False)

    @pytest.mark.asyncio
    async def test_valid_business_email(self):
        result = await self.validator.validate("john.doe@company.com")
        assert result["is_valid"] is True
        assert result["score"] >= 0.7
        assert result["is_disposable"] is False

    @pytest.mark.asyncio
    async def test_invalid_syntax(self):
        result = await self.validator.validate("not-an-email")
        assert result["is_valid"] is False
        assert result["score"] == 0.0
        assert "invalid_syntax" in result["flags"]

    @pytest.mark.asyncio
    async def test_disposable_email(self):
        result = await self.validator.validate("user@mailinator.com")
        assert result["is_disposable"] is True
        assert result["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_free_provider(self):
        result = await self.validator.validate("user@gmail.com")
        assert result["is_free_provider"] is True
        assert result["is_valid"] is True
        assert "free_email_provider" in result["flags"]

    @pytest.mark.asyncio
    async def test_role_based_email(self):
        result = await self.validator.validate("admin@company.com")
        assert result["is_role_based"] is True
        assert "role_based_email" in result["flags"]

    @pytest.mark.asyncio
    async def test_typo_detection(self):
        result = await self.validator.validate("user@gmial.com")
        assert result["suggested_correction"] == "user@gmail.com"
        assert "possible_typo" in result["flags"]


class TestDuplicateDetector:
    """Test duplicate lead detection."""

    def setup_method(self):
        self.detector = DuplicateDetector(threshold=0.75)

    def test_exact_email_match(self):
        new_lead = {"email": "john@company.com", "first_name": "John"}
        existing = [
            {"email": "john@company.com", "first_name": "John", "last_name": "Doe"},
        ]
        dupes = self.detector.find_duplicates(new_lead, existing)
        assert len(dupes) == 1
        assert dupes[0]["confidence"] >= 0.9

    def test_no_duplicate(self):
        new_lead = {"email": "alice@other.com", "first_name": "Alice"}
        existing = [
            {"email": "john@company.com", "first_name": "John"},
        ]
        dupes = self.detector.find_duplicates(new_lead, existing)
        assert len(dupes) == 0

    def test_phone_match(self):
        new_lead = {"phone": "+1 (555) 123-4567", "first_name": "John"}
        existing = [
            {"phone": "5551234567", "first_name": "John Doe"},
        ]
        dupes = self.detector.find_duplicates(new_lead, existing)
        assert len(dupes) == 1

    def test_batch_dedup(self):
        leads = [
            {"email": "a@company.com", "first_name": "Alice"},
            {"email": "b@company.com", "first_name": "Bob"},
            {"email": "a@company.com", "first_name": "Alice S."},  # duplicate
            {"email": "c@company.com", "first_name": "Charlie"},
        ]
        result = self.detector.batch_dedup(leads)
        assert result["stats"]["unique"] == 3
        assert result["stats"]["duplicates"] == 1

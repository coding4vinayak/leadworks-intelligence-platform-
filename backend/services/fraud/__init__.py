"""Fraud detection - spam filtering, bot detection, email validation, dedup."""
from backend.services.fraud.fraud_detector import FraudDetector, FraudResult
from backend.services.fraud.email_validator import EmailValidator
from backend.services.fraud.duplicate_detector import DuplicateDetector

__all__ = ["FraudDetector", "FraudResult", "EmailValidator", "DuplicateDetector"]

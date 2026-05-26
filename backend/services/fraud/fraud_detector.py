"""Fraud detector - comprehensive spam/bot/fake lead detection."""
import re
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
import structlog

from backend.services.fraud.email_validator import EmailValidator
from backend.services.fraud.duplicate_detector import DuplicateDetector

logger = structlog.get_logger()


@dataclass
class FraudResult:
    """Result of fraud analysis on a lead."""
    is_fraud: bool = False
    spam_score: float = 0.0  # 0-1, higher = more likely spam
    risk_level: str = "low"  # low, medium, high, critical
    flags: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    recommended_action: str = "accept"  # accept, review, quarantine, reject


# Known spam patterns
SPAM_NAME_PATTERNS = [
    r'^test\s*\d*$', r'^asdf', r'^qwerty', r'^aaa+', r'^xxx',
    r'^fuck', r'^spam', r'^fake', r'^none', r'^na$', r'^n/a$',
    r'^\d+$', r'^(.)\1{3,}',  # Repeated characters
]

SPAM_COMPANY_PATTERNS = [
    r'^test', r'^asdf', r'^none', r'^na$', r'^n/a$', r'^company$',
    r'^my\s*company$', r'^self$', r'^freelance$',
]

# Suspicious TLDs
SUSPICIOUS_TLDS = {
    ".xyz", ".top", ".club", ".icu", ".buzz", ".work", ".click",
    ".link", ".info", ".online", ".website", ".site", ".space",
}


class FraudDetector:
    """
    Multi-layer fraud detection system:

    Layer 1: Email validation (syntax, disposable, MX)
    Layer 2: Content analysis (spam patterns in names, gibberish detection)
    Layer 3: Bot detection (form timing, honeypot, behavior)
    Layer 4: Rate limiting (IP-based, domain-based)
    Layer 5: Duplicate detection
    Layer 6: Risk scoring (combine all signals)

    Each layer contributes to a final spam_score (0-1).
    """

    def __init__(self):
        self.email_validator = EmailValidator(check_mx=True, check_smtp=False)
        self.duplicate_detector = DuplicateDetector()
        self._ip_submissions: Dict[str, List[datetime]] = {}
        self._domain_submissions: Dict[str, List[datetime]] = {}

    async def analyze_lead(
        self,
        lead_data: Dict[str, Any],
        submission_metadata: Optional[Dict] = None,
        existing_leads: Optional[List[Dict]] = None,
    ) -> FraudResult:
        """
        Analyze a lead for fraud/spam indicators.

        Args:
            lead_data: The lead to analyze
            submission_metadata: IP, user agent, timing, honeypot fields
            existing_leads: Existing leads for duplicate checking
        """
        result = FraudResult()
        scores: List[float] = []

        metadata = submission_metadata or {}

        # Layer 1: Email validation
        email = lead_data.get("email", "")
        if email:
            email_result = await self.email_validator.validate(email)
            email_score = self._score_email(email_result)
            scores.append(email_score)
            if email_result.get("flags"):
                result.flags.extend([f"email:{f}" for f in email_result["flags"]])
            result.details["email_validation"] = email_result

        # Layer 2: Content analysis
        content_score = self._analyze_content(lead_data)
        scores.append(content_score["score"])
        result.flags.extend(content_score["flags"])

        # Layer 3: Bot detection
        bot_score = self._detect_bot(metadata)
        scores.append(bot_score["score"])
        result.flags.extend(bot_score["flags"])
        result.details["bot_detection"] = bot_score

        # Layer 4: Rate limiting
        rate_score = self._check_rate_limits(metadata, lead_data)
        scores.append(rate_score["score"])
        result.flags.extend(rate_score["flags"])

        # Layer 5: Duplicate check
        if existing_leads:
            dupes = self.duplicate_detector.find_duplicates(lead_data, existing_leads)
            if dupes:
                dupe_score = min(0.5, len(dupes) * 0.2)
                scores.append(dupe_score)
                result.flags.append(f"duplicate_found:{len(dupes)}")
                result.details["duplicates"] = len(dupes)

        # Layer 6: Combined risk scoring
        if scores:
            # Weighted average with max boost
            avg_score = sum(scores) / len(scores)
            max_score = max(scores)
            result.spam_score = round((avg_score * 0.6 + max_score * 0.4), 3)
        else:
            result.spam_score = 0.0

        # Determine risk level and action
        if result.spam_score >= 0.8:
            result.risk_level = "critical"
            result.is_fraud = True
            result.recommended_action = "reject"
        elif result.spam_score >= 0.6:
            result.risk_level = "high"
            result.is_fraud = True
            result.recommended_action = "quarantine"
        elif result.spam_score >= 0.4:
            result.risk_level = "medium"
            result.recommended_action = "review"
        else:
            result.risk_level = "low"
            result.recommended_action = "accept"

        return result

    async def analyze_batch(
        self,
        leads: List[Dict[str, Any]],
        existing_leads: Optional[List[Dict]] = None,
    ) -> List[FraudResult]:
        """Analyze multiple leads for fraud."""
        import asyncio
        tasks = [
            self.analyze_lead(lead, existing_leads=existing_leads)
            for lead in leads
        ]
        return await asyncio.gather(*tasks)

    def _score_email(self, email_result: Dict) -> float:
        """Convert email validation result to fraud score."""
        score = 0.0

        if not email_result.get("is_valid"):
            score = 0.9
        elif email_result.get("is_disposable"):
            score = 0.8
        elif not email_result.get("has_mx_record"):
            score = 0.7
        elif email_result.get("is_role_based"):
            score += 0.2

        # Email quality score inverse
        email_quality = email_result.get("score", 1.0)
        score = max(score, 1.0 - email_quality)

        return min(1.0, score)

    def _analyze_content(self, lead: Dict) -> Dict:
        """Analyze lead content for spam patterns."""
        score = 0.0
        flags = []

        # Check name patterns
        first_name = (lead.get("first_name") or "").strip()
        last_name = (lead.get("last_name") or "").strip()
        full_name = f"{first_name} {last_name}".strip().lower()

        for pattern in SPAM_NAME_PATTERNS:
            if re.match(pattern, full_name, re.I):
                score += 0.4
                flags.append("spam_name_pattern")
                break

        # Gibberish detection (consonant clusters, no vowels)
        if full_name and len(full_name) > 3:
            vowel_ratio = len(re.findall(r'[aeiou]', full_name)) / len(full_name)
            if vowel_ratio < 0.1:
                score += 0.3
                flags.append("gibberish_name")

        # All caps
        if first_name and first_name == first_name.upper() and len(first_name) > 2:
            score += 0.1
            flags.append("all_caps_name")

        # Company spam patterns
        company = (lead.get("company_name") or "").strip().lower()
        for pattern in SPAM_COMPANY_PATTERNS:
            if re.match(pattern, company, re.I):
                score += 0.2
                flags.append("spam_company_pattern")
                break

        # Suspicious URL in fields
        text_fields = str(lead.get("custom_fields", ""))
        if re.search(r'https?://\S+', text_fields):
            score += 0.2
            flags.append("url_in_fields")

        # Phone number validation
        phone = lead.get("phone", "")
        if phone:
            digits_only = re.sub(r'[^\d]', '', phone)
            if digits_only and (len(digits_only) < 7 or len(set(digits_only)) <= 2):
                score += 0.3
                flags.append("suspicious_phone")

        # Suspicious TLD in email domain
        email = lead.get("email", "")
        if email and "@" in email:
            domain = email.split("@")[1]
            for tld in SUSPICIOUS_TLDS:
                if domain.endswith(tld):
                    score += 0.15
                    flags.append("suspicious_tld")
                    break

        return {"score": min(1.0, score), "flags": flags}

    def _detect_bot(self, metadata: Dict) -> Dict:
        """Detect bot submissions from form metadata."""
        score = 0.0
        flags = []

        # Honeypot check (hidden field was filled)
        if metadata.get("honeypot_filled"):
            score = 0.95
            flags.append("honeypot_triggered")
            return {"score": score, "flags": flags}

        # Form submission time (bots submit instantly)
        submit_time_ms = metadata.get("form_submit_time_ms", 5000)
        if submit_time_ms < 1000:  # Less than 1 second
            score += 0.6
            flags.append("instant_submission")
        elif submit_time_ms < 2000:  # Less than 2 seconds
            score += 0.3
            flags.append("fast_submission")

        # Missing or suspicious user agent
        user_agent = metadata.get("user_agent", "")
        if not user_agent:
            score += 0.3
            flags.append("no_user_agent")
        elif any(bot in user_agent.lower() for bot in ["bot", "spider", "crawl", "curl", "wget", "python"]):
            score += 0.5
            flags.append("bot_user_agent")

        # JavaScript disabled (most bots don't run JS)
        if metadata.get("js_disabled"):
            score += 0.3
            flags.append("no_javascript")

        # No referrer (direct POST without loading page)
        if not metadata.get("referrer") and metadata.get("method") == "POST":
            score += 0.2
            flags.append("no_referrer")

        # Headless browser detection
        if metadata.get("is_headless"):
            score += 0.4
            flags.append("headless_browser")

        return {"score": min(1.0, score), "flags": flags}

    def _check_rate_limits(self, metadata: Dict, lead: Dict) -> Dict:
        """Check for rate limit violations (rapid-fire submissions)."""
        score = 0.0
        flags = []
        now = datetime.utcnow()
        window = timedelta(minutes=10)

        # IP-based rate limiting
        ip = metadata.get("ip_address", "")
        if ip:
            if ip not in self._ip_submissions:
                self._ip_submissions[ip] = []
            # Clean old entries
            self._ip_submissions[ip] = [
                t for t in self._ip_submissions[ip] if now - t < window
            ]
            self._ip_submissions[ip].append(now)

            submissions_count = len(self._ip_submissions[ip])
            if submissions_count > 10:
                score += 0.8
                flags.append(f"ip_rate_limit:{submissions_count}")
            elif submissions_count > 5:
                score += 0.4
                flags.append(f"ip_high_frequency:{submissions_count}")

        # Domain-based rate limiting (same email domain)
        email = lead.get("email", "")
        if email and "@" in email:
            domain = email.split("@")[1]
            if domain not in self._domain_submissions:
                self._domain_submissions[domain] = []
            self._domain_submissions[domain] = [
                t for t in self._domain_submissions[domain] if now - t < window
            ]
            self._domain_submissions[domain].append(now)

            domain_count = len(self._domain_submissions[domain])
            if domain_count > 20:
                score += 0.5
                flags.append(f"domain_rate_limit:{domain_count}")

        return {"score": min(1.0, score), "flags": flags}

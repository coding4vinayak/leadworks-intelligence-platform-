"""Email validation - comprehensive email address verification."""
import re
import asyncio
from typing import Dict, List, Optional, Set
import structlog

logger = structlog.get_logger()

# Known disposable/temporary email domains
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwaway.email",
    "yopmail.com", "trashmail.com", "10minutemail.com", "temp-mail.org",
    "fakeinbox.com", "sharklasers.com", "grr.la", "guerrillamailblock.com",
    "disposableemailaddresses.emailmiser.com", "maildrop.cc", "dispostable.com",
    "getnada.com", "emailondeck.com", "tempail.com", "mohmal.com",
    "burnermail.io", "guerrillamail.info", "tempr.email", "spam4.me",
    "spamgourmet.com", "mintemail.com", "mailnesia.com", "mailcatch.com",
}

# Free email providers (not necessarily bad, but lower B2B value)
FREE_EMAIL_PROVIDERS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "mail.com", "protonmail.com", "zoho.com", "yandex.com",
    "gmx.com", "live.com", "msn.com", "me.com", "inbox.com",
    "fastmail.com", "tutanota.com",
}

# Role-based emails (not a real person)
ROLE_BASED_PREFIXES = {
    "admin", "info", "support", "sales", "marketing", "contact", "hello",
    "help", "team", "office", "hr", "billing", "noreply", "no-reply",
    "webmaster", "postmaster", "abuse", "security", "press", "media",
    "careers", "jobs", "legal", "compliance", "privacy", "feedback",
}

EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)


class EmailValidator:
    """
    Multi-layer email validation:
    1. Syntax check (RFC 5322 format)
    2. Disposable domain detection
    3. Free email provider detection
    4. Role-based email detection
    5. MX record verification
    6. SMTP mailbox verification (deliverability check)
    7. Typo detection (did you mean gmail.com?)
    """

    def __init__(self, check_mx: bool = True, check_smtp: bool = False):
        self.check_mx = check_mx
        self.check_smtp = check_smtp

    async def validate(self, email: str) -> Dict[str, any]:
        """
        Validate an email address comprehensively.

        Returns:
            {
                "email": str,
                "is_valid": bool,
                "score": float (0-1, 1 = perfect),
                "is_deliverable": bool,
                "is_disposable": bool,
                "is_free_provider": bool,
                "is_role_based": bool,
                "has_mx_record": bool,
                "suggested_correction": str or None,
                "flags": ["flag1", "flag2"],
                "risk_level": "low|medium|high|critical"
            }
        """
        email = email.strip().lower()

        result = {
            "email": email,
            "is_valid": True,
            "score": 1.0,
            "is_deliverable": True,
            "is_disposable": False,
            "is_free_provider": False,
            "is_role_based": False,
            "has_mx_record": True,
            "suggested_correction": None,
            "flags": [],
            "risk_level": "low",
        }

        # 1. Syntax check
        if not EMAIL_REGEX.match(email):
            result["is_valid"] = False
            result["score"] = 0.0
            result["flags"].append("invalid_syntax")
            result["risk_level"] = "critical"
            return result

        local_part, domain = email.rsplit("@", 1)

        # 2. Check for common typos
        correction = self._check_typos(domain)
        if correction:
            result["suggested_correction"] = f"{local_part}@{correction}"
            result["flags"].append("possible_typo")
            result["score"] -= 0.1

        # 3. Disposable domain check
        if domain in DISPOSABLE_DOMAINS:
            result["is_disposable"] = True
            result["flags"].append("disposable_domain")
            result["score"] -= 0.5
            result["risk_level"] = "high"

        # 4. Free email provider check
        if domain in FREE_EMAIL_PROVIDERS:
            result["is_free_provider"] = True
            result["flags"].append("free_email_provider")
            result["score"] -= 0.15

        # 5. Role-based check
        prefix = local_part.split(".")[0].split("_")[0].split("-")[0]
        if prefix in ROLE_BASED_PREFIXES:
            result["is_role_based"] = True
            result["flags"].append("role_based_email")
            result["score"] -= 0.2

        # 6. Suspicious patterns
        if len(local_part) < 2:
            result["flags"].append("too_short")
            result["score"] -= 0.1
        if re.match(r'^[0-9]+$', local_part):
            result["flags"].append("numeric_only")
            result["score"] -= 0.2
        if len(re.findall(r'[0-9]', local_part)) > 5:
            result["flags"].append("excessive_numbers")
            result["score"] -= 0.15
        if '..' in email or '--' in email or '__' in email:
            result["flags"].append("suspicious_pattern")
            result["score"] -= 0.1

        # 7. MX record check
        if self.check_mx:
            has_mx = await self._check_mx_record(domain)
            result["has_mx_record"] = has_mx
            if not has_mx:
                result["is_deliverable"] = False
                result["flags"].append("no_mx_record")
                result["score"] -= 0.4
                result["risk_level"] = "high"

        # 8. SMTP verification (optional, slow)
        if self.check_smtp and result["has_mx_record"]:
            is_deliverable = await self._smtp_verify(email, domain)
            result["is_deliverable"] = is_deliverable
            if not is_deliverable:
                result["flags"].append("smtp_undeliverable")
                result["score"] -= 0.3

        # Clamp score
        result["score"] = max(0.0, min(1.0, result["score"]))

        # Final risk assessment
        if result["score"] < 0.3:
            result["risk_level"] = "critical"
        elif result["score"] < 0.5:
            result["risk_level"] = "high"
        elif result["score"] < 0.7:
            result["risk_level"] = "medium"
        else:
            result["risk_level"] = "low"

        return result

    async def validate_batch(self, emails: List[str]) -> List[Dict]:
        """Validate multiple emails concurrently."""
        tasks = [self.validate(email) for email in emails]
        return await asyncio.gather(*tasks)

    def _check_typos(self, domain: str) -> Optional[str]:
        """Detect common email domain typos."""
        typo_map = {
            "gmial.com": "gmail.com", "gmal.com": "gmail.com",
            "gmai.com": "gmail.com", "gamil.com": "gmail.com",
            "gnail.com": "gmail.com", "gmail.con": "gmail.com",
            "yahooo.com": "yahoo.com", "yaho.com": "yahoo.com",
            "yahoo.con": "yahoo.com",
            "hotmal.com": "hotmail.com", "hotmai.com": "hotmail.com",
            "hotmail.con": "hotmail.com",
            "outloo.com": "outlook.com", "outlok.com": "outlook.com",
            "outlook.con": "outlook.com",
        }
        return typo_map.get(domain)

    async def _check_mx_record(self, domain: str) -> bool:
        """Check if domain has MX records (can receive email)."""
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, 'MX')
            return len(answers) > 0
        except Exception:
            # If dns.resolver not available, use dig via subprocess
            try:
                proc = await asyncio.create_subprocess_exec(
                    'dig', '+short', 'MX', domain,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                return bool(stdout.strip())
            except:
                return True  # Assume valid if we can't check

    async def _smtp_verify(self, email: str, domain: str) -> bool:
        """SMTP-level mailbox verification (resource intensive)."""
        # This is a simplified check - in production use a service
        try:
            import dns.resolver
            mx_records = dns.resolver.resolve(domain, 'MX')
            mx_host = str(mx_records[0].exchange).rstrip('.')

            import aiosmtplib
            smtp = aiosmtplib.SMTP(hostname=mx_host, port=25, timeout=10)
            await smtp.connect()
            await smtp.helo("leadworks.io")
            code, _ = await smtp.mail("verify@leadworks.io")
            code, _ = await smtp.rcpt(email)
            await smtp.quit()
            return code == 250
        except:
            return True  # Can't verify, assume ok

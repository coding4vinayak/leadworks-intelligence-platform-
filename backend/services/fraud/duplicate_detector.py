"""Duplicate detection - finds and merges duplicate leads."""
import re
from typing import Any, Dict, List, Optional, Tuple
from difflib import SequenceMatcher
import structlog

logger = structlog.get_logger()


class DuplicateDetector:
    """
    Multi-strategy duplicate detection:
    1. Exact email match
    2. Fuzzy name + company match
    3. Phone number normalization + match
    4. LinkedIn URL match
    5. Domain + name combination match

    Provides:
    - Confidence scoring for each match
    - Merge suggestions (which fields to keep)
    - Batch dedup on import
    """

    def __init__(self, threshold: float = 0.75):
        """
        Args:
            threshold: Minimum similarity score to flag as duplicate (0-1)
        """
        self.threshold = threshold

    def find_duplicates(
        self,
        new_lead: Dict[str, Any],
        existing_leads: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Find potential duplicates for a new lead.

        Returns list of matches with confidence scores.
        """
        matches = []

        for existing in existing_leads:
            similarity = self._calculate_similarity(new_lead, existing)

            if similarity["total_score"] >= self.threshold:
                matches.append({
                    "existing_lead": existing,
                    "confidence": similarity["total_score"],
                    "match_reasons": similarity["reasons"],
                    "suggested_action": self._suggest_action(similarity),
                    "merge_strategy": self._suggest_merge(new_lead, existing),
                })

        # Sort by confidence (highest first)
        matches.sort(key=lambda x: x["confidence"], reverse=True)
        return matches

    def batch_dedup(
        self,
        leads: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Deduplicate a batch of leads (e.g., during CSV import).

        Returns:
            {
                "unique_leads": [...],
                "duplicates": [{"lead": ..., "duplicate_of_index": int}],
                "stats": {"total": N, "unique": N, "duplicates": N}
            }
        """
        unique: List[Dict] = []
        duplicates = []

        for i, lead in enumerate(leads):
            is_dup = False
            for j, existing in enumerate(unique):
                similarity = self._calculate_similarity(lead, existing)
                if similarity["total_score"] >= self.threshold:
                    duplicates.append({
                        "lead": lead,
                        "duplicate_of_index": j,
                        "confidence": similarity["total_score"],
                        "reasons": similarity["reasons"],
                    })
                    is_dup = True
                    break

            if not is_dup:
                unique.append(lead)

        return {
            "unique_leads": unique,
            "duplicates": duplicates,
            "stats": {
                "total": len(leads),
                "unique": len(unique),
                "duplicates": len(duplicates),
            },
        }

    def _calculate_similarity(self, lead_a: Dict, lead_b: Dict) -> Dict:
        """Calculate overall similarity between two leads."""
        scores = []
        reasons = []

        # 1. Email exact match (strongest signal)
        email_a = (lead_a.get("email") or "").lower().strip()
        email_b = (lead_b.get("email") or "").lower().strip()
        if email_a and email_b:
            if email_a == email_b:
                scores.append(1.0)
                reasons.append("exact_email_match")
            else:
                # Check email similarity (typos)
                email_sim = SequenceMatcher(None, email_a, email_b).ratio()
                if email_sim > 0.9:
                    scores.append(0.8)
                    reasons.append("similar_email")

        # 2. Phone number match
        phone_a = self._normalize_phone(lead_a.get("phone", ""))
        phone_b = self._normalize_phone(lead_b.get("phone", ""))
        if phone_a and phone_b and phone_a == phone_b:
            scores.append(0.9)
            reasons.append("phone_match")

        # 3. LinkedIn URL match
        linkedin_a = (lead_a.get("linkedin_url") or "").lower().strip().rstrip("/")
        linkedin_b = (lead_b.get("linkedin_url") or "").lower().strip().rstrip("/")
        if linkedin_a and linkedin_b and linkedin_a == linkedin_b:
            scores.append(0.95)
            reasons.append("linkedin_match")

        # 4. Name + Company fuzzy match
        name_a = f"{lead_a.get('first_name', '')} {lead_a.get('last_name', '')}".strip().lower()
        name_b = f"{lead_b.get('first_name', '')} {lead_b.get('last_name', '')}".strip().lower()
        company_a = (lead_a.get("company_name") or "").lower().strip()
        company_b = (lead_b.get("company_name") or "").lower().strip()

        if name_a and name_b:
            name_sim = SequenceMatcher(None, name_a, name_b).ratio()
            if name_sim > 0.85:
                if company_a and company_b:
                    company_sim = SequenceMatcher(None, company_a, company_b).ratio()
                    if company_sim > 0.8:
                        combined = (name_sim + company_sim) / 2
                        scores.append(combined)
                        reasons.append("name_company_match")
                elif name_sim > 0.95:
                    scores.append(name_sim * 0.7)
                    reasons.append("name_match_no_company")

        # 5. Domain + last name match
        if email_a and email_b:
            domain_a = email_a.split("@")[-1] if "@" in email_a else ""
            domain_b = email_b.split("@")[-1] if "@" in email_b else ""
            last_a = (lead_a.get("last_name") or "").lower()
            last_b = (lead_b.get("last_name") or "").lower()
            if domain_a and domain_b and domain_a == domain_b and last_a and last_b:
                if SequenceMatcher(None, last_a, last_b).ratio() > 0.85:
                    scores.append(0.7)
                    reasons.append("same_domain_similar_name")

        # Calculate total score
        total_score = max(scores) if scores else 0.0

        return {
            "total_score": round(total_score, 3),
            "individual_scores": scores,
            "reasons": reasons,
        }

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number for comparison."""
        if not phone:
            return ""
        # Remove all non-digit characters except leading +
        normalized = re.sub(r'[^\d+]', '', phone)
        # Remove leading country code variations
        if normalized.startswith("+1") and len(normalized) == 12:
            normalized = normalized[2:]
        elif normalized.startswith("1") and len(normalized) == 11:
            normalized = normalized[1:]
        return normalized

    def _suggest_action(self, similarity: Dict) -> str:
        """Suggest what to do with a duplicate."""
        score = similarity["total_score"]
        if score >= 0.95:
            return "auto_merge"
        elif score >= 0.85:
            return "review_and_merge"
        elif score >= 0.75:
            return "flag_for_review"
        return "ignore"

    def _suggest_merge(self, new_lead: Dict, existing: Dict) -> Dict[str, str]:
        """
        Suggest which fields to keep when merging.
        Strategy: Keep the most complete/recent data.
        """
        merge = {}
        all_fields = set(list(new_lead.keys()) + list(existing.keys()))

        for field in all_fields:
            new_val = new_lead.get(field)
            existing_val = existing.get(field)

            if new_val and not existing_val:
                merge[field] = "use_new"
            elif existing_val and not new_val:
                merge[field] = "keep_existing"
            elif new_val and existing_val:
                # If values differ, prefer the longer/more detailed one
                if isinstance(new_val, str) and isinstance(existing_val, str):
                    if len(str(new_val)) > len(str(existing_val)):
                        merge[field] = "use_new"
                    else:
                        merge[field] = "keep_existing"
                else:
                    merge[field] = "keep_existing"

        return merge

"""AI-powered enrichment using OpenAI for intelligent data inference."""
import json
from typing import Any, Dict, List, Optional
import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger()


class AIEnrichment:
    """
    Uses OpenAI GPT-4 for intelligent lead enrichment:
    - Infer job seniority from title
    - Categorize industry from company description
    - Generate personalized outreach suggestions
    - Summarize company from website content
    - Detect buying intent signals
    - Suggest ICP (Ideal Customer Profile) match score
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
        self.base_url = "https://api.openai.com/v1"

    async def _call_openai(self, messages: List[Dict], temperature: float = 0.3) -> Optional[str]:
        """Make an OpenAI API call."""
        if not self.api_key:
            logger.warning("openai_api_key_not_set")
            return None

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": 1000,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.error("openai_error", status=response.status_code)
                    return None

        except Exception as e:
            logger.error("openai_call_failed", error=str(e))
            return None

    async def analyze_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive AI analysis of a lead.
        Returns structured insights about seniority, intent, ICP fit, etc.
        """
        prompt = f"""Analyze this B2B lead and provide structured insights.

Lead Data:
- Name: {lead_data.get('first_name', '')} {lead_data.get('last_name', '')}
- Job Title: {lead_data.get('job_title', 'Unknown')}
- Company: {lead_data.get('company_name', 'Unknown')}
- Industry: {lead_data.get('industry', 'Unknown')}
- Company Size: {lead_data.get('employee_count', 'Unknown')}
- Location: {lead_data.get('city', '')} {lead_data.get('country', '')}
- Website: {lead_data.get('website', '')}
- Tech Stack: {lead_data.get('tech_stack', [])}

Respond in JSON format:
{{
    "seniority_level": "c_level|vp|director|manager|individual_contributor|intern",
    "department": "engineering|sales|marketing|finance|hr|operations|product|other",
    "decision_maker": true/false,
    "budget_authority": "high|medium|low|unknown",
    "industry_category": "...",
    "company_size_category": "startup|smb|mid_market|enterprise",
    "buying_intent_signals": ["signal1", "signal2"],
    "recommended_approach": "brief personalized outreach recommendation",
    "icp_fit_score": 0-100,
    "key_talking_points": ["point1", "point2", "point3"]
}}"""

        messages = [
            {"role": "system", "content": "You are a B2B sales intelligence analyst. Provide accurate, actionable insights about leads. Always respond in valid JSON."},
            {"role": "user", "content": prompt},
        ]

        response = await self._call_openai(messages)
        if response:
            try:
                # Clean response (remove markdown code blocks if present)
                cleaned = response.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1]
                if cleaned.endswith("```"):
                    cleaned = cleaned.rsplit("```", 1)[0]
                return json.loads(cleaned)
            except json.JSONDecodeError:
                logger.warning("ai_response_parse_failed", response=response[:200])
        return {}

    async def generate_outreach_message(
        self,
        lead_data: Dict[str, Any],
        channel: str = "email",
        tone: str = "professional",
        context: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """
        Generate personalized outreach message for a lead.

        Args:
            lead_data: Lead information
            channel: "email", "linkedin", "whatsapp"
            tone: "professional", "casual", "direct"
            context: Additional context (e.g., product info, pain points)
        """
        prompt = f"""Generate a personalized {channel} outreach message for this lead.

Lead:
- Name: {lead_data.get('first_name', '')} {lead_data.get('last_name', '')}
- Title: {lead_data.get('job_title', '')}
- Company: {lead_data.get('company_name', '')}
- Industry: {lead_data.get('industry', '')}

Tone: {tone}
{f'Context: {context}' if context else ''}

Respond in JSON:
{{
    "subject": "email subject line (if email)",
    "message": "the outreach message",
    "follow_up": "suggested follow-up message after 3 days"
}}"""

        messages = [
            {"role": "system", "content": "You are an expert B2B sales copywriter. Write concise, personalized messages that get responses. No spam. Always respond in valid JSON."},
            {"role": "user", "content": prompt},
        ]

        response = await self._call_openai(messages, temperature=0.7)
        if response:
            try:
                cleaned = response.strip().strip("`").strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                return json.loads(cleaned)
            except:
                return {"message": response}
        return None

    async def infer_company_data(self, company_name: str, website_content: str = "") -> Dict[str, Any]:
        """
        Infer company data from name and/or website content.
        """
        prompt = f"""Based on this company information, provide structured data.

Company: {company_name}
Website content (first 2000 chars): {website_content[:2000]}

Respond in JSON:
{{
    "industry": "...",
    "sub_industry": "...",
    "employee_range": "1-10|11-50|51-200|201-500|501-1000|1000+",
    "company_type": "startup|smb|mid_market|enterprise|agency|consultancy",
    "likely_tech_buyer": true/false,
    "business_model": "saas|marketplace|services|ecommerce|manufacturing|other",
    "target_market": "b2b|b2c|b2b2c",
    "keywords": ["keyword1", "keyword2", "keyword3"]
}}"""

        messages = [
            {"role": "system", "content": "You are a business intelligence analyst. Provide accurate company categorization. Always respond in valid JSON."},
            {"role": "user", "content": prompt},
        ]

        response = await self._call_openai(messages)
        if response:
            try:
                cleaned = response.strip().strip("`").strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                return json.loads(cleaned)
            except:
                pass
        return {}

    async def detect_intent_signals(self, lead_activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze lead activity to detect buying intent signals.
        """
        prompt = f"""Analyze this lead's activity and identify buying intent signals.

Activity Data:
- Page visits: {lead_activity.get('page_visits', 0)}
- Pages visited: {lead_activity.get('pages', [])}
- Emails opened: {lead_activity.get('emails_opened', 0)}
- Emails clicked: {lead_activity.get('emails_clicked', 0)}
- Form submissions: {lead_activity.get('form_submissions', 0)}
- Content downloads: {lead_activity.get('downloads', [])}
- Time on site: {lead_activity.get('time_on_site_minutes', 0)} minutes
- Visited pricing page: {lead_activity.get('visited_pricing', False)}
- Visited demo page: {lead_activity.get('visited_demo', False)}

Respond in JSON:
{{
    "intent_level": "high|medium|low|none",
    "intent_score": 0-100,
    "signals": ["signal1", "signal2"],
    "recommended_action": "what should sales do next",
    "urgency": "hot|warm|cold",
    "likely_stage": "awareness|consideration|decision"
}}"""

        messages = [
            {"role": "system", "content": "You are a sales intelligence AI. Identify buying intent from behavioral signals. Always respond in valid JSON."},
            {"role": "user", "content": prompt},
        ]

        response = await self._call_openai(messages)
        if response:
            try:
                cleaned = response.strip().strip("`").strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                return json.loads(cleaned)
            except:
                pass
        return {}

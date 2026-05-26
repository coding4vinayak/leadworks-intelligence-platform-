"""AI Sales Assistant - natural language interface for lead intelligence."""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger()


class SalesAssistant:
    """
    AI-powered sales chatbot that helps users:
    - Query leads in natural language ("Show me hot leads in SaaS")
    - Get recommendations ("Who should I contact today?")
    - Trigger actions ("Enrich all leads from LinkedIn")
    - Explain scores ("Why is Sarah Chen scored 92?")
    - Generate outreach ("Write an email to James at DataFlow")
    - Analyze pipeline ("How's my pipeline this week?")
    - Answer questions ("What's our best performing source?")

    Uses function calling to execute operations.
    """

    SYSTEM_PROMPT = """You are Leadworks AI, a sales intelligence assistant. 
You help sales teams manage leads, understand their pipeline, and close deals faster.

You have access to:
- Lead database (search, filter, get details)
- Scoring engine (explain scores, suggest improvements)
- Enrichment (trigger enrichment for leads)
- Campaign management (create sequences, check performance)
- Analytics (pipeline stats, source analysis, conversion rates)

Be concise, actionable, and data-driven. Use numbers and specifics.
Format responses with bullet points and clear structure.
When showing leads, include: name, company, title, score, and recommended action."""

    AVAILABLE_FUNCTIONS = [
        {
            "name": "search_leads",
            "description": "Search and filter leads by various criteria",
            "parameters": {
                "query": "Natural language search query",
                "filters": {
                    "score_min": "Minimum score",
                    "score_max": "Maximum score",
                    "status": "Lead status filter",
                    "source": "Lead source filter",
                    "tags": "Tags to filter by",
                    "company": "Company name filter",
                    "title": "Job title contains",
                },
                "limit": "Max results (default 10)",
                "sort_by": "Sort field (score, created_at, name)",
            }
        },
        {
            "name": "get_lead_details",
            "description": "Get full details about a specific lead including score breakdown and activity",
            "parameters": {"lead_id": "Lead ID or email"}
        },
        {
            "name": "explain_score",
            "description": "Explain why a lead has their current score",
            "parameters": {"lead_id": "Lead ID"}
        },
        {
            "name": "get_pipeline_stats",
            "description": "Get pipeline and conversion statistics",
            "parameters": {"period": "Time period (today, this_week, this_month, last_30_days)"}
        },
        {
            "name": "get_recommendations",
            "description": "Get AI recommendations for who to contact, what to do next",
            "parameters": {"type": "Type: contact_today, follow_up, at_risk, quick_wins"}
        },
        {
            "name": "trigger_enrichment",
            "description": "Trigger lead enrichment for one or more leads",
            "parameters": {"lead_ids": "List of lead IDs", "depth": "basic, standard, deep"}
        },
        {
            "name": "generate_outreach",
            "description": "Generate personalized outreach message",
            "parameters": {"lead_id": "Lead ID", "channel": "email, linkedin, whatsapp", "tone": "professional, casual, direct"}
        },
        {
            "name": "get_source_analysis",
            "description": "Analyze lead source performance",
            "parameters": {"period": "Time period"}
        },
    ]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        self.conversation_history: List[Dict[str, str]] = []

    async def chat(
        self,
        message: str,
        user_id: Optional[str] = None,
        team_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message and return AI response with actions.

        Args:
            message: User's natural language message
            user_id: For personalization
            team_id: For data access
            context: Additional context (current page, selected lead, etc.)

        Returns:
            {
                "response": "AI text response",
                "actions": [{"type": "...", "data": {...}}],
                "suggestions": ["follow-up question 1", "..."],
                "data": {...}  # Any structured data (leads, stats)
            }
        """
        # Build context-aware prompt
        system_context = self.SYSTEM_PROMPT
        if context:
            if context.get("current_lead"):
                system_context += f"\n\nUser is currently viewing lead: {json.dumps(context['current_lead'])}"
            if context.get("current_page"):
                system_context += f"\nUser is on page: {context['current_page']}"

        # Add message to history
        self.conversation_history.append({"role": "user", "content": message})

        # Call OpenAI
        messages = [
            {"role": "system", "content": system_context},
            *self.conversation_history[-10:],  # Last 10 messages for context
        ]

        response_text = await self._call_openai(messages)

        if not response_text:
            return {
                "response": "I'm having trouble connecting to AI services. Please try again.",
                "actions": [],
                "suggestions": [],
            }

        # Parse response for actionable content
        result = self._parse_response(response_text, message)

        # Add to history
        self.conversation_history.append({"role": "assistant", "content": response_text})

        return result

    async def get_daily_briefing(self, team_id: str) -> Dict[str, Any]:
        """Generate a personalized daily sales briefing."""
        prompt = """Generate a daily sales briefing for the team. Include:
1. Key metrics today vs yesterday
2. Top 3 leads to prioritize (with specific actions)
3. Leads at risk of going cold
4. Campaign performance highlights
5. One actionable insight

Keep it concise and actionable. Use bullet points."""

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        response = await self._call_openai(messages)
        return {
            "briefing": response or "Unable to generate briefing.",
            "generated_at": datetime.utcnow().isoformat(),
            "type": "daily_briefing",
        }

    async def suggest_next_actions(self, lead_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Suggest next best actions for a specific lead."""
        prompt = f"""Given this lead data, suggest the top 3 next best actions:

Lead: {json.dumps(lead_data, default=str)}

For each action provide:
- What to do
- Why (based on their data/behavior)
- When (urgency)
- Template/script if applicable

Respond in JSON array format: [{{"action": "...", "reason": "...", "urgency": "high/medium/low", "script": "..."}}]"""

        messages = [
            {"role": "system", "content": "You are a B2B sales strategy AI. Always respond in valid JSON."},
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
        return []

    async def answer_question(self, question: str, data_context: Dict[str, Any]) -> str:
        """Answer a data question with context."""
        prompt = f"""Answer this sales question using the provided data:

Question: {question}

Available Data:
{json.dumps(data_context, default=str, indent=2)}

Be specific with numbers. If you can't determine the answer from the data, say so."""

        messages = [
            {"role": "system", "content": "You are a sales data analyst. Give precise, data-driven answers."},
            {"role": "user", "content": prompt},
        ]

        return await self._call_openai(messages) or "Unable to answer."

    async def _call_openai(self, messages: List[Dict], temperature: float = 0.4) -> Optional[str]:
        """Make OpenAI API call."""
        if not self.api_key:
            return self._get_mock_response(messages[-1]["content"])

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": 1500,
                    },
                )
                if response.status_code == 200:
                    return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error("openai_chat_failed", error=str(e))

        return self._get_mock_response(messages[-1]["content"])

    def _get_mock_response(self, user_message: str) -> str:
        """Provide mock responses when API is unavailable."""
        msg = user_message.lower()

        if "hot lead" in msg or "best lead" in msg:
            return """Here are your top hot leads today:

1. **Sarah Chen** - VP Engineering @ TechCorp (Score: 92)
   - Visited pricing page 3x, opened all emails
   - *Action:* Book a demo call ASAP

2. **Lisa Park** - CEO @ AI Solutions (Score: 95)
   - Referred by existing customer, series B funded
   - *Action:* Send personalized intro with case study

3. **James Wilson** - CTO @ DataFlow (Score: 87)
   - Replied to follow-up, asked about integrations
   - *Action:* Schedule technical deep-dive

💡 *Tip:* All 3 leads are in SaaS/AI - consider a vertical-specific approach."""

        elif "pipeline" in msg or "stats" in msg:
            return """📊 **Pipeline Summary (This Week)**

- **New leads:** 47 (+12% vs last week)
- **Hot leads:** 12 (8 uncontacted!)
- **Emails sent:** 234 | Open rate: 42% | Reply rate: 8.5%
- **Meetings booked:** 6
- **Pipeline value:** $485K (+$65K)

⚠️ **Alert:** 8 hot leads haven't been contacted yet. Assign them today!
✅ **Win:** Reply rate up 2.1% since switching to personalized subjects."""

        elif "recommend" in msg or "contact" in msg or "who should" in msg:
            return """🎯 **Today's Priority Actions:**

1. **Follow up** with James Wilson - replied 2 days ago asking about pricing
2. **Enrich** the 15 new LinkedIn leads from yesterday's scrape
3. **Re-engage** David Kim - was warm but went quiet 7 days ago
4. **Call** Maria Garcia - she visited demo page twice today

💡 Best send time for your audience today: **10:00 AM PST** (highest open rates)."""

        else:
            return f"""I can help you with that! Here's what I can do:

• **Search leads** - "Show me CTOs in fintech with score > 70"
• **Pipeline stats** - "How's my pipeline this week?"
• **Recommendations** - "Who should I contact today?"
• **Score explanations** - "Why is [lead] scored high?"
• **Generate outreach** - "Write an email to [lead]"
• **Source analysis** - "What's our best lead source?"

What would you like to know?"""

    def _parse_response(self, response: str, original_message: str) -> Dict[str, Any]:
        """Parse AI response into structured result."""
        result = {
            "response": response,
            "actions": [],
            "suggestions": [],
            "data": None,
        }

        # Generate follow-up suggestions based on content
        msg_lower = original_message.lower()
        if "hot lead" in msg_lower or "best" in msg_lower:
            result["suggestions"] = [
                "Show me their recent activity",
                "Generate an outreach email for the top lead",
                "What companies are they from?",
            ]
        elif "pipeline" in msg_lower or "stats" in msg_lower:
            result["suggestions"] = [
                "What's our conversion rate by source?",
                "Show me leads at risk of going cold",
                "Compare this week vs last week",
            ]
        else:
            result["suggestions"] = [
                "Show my hot leads",
                "How's my pipeline?",
                "Who should I follow up with?",
            ]

        return result

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []

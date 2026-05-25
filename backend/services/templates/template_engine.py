"""Email template engine with variable substitution, conditional blocks, and previews."""
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4
import structlog

logger = structlog.get_logger()


@dataclass
class EmailTemplate:
    """Email template with content and metadata."""
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    name: str = ""
    category: str = "outreach"  # outreach, nurture, follow_up, re_engagement, transactional
    subject: str = ""
    body_html: str = ""
    body_text: str = ""
    variables: List[str] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    usage_count: int = 0
    # Performance metrics
    avg_open_rate: float = 0.0
    avg_reply_rate: float = 0.0
    tags: List[str] = field(default_factory=list)


# Pre-built templates
DEFAULT_TEMPLATES = [
    EmailTemplate(
        id="welcome",
        name="Welcome / Introduction",
        category="outreach",
        subject="{{first_name}}, quick intro from {{sender_name}}",
        body_html="""<p>Hi {{first_name}},</p>
<p>I noticed you're {{job_title}} at {{company_name}} and thought I'd reach out.</p>
<p>We help companies like yours {{value_proposition}}.</p>
<p>Would you be open to a quick 15-min chat this week?</p>
<p>Best,<br>{{sender_name}}</p>""",
        variables=["first_name", "job_title", "company_name", "value_proposition", "sender_name"],
        tags=["cold_outreach", "intro"],
    ),
    EmailTemplate(
        id="follow_up_1",
        name="Follow-up #1 (3 days)",
        category="follow_up",
        subject="Re: {{previous_subject}}",
        body_html="""<p>Hi {{first_name}},</p>
<p>Just bumping this up in your inbox. I know things get busy!</p>
<p>{{personalized_hook}}</p>
<p>Would love to show you how we can help {{company_name}} {{specific_benefit}}.</p>
<p>Even a 10-min call would be enough to see if there's a fit.</p>
<p>{{sender_name}}</p>""",
        variables=["first_name", "previous_subject", "personalized_hook", "company_name", "specific_benefit", "sender_name"],
        tags=["follow_up"],
    ),
    EmailTemplate(
        id="follow_up_breakup",
        name="Breakup Email (Final Follow-up)",
        category="follow_up",
        subject="Should I close your file?",
        body_html="""<p>Hi {{first_name}},</p>
<p>I've reached out a few times and haven't heard back, so I'll assume the timing isn't right.</p>
<p>I'll close out your file on my end. If things change in the future, feel free to reach out anytime.</p>
<p>Wishing you and the team at {{company_name}} all the best!</p>
<p>{{sender_name}}</p>""",
        variables=["first_name", "company_name", "sender_name"],
        tags=["breakup", "final"],
    ),
    EmailTemplate(
        id="case_study",
        name="Case Study Share",
        category="nurture",
        subject="How {{case_study_company}} achieved {{result}}",
        body_html="""<p>Hi {{first_name}},</p>
<p>Thought you'd find this interesting - {{case_study_company}} (similar to {{company_name}}) recently achieved:</p>
<ul>
<li>{{result_1}}</li>
<li>{{result_2}}</li>
<li>{{result_3}}</li>
</ul>
<p>Here's the full case study: <a href="{{case_study_url}}">Read More</a></p>
<p>Happy to walk you through how this could work for {{company_name}}.</p>
<p>{{sender_name}}</p>""",
        variables=["first_name", "company_name", "case_study_company", "result", "result_1", "result_2", "result_3", "case_study_url", "sender_name"],
        tags=["case_study", "social_proof"],
    ),
    EmailTemplate(
        id="re_engagement",
        name="Re-engagement (We miss you)",
        category="re_engagement",
        subject="{{first_name}}, things have changed since we last spoke",
        body_html="""<p>Hi {{first_name}},</p>
<p>It's been a while since we connected, and a lot has changed on our end:</p>
<ul>
<li>{{update_1}}</li>
<li>{{update_2}}</li>
</ul>
<p>I think these updates would be particularly relevant for {{company_name}} given {{reason}}.</p>
<p>Worth a quick catch-up?</p>
<p>{{sender_name}}</p>""",
        variables=["first_name", "company_name", "update_1", "update_2", "reason", "sender_name"],
        tags=["re_engagement", "winback"],
    ),
    EmailTemplate(
        id="meeting_request",
        name="Meeting Request",
        category="outreach",
        subject="{{first_name}} - 15 min for {{topic}}?",
        body_html="""<p>Hi {{first_name}},</p>
<p>{{personalized_opening}}</p>
<p>I'd love to share how we're helping {{industry}} companies like {{similar_company}} with {{topic}}.</p>
<p>Would any of these work for a quick call?</p>
<ul>
<li>{{slot_1}}</li>
<li>{{slot_2}}</li>
<li>{{slot_3}}</li>
</ul>
<p>Or feel free to grab a time here: <a href="{{calendar_link}}">Book a Time</a></p>
<p>{{sender_name}}</p>""",
        variables=["first_name", "personalized_opening", "industry", "similar_company", "topic", "slot_1", "slot_2", "slot_3", "calendar_link", "sender_name"],
        tags=["meeting", "calendar"],
    ),
]

# Template variable regex: matches {{variable_name}} and {{ variable_name }}
VARIABLE_PATTERN = re.compile(r'\{\{\s*(\w+)\s*\}\}')

# Conditional block regex: {{#if condition}}...{{/if}}
CONDITIONAL_PATTERN = re.compile(r'\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}', re.DOTALL)


class TemplateEngine:
    """
    Email template engine.

    Features:
    - Variable substitution ({{first_name}})
    - Conditional blocks ({{#if has_phone}}Call: {{phone}}{{/if}})
    - Template library with categories
    - Performance tracking per template
    - A/B testing integration
    - Preview with sample data
    - Auto-detect variables from template
    - Smart fallbacks for missing variables
    """

    def __init__(self):
        self.templates: Dict[str, EmailTemplate] = {}
        # Load defaults
        for tmpl in DEFAULT_TEMPLATES:
            self.templates[tmpl.id] = tmpl

    def create_template(
        self,
        name: str,
        subject: str,
        body_html: str,
        category: str = "outreach",
        body_text: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> EmailTemplate:
        """Create a new email template."""
        # Auto-detect variables
        variables = self.extract_variables(subject + " " + body_html)

        template = EmailTemplate(
            name=name,
            category=category,
            subject=subject,
            body_html=body_html,
            body_text=body_text or self._html_to_text(body_html),
            variables=variables,
            tags=tags or [],
        )
        self.templates[template.id] = template
        return template

    def render(
        self,
        template_id: str,
        variables: Dict[str, Any],
        fallbacks: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Render a template with variable substitution.

        Args:
            template_id: Template to render
            variables: Variable values (e.g., {"first_name": "John"})
            fallbacks: Default values for missing variables

        Returns:
            {"subject": "...", "body_html": "...", "body_text": "..."}
        """
        template = self.templates.get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        defaults = fallbacks or {
            "first_name": "there",
            "company_name": "your company",
            "sender_name": "The Team",
            "job_title": "",
        }

        # Merge variables with defaults
        merged = {**defaults, **variables}

        # Render subject
        subject = self._substitute(template.subject, merged)

        # Process conditional blocks first
        body_html = self._process_conditionals(template.body_html, merged)
        # Then substitute variables
        body_html = self._substitute(body_html, merged)

        # Generate text version
        body_text = self._html_to_text(body_html)

        # Track usage
        template.usage_count += 1
        template.updated_at = datetime.utcnow()

        return {
            "subject": subject,
            "body_html": body_html,
            "body_text": body_text,
        }

    def preview(
        self,
        template_id: str,
        sample_lead: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Preview a template with sample data.

        Uses sample_lead data or generates realistic preview data.
        """
        sample = sample_lead or {
            "first_name": "Sarah",
            "last_name": "Chen",
            "email": "sarah@techcorp.io",
            "job_title": "VP Engineering",
            "company_name": "TechCorp",
            "industry": "SaaS",
            "city": "San Francisco",
            "sender_name": "Alex from Leadworks",
            "value_proposition": "reduce lead response time by 80%",
            "specific_benefit": "close deals 3x faster",
            "personalized_hook": "Saw your team just shipped that new API - impressive!",
            "previous_subject": "Quick question about your pipeline",
            "topic": "lead automation",
            "similar_company": "DataFlow",
            "calendar_link": "https://calendly.com/demo",
        }
        return self.render(template_id, sample)

    def extract_variables(self, text: str) -> List[str]:
        """Extract all variable names from template text."""
        variables = VARIABLE_PATTERN.findall(text)
        # Remove conditional keywords
        skip = {"if", "else", "endif"}
        return list(set(v for v in variables if v not in skip))

    def get_templates(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List templates with optional filtering."""
        results = []
        for tmpl in self.templates.values():
            if category and tmpl.category != category:
                continue
            if tags and not any(t in tmpl.tags for t in tags):
                continue
            results.append({
                "id": tmpl.id,
                "name": tmpl.name,
                "category": tmpl.category,
                "subject": tmpl.subject,
                "variables": tmpl.variables,
                "usage_count": tmpl.usage_count,
                "avg_open_rate": tmpl.avg_open_rate,
                "avg_reply_rate": tmpl.avg_reply_rate,
                "tags": tmpl.tags,
            })
        return results

    def _substitute(self, text: str, variables: Dict[str, Any]) -> str:
        """Replace {{variable}} placeholders with values."""
        def replacer(match):
            var_name = match.group(1).strip()
            value = variables.get(var_name, "")
            return str(value) if value else ""
        return VARIABLE_PATTERN.sub(replacer, text)

    def _process_conditionals(self, text: str, variables: Dict[str, Any]) -> str:
        """Process {{#if variable}}...{{/if}} blocks."""
        def replacer(match):
            condition_var = match.group(1)
            content = match.group(2)
            # Show content only if variable is truthy
            if variables.get(condition_var):
                return content
            return ""
        return CONDITIONAL_PATTERN.sub(replacer, text)

    def _html_to_text(self, html: str) -> str:
        """Simple HTML to plain text conversion."""
        import re
        text = re.sub(r'<br\s*/?>', '\n', html)
        text = re.sub(r'<li>', '- ', text)
        text = re.sub(r'</li>', '\n', text)
        text = re.sub(r'<p>', '', text)
        text = re.sub(r'</p>', '\n\n', text)
        text = re.sub(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', r'\2 (\1)', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

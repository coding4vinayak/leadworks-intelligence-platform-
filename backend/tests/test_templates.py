"""Tests for email template engine."""
import pytest
from backend.services.templates.template_engine import TemplateEngine


class TestTemplateEngine:
    """Test email template rendering."""

    def setup_method(self):
        self.engine = TemplateEngine()

    def test_list_default_templates(self):
        """Should have pre-built templates loaded."""
        templates = self.engine.get_templates()
        assert len(templates) >= 6
        assert any(t["id"] == "welcome" for t in templates)
        assert any(t["id"] == "follow_up_1" for t in templates)

    def test_render_welcome_template(self):
        """Render welcome template with variables."""
        result = self.engine.render(
            template_id="welcome",
            variables={
                "first_name": "Sarah",
                "job_title": "VP Engineering",
                "company_name": "TechCorp",
                "value_proposition": "reduce churn by 50%",
                "sender_name": "Alex",
            },
        )
        assert "Sarah" in result["subject"]
        assert "TechCorp" in result["body_html"]
        assert "reduce churn by 50%" in result["body_html"]
        assert "Alex" in result["body_html"]

    def test_render_with_fallbacks(self):
        """Missing variables should use fallbacks."""
        result = self.engine.render(
            template_id="welcome",
            variables={"company_name": "Acme"},
            fallbacks={"first_name": "there", "sender_name": "The Team"},
        )
        assert "there" in result["subject"]
        assert "The Team" in result["body_html"]

    def test_create_custom_template(self):
        """Create a new custom template."""
        template = self.engine.create_template(
            name="Custom Intro",
            subject="Hey {{first_name}}, quick thought",
            body_html="<p>Hi {{first_name}}, I work with {{industry}} companies.</p>",
            category="outreach",
            tags=["custom", "intro"],
        )
        assert template.id is not None
        assert "first_name" in template.variables
        assert "industry" in template.variables

    def test_preview_template(self):
        """Preview should render with sample data."""
        preview = self.engine.preview("welcome")
        assert "Sarah" in preview["subject"] or "there" in preview["subject"]
        assert preview["body_html"]  # Not empty
        assert preview["body_text"]  # Text version generated

    def test_extract_variables(self):
        """Should detect all {{variable}} placeholders."""
        text = "Hi {{first_name}}, your company {{company_name}} uses {{tech}}."
        variables = self.engine.extract_variables(text)
        assert "first_name" in variables
        assert "company_name" in variables
        assert "tech" in variables

    def test_html_to_text_conversion(self):
        """Should strip HTML and convert to readable text."""
        html = "<p>Hello <strong>World</strong></p><ul><li>Item 1</li><li>Item 2</li></ul>"
        text = self.engine._html_to_text(html)
        assert "Hello World" in text
        assert "- Item 1" in text
        assert "<p>" not in text

    def test_conditional_blocks(self):
        """{{#if var}}...{{/if}} should show/hide content."""
        template = self.engine.create_template(
            name="Conditional",
            subject="Test",
            body_html="<p>Hi {{first_name}}{{#if phone}}, call me at {{phone}}{{/if}}</p>",
        )
        # With phone
        result = self.engine.render(template.id, {"first_name": "John", "phone": "+1234567890"})
        assert "+1234567890" in result["body_html"]

        # Without phone
        result = self.engine.render(template.id, {"first_name": "John"})
        assert "call me" not in result["body_html"]

    def test_template_usage_tracking(self):
        """Usage count should increment on render."""
        initial_count = self.engine.templates["welcome"].usage_count
        self.engine.render("welcome", {"first_name": "Test", "sender_name": "X"})
        assert self.engine.templates["welcome"].usage_count == initial_count + 1

    def test_get_templates_by_category(self):
        """Filter templates by category."""
        outreach = self.engine.get_templates(category="outreach")
        follow_up = self.engine.get_templates(category="follow_up")
        assert all(t["category"] == "outreach" for t in outreach)
        assert all(t["category"] == "follow_up" for t in follow_up)

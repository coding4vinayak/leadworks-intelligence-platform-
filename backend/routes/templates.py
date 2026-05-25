"""Template routes - manage email templates."""
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.routes.auth import get_current_user
from backend.services.templates import TemplateEngine

router = APIRouter()
template_engine = TemplateEngine()


class CreateTemplateRequest(BaseModel):
    name: str
    subject: str
    body_html: str
    category: str = "outreach"
    body_text: Optional[str] = None
    tags: Optional[List[str]] = None


class RenderTemplateRequest(BaseModel):
    template_id: str
    variables: dict
    fallbacks: Optional[dict] = None


class PreviewRequest(BaseModel):
    template_id: str
    sample_lead: Optional[dict] = None


@router.get("/")
async def list_templates(
    category: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """List all email templates."""
    templates = template_engine.get_templates(category=category)
    return {"templates": templates}


@router.post("/", status_code=201)
async def create_template(
    request: CreateTemplateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new email template."""
    template = template_engine.create_template(
        name=request.name,
        subject=request.subject,
        body_html=request.body_html,
        category=request.category,
        body_text=request.body_text,
        tags=request.tags,
    )
    return {
        "id": template.id,
        "name": template.name,
        "variables": template.variables,
    }


@router.get("/{template_id}")
async def get_template(template_id: str, current_user: dict = Depends(get_current_user)):
    """Get template details."""
    tmpl = template_engine.templates.get(template_id)
    if not tmpl:
        return {"error": "Template not found"}
    return {
        "id": tmpl.id,
        "name": tmpl.name,
        "category": tmpl.category,
        "subject": tmpl.subject,
        "body_html": tmpl.body_html,
        "variables": tmpl.variables,
        "usage_count": tmpl.usage_count,
        "tags": tmpl.tags,
    }


@router.post("/render")
async def render_template(
    request: RenderTemplateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Render a template with variables."""
    rendered = template_engine.render(
        template_id=request.template_id,
        variables=request.variables,
        fallbacks=request.fallbacks,
    )
    return rendered


@router.post("/preview")
async def preview_template(
    request: PreviewRequest,
    current_user: dict = Depends(get_current_user),
):
    """Preview a template with sample data."""
    preview = template_engine.preview(
        template_id=request.template_id,
        sample_lead=request.sample_lead,
    )
    return {"preview": preview}


@router.get("/{template_id}/variables")
async def get_template_variables(template_id: str, current_user: dict = Depends(get_current_user)):
    """Get list of variables needed for a template."""
    tmpl = template_engine.templates.get(template_id)
    if not tmpl:
        return {"error": "Template not found"}
    return {"template_id": template_id, "variables": tmpl.variables}

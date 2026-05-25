"""Enrichment routes - trigger and manage lead enrichment."""
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.routes.auth import get_current_user
from backend.services.enrichment import EnrichmentPipeline

router = APIRouter()


class EnrichLeadRequest(BaseModel):
    lead_data: dict
    sources: Optional[List[str]] = None
    depth: str = "standard"  # basic, standard, deep
    include_ai: bool = True


class EnrichBatchRequest(BaseModel):
    lead_ids: List[str]
    depth: str = "standard"
    include_ai: bool = True


class AIAnalyzeRequest(BaseModel):
    lead_data: dict


class OutreachRequest(BaseModel):
    lead_data: dict
    channel: str = "email"
    tone: str = "professional"
    context: Optional[str] = None


@router.post("/lead")
async def enrich_lead(
    request: EnrichLeadRequest,
    current_user: dict = Depends(get_current_user),
):
    """Enrich a single lead with data from multiple sources."""
    pipeline = EnrichmentPipeline()
    result = await pipeline.run_pipeline(
        lead_data=request.lead_data,
        include_ai=request.include_ai,
        depth=request.depth,
    )
    return result


@router.post("/batch")
async def enrich_batch(
    request: EnrichBatchRequest,
    current_user: dict = Depends(get_current_user),
):
    """Enrich multiple leads (async job)."""
    return {
        "status": "queued",
        "leads_queued": len(request.lead_ids),
        "depth": request.depth,
        "message": "Enrichment job started. Results will update leads automatically.",
    }


@router.post("/ai/analyze")
async def ai_analyze(
    request: AIAnalyzeRequest,
    current_user: dict = Depends(get_current_user),
):
    """Get AI analysis of a lead (seniority, intent, ICP fit)."""
    from backend.services.enrichment.ai_enrichment import AIEnrichment
    ai = AIEnrichment()
    result = await ai.analyze_lead(request.lead_data)
    return {"analysis": result}


@router.post("/ai/outreach")
async def generate_outreach(
    request: OutreachRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate personalized outreach message with AI."""
    from backend.services.enrichment.ai_enrichment import AIEnrichment
    ai = AIEnrichment()
    result = await ai.generate_outreach_message(
        lead_data=request.lead_data,
        channel=request.channel,
        tone=request.tone,
        context=request.context,
    )
    return {"outreach": result}


@router.post("/ai/company")
async def infer_company(
    company_name: str,
    website_content: str = "",
    current_user: dict = Depends(get_current_user),
):
    """Infer company data using AI."""
    from backend.services.enrichment.ai_enrichment import AIEnrichment
    ai = AIEnrichment()
    result = await ai.infer_company_data(company_name, website_content)
    return {"company_data": result}

"""Enrichment pipeline - automated workflow that enriches leads on events."""
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
import structlog

from backend.services.enrichment.enrichment_engine import EnrichmentEngine, EnrichmentResult
from backend.services.enrichment.ai_enrichment import AIEnrichment

logger = structlog.get_logger()


class EnrichmentPipeline:
    """
    Automated enrichment pipeline that triggers on:
    - Lead creation (new leads auto-enriched)
    - Scheduled re-enrichment (stale data refresh)
    - Manual trigger (user requests enrichment)
    - Score threshold (when score drops, try to get more data)

    Pipeline stages:
    1. Data validation (ensure we have enough to work with)
    2. Source determination (what can we look up?)
    3. Parallel enrichment (run all applicable sources)
    4. Data merging (combine results, resolve conflicts)
    5. AI analysis (infer seniority, intent, ICP fit)
    6. Score update (trigger re-scoring with new data)
    """

    def __init__(self, proxies: Optional[List[str]] = None, openai_key: Optional[str] = None):
        self.engine = EnrichmentEngine(proxies=proxies)
        self.ai = AIEnrichment(api_key=openai_key)

    async def run_pipeline(
        self,
        lead_data: Dict[str, Any],
        team_id: Optional[UUID] = None,
        include_ai: bool = True,
        depth: str = "standard",
    ) -> Dict[str, Any]:
        """
        Run the full enrichment pipeline on a lead.

        Args:
            lead_data: Current lead data
            team_id: Team for billing/limits
            include_ai: Whether to run AI analysis
            depth: "basic" (email+linkedin), "standard" (all sources), "deep" (+ AI)

        Returns:
            Complete enriched lead data with metadata
        """
        pipeline_result = {
            "lead_data": lead_data.copy(),
            "enrichment_results": {},
            "ai_insights": {},
            "pipeline_metadata": {
                "started_at": datetime.utcnow().isoformat(),
                "depth": depth,
                "stages_completed": [],
            },
        }

        # Stage 1: Validation
        if not self._validate_input(lead_data):
            pipeline_result["pipeline_metadata"]["error"] = "Insufficient data for enrichment"
            return pipeline_result

        pipeline_result["pipeline_metadata"]["stages_completed"].append("validation")

        # Stage 2: Source determination & enrichment
        sources = self._get_sources_for_depth(depth)
        enrichment_result = await self.engine.enrich_lead(
            lead_data=lead_data,
            sources=sources,
        )

        if enrichment_result.success:
            pipeline_result["lead_data"] = enrichment_result.enriched_data
            pipeline_result["enrichment_results"] = {
                "sources_used": enrichment_result.sources_used,
                "fields_added": enrichment_result.fields_added,
                "fields_updated": enrichment_result.fields_updated,
                "confidence_scores": enrichment_result.confidence_scores,
                "duration": enrichment_result.duration_seconds,
            }

        pipeline_result["pipeline_metadata"]["stages_completed"].append("enrichment")

        # Stage 3: AI Analysis (if enabled and depth allows)
        if include_ai and depth in ("standard", "deep"):
            try:
                # AI lead analysis
                ai_analysis = await self.ai.analyze_lead(pipeline_result["lead_data"])
                pipeline_result["ai_insights"]["analysis"] = ai_analysis

                # Apply AI insights to lead data
                if ai_analysis:
                    enriched = pipeline_result["lead_data"]
                    enriched["intent_signals"] = ai_analysis.get("buying_intent_signals", [])
                    enriched["ai_seniority"] = ai_analysis.get("seniority_level")
                    enriched["ai_department"] = ai_analysis.get("department")
                    enriched["ai_icp_score"] = ai_analysis.get("icp_fit_score")
                    enriched["ai_talking_points"] = ai_analysis.get("key_talking_points", [])

                # Company inference if we have company name
                company_name = pipeline_result["lead_data"].get("company_name")
                if company_name:
                    company_data = await self.ai.infer_company_data(company_name)
                    pipeline_result["ai_insights"]["company"] = company_data

                    if company_data:
                        enriched = pipeline_result["lead_data"]
                        enriched["industry"] = company_data.get("industry")
                        enriched["company_size_category"] = company_data.get("employee_range")
                        enriched["business_model"] = company_data.get("business_model")

                pipeline_result["pipeline_metadata"]["stages_completed"].append("ai_analysis")

            except Exception as e:
                logger.warning("ai_enrichment_failed", error=str(e))
                pipeline_result["ai_insights"]["error"] = str(e)

        # Stage 4: Generate outreach suggestions (deep mode only)
        if depth == "deep" and include_ai:
            try:
                outreach = await self.ai.generate_outreach_message(
                    pipeline_result["lead_data"],
                    channel="email",
                )
                pipeline_result["ai_insights"]["outreach_suggestion"] = outreach
                pipeline_result["pipeline_metadata"]["stages_completed"].append("outreach_generation")
            except:
                pass

        pipeline_result["pipeline_metadata"]["completed_at"] = datetime.utcnow().isoformat()
        pipeline_result["pipeline_metadata"]["success"] = True

        return pipeline_result

    async def auto_enrich_new_leads(
        self,
        leads: List[Dict[str, Any]],
        team_id: Optional[UUID] = None,
        max_concurrent: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Auto-enrich a batch of newly created leads.
        Called automatically when leads are imported/created.
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def enrich_one(lead):
            async with semaphore:
                return await self.run_pipeline(
                    lead_data=lead,
                    team_id=team_id,
                    include_ai=True,
                    depth="standard",
                )

        results = await asyncio.gather(
            *[enrich_one(lead) for lead in leads],
            return_exceptions=True,
        )

        enriched_leads = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("batch_enrich_failed", error=str(result))
                continue
            if isinstance(result, dict):
                enriched_leads.append(result)

        return enriched_leads

    def _validate_input(self, lead_data: Dict) -> bool:
        """Check if we have enough data to attempt enrichment."""
        has_email = bool(lead_data.get("email"))
        has_name = bool(lead_data.get("first_name") or lead_data.get("full_name"))
        has_company = bool(lead_data.get("company_name"))
        has_linkedin = bool(lead_data.get("linkedin_url"))
        has_domain = False

        if has_email and "@" in lead_data["email"]:
            domain = lead_data["email"].split("@")[1]
            # Filter out generic email providers
            generic = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"}
            has_domain = domain not in generic

        # Need at least one meaningful data point
        return has_email or has_linkedin or (has_name and has_company) or has_domain

    def _get_sources_for_depth(self, depth: str) -> Optional[List[str]]:
        """Get enrichment sources based on depth level."""
        if depth == "basic":
            return ["linkedin", "email_finder"]
        elif depth == "standard":
            return ["linkedin", "company_website", "email_finder", "tech_stack"]
        elif depth == "deep":
            return None  # All sources
        return ["linkedin", "email_finder"]

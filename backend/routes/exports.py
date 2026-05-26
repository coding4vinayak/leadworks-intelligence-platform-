"""Export routes - generate reports and export data."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel

from backend.routes.auth import get_current_user
from backend.services.export import ExportEngine

router = APIRouter()
export_engine = ExportEngine()


class ExportLeadsRequest(BaseModel):
    leads: List[dict]
    format: str = "csv"  # csv, excel, json
    columns: Optional[List[str]] = None


class GenerateReportRequest(BaseModel):
    leads: List[dict]
    report_type: str = "summary"  # summary, pipeline, performance, source_analysis
    date_range: Optional[dict] = None


@router.post("/leads")
async def export_leads(
    request: ExportLeadsRequest,
    current_user: dict = Depends(get_current_user),
):
    """Export leads to CSV, Excel, or JSON."""
    if request.format == "csv":
        content = export_engine.export_leads_csv(request.leads, request.columns)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=leads_export.csv"},
        )
    elif request.format == "excel":
        content = export_engine.export_leads_excel(request.leads, request.columns)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=leads_export.xlsx"},
        )
    elif request.format == "json":
        content = export_engine.export_leads_json(request.leads, request.columns)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=leads_export.json"},
        )
    return {"error": "Unsupported format"}


@router.post("/report")
async def generate_report(
    request: GenerateReportRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate a structured report."""
    report = export_engine.generate_report(
        leads=request.leads,
        report_type=request.report_type,
        date_range=request.date_range,
    )
    return report


@router.get("/columns")
async def available_columns(current_user: dict = Depends(get_current_user)):
    """Get available columns for export."""
    return {
        "default_columns": export_engine.DEFAULT_LEAD_COLUMNS,
        "all_columns": export_engine.DEFAULT_LEAD_COLUMNS + [
            "score_breakdown", "enrichment_sources", "tech_stack",
            "intent_signals", "campaign_enrollments", "custom_fields",
        ],
    }

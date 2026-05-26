"""Export engine - generate CSV, Excel, JSON, PDF reports."""
import csv
import io
import json
import enum
from datetime import datetime
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger()


class ExportFormat(str, enum.Enum):
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    PDF = "pdf"


class ExportEngine:
    """
    Multi-format export engine.

    Supports:
    - CSV export with custom column selection
    - Excel export with formatting
    - JSON export (API-friendly)
    - PDF reports with charts and summaries
    - Scheduled exports (daily/weekly email)
    - Filtered exports (by segment, score, date range)
    """

    DEFAULT_LEAD_COLUMNS = [
        "first_name", "last_name", "email", "phone", "job_title",
        "company_name", "city", "country", "status", "source",
        "score", "tags", "linkedin_url", "website",
        "created_at", "last_contacted_at",
    ]

    def export_leads_csv(
        self,
        leads: List[Dict[str, Any]],
        columns: Optional[List[str]] = None,
        filename: Optional[str] = None,
    ) -> bytes:
        """Export leads to CSV format."""
        cols = columns or self.DEFAULT_LEAD_COLUMNS

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()

        for lead in leads:
            row = {}
            for col in cols:
                val = lead.get(col, "")
                if isinstance(val, (list, dict)):
                    val = json.dumps(val)
                elif isinstance(val, datetime):
                    val = val.isoformat()
                row[col] = val
            writer.writerow(row)

        return output.getvalue().encode("utf-8")

    def export_leads_excel(
        self,
        leads: List[Dict[str, Any]],
        columns: Optional[List[str]] = None,
        sheet_name: str = "Leads",
    ) -> bytes:
        """Export leads to Excel format."""
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = sheet_name

            cols = columns or self.DEFAULT_LEAD_COLUMNS

            # Header row with styling
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")

            for col_idx, col_name in enumerate(cols, 1):
                cell = ws.cell(row=1, column=col_idx, value=col_name.replace("_", " ").title())
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")

            # Data rows
            for row_idx, lead in enumerate(leads, 2):
                for col_idx, col_name in enumerate(cols, 1):
                    val = lead.get(col_name, "")
                    if isinstance(val, (list, dict)):
                        val = json.dumps(val)
                    elif isinstance(val, datetime):
                        val = val.strftime("%Y-%m-%d %H:%M")
                    ws.cell(row=row_idx, column=col_idx, value=val)

            # Auto-size columns
            for col_idx, col_name in enumerate(cols, 1):
                ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = max(15, len(col_name) + 5)

            # Save to bytes
            output = io.BytesIO()
            wb.save(output)
            return output.getvalue()

        except ImportError:
            logger.warning("openpyxl not installed, falling back to CSV")
            return self.export_leads_csv(leads, columns)

    def export_leads_json(
        self,
        leads: List[Dict[str, Any]],
        columns: Optional[List[str]] = None,
        pretty: bool = True,
    ) -> bytes:
        """Export leads to JSON format."""
        cols = columns or self.DEFAULT_LEAD_COLUMNS

        exported = []
        for lead in leads:
            row = {col: lead.get(col) for col in cols}
            # Serialize datetimes
            for k, v in row.items():
                if isinstance(v, datetime):
                    row[k] = v.isoformat()
            exported.append(row)

        indent = 2 if pretty else None
        return json.dumps(exported, indent=indent, default=str).encode("utf-8")

    def generate_report(
        self,
        leads: List[Dict[str, Any]],
        report_type: str = "summary",
        date_range: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a structured report (for PDF rendering or dashboard).

        Report types: summary, pipeline, performance, source_analysis
        """
        if report_type == "summary":
            return self._summary_report(leads)
        elif report_type == "pipeline":
            return self._pipeline_report(leads)
        elif report_type == "performance":
            return self._performance_report(leads)
        elif report_type == "source_analysis":
            return self._source_report(leads)
        return self._summary_report(leads)

    def _summary_report(self, leads: List[Dict]) -> Dict[str, Any]:
        """Executive summary report."""
        total = len(leads)
        scores = [l.get("score", 0) for l in leads]
        statuses = {}
        sources = {}

        for lead in leads:
            s = lead.get("status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1
            src = lead.get("source", "unknown")
            sources[src] = sources.get(src, 0) + 1

        return {
            "report_type": "summary",
            "generated_at": datetime.utcnow().isoformat(),
            "total_leads": total,
            "avg_score": round(sum(scores) / max(total, 1), 1),
            "hot_leads": sum(1 for s in scores if s >= 75),
            "warm_leads": sum(1 for s in scores if 45 <= s < 75),
            "cold_leads": sum(1 for s in scores if s < 45),
            "enriched": sum(1 for l in leads if l.get("is_enriched")),
            "enrichment_rate": round(sum(1 for l in leads if l.get("is_enriched")) / max(total, 1) * 100, 1),
            "status_breakdown": statuses,
            "source_breakdown": sources,
            "top_companies": self._top_n(leads, "company_name", 10),
        }

    def _pipeline_report(self, leads: List[Dict]) -> Dict[str, Any]:
        """Pipeline/funnel report."""
        pipeline = {
            "new": [], "contacted": [], "qualified": [],
            "nurturing": [], "converted": [], "lost": [],
        }
        for lead in leads:
            status = lead.get("status", "new")
            if status in pipeline:
                pipeline[status].append(lead.get("company_name", "Unknown"))

        return {
            "report_type": "pipeline",
            "generated_at": datetime.utcnow().isoformat(),
            "stages": {k: {"count": len(v), "companies": v[:5]} for k, v in pipeline.items()},
            "conversion_rate": round(
                len(pipeline["converted"]) / max(len(leads), 1) * 100, 2
            ),
        }

    def _performance_report(self, leads: List[Dict]) -> Dict[str, Any]:
        """Outreach performance report."""
        total_sent = sum(l.get("emails_sent", 0) for l in leads)
        total_opened = sum(l.get("emails_opened", 0) for l in leads)
        total_clicked = sum(l.get("emails_clicked", 0) for l in leads)
        responded = sum(1 for l in leads if l.get("last_responded_at"))

        return {
            "report_type": "performance",
            "generated_at": datetime.utcnow().isoformat(),
            "emails_sent": total_sent,
            "emails_opened": total_opened,
            "emails_clicked": total_clicked,
            "leads_responded": responded,
            "open_rate": round(total_opened / max(total_sent, 1) * 100, 1),
            "click_rate": round(total_clicked / max(total_opened, 1) * 100, 1),
            "response_rate": round(responded / max(len(leads), 1) * 100, 1),
        }

    def _source_report(self, leads: List[Dict]) -> Dict[str, Any]:
        """Lead source analysis report."""
        source_data = {}
        for lead in leads:
            src = lead.get("source", "unknown")
            if src not in source_data:
                source_data[src] = {"count": 0, "scores": [], "converted": 0}
            source_data[src]["count"] += 1
            source_data[src]["scores"].append(lead.get("score", 0))
            if lead.get("status") == "converted":
                source_data[src]["converted"] += 1

        analysis = []
        for src, data in source_data.items():
            analysis.append({
                "source": src,
                "lead_count": data["count"],
                "avg_score": round(sum(data["scores"]) / max(len(data["scores"]), 1), 1),
                "conversion_rate": round(data["converted"] / max(data["count"], 1) * 100, 2),
            })

        analysis.sort(key=lambda x: x["lead_count"], reverse=True)
        return {
            "report_type": "source_analysis",
            "generated_at": datetime.utcnow().isoformat(),
            "sources": analysis,
            "best_converting_source": max(analysis, key=lambda x: x["conversion_rate"])["source"] if analysis else None,
            "highest_quality_source": max(analysis, key=lambda x: x["avg_score"])["source"] if analysis else None,
        }

    def _top_n(self, leads: List[Dict], field: str, n: int) -> List[Dict]:
        """Get top N values for a field."""
        counts: Dict[str, int] = {}
        for lead in leads:
            val = lead.get(field)
            if val:
                counts[str(val)] = counts.get(str(val), 0) + 1
        sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [{"value": k, "count": v} for k, v in sorted_items[:n]]

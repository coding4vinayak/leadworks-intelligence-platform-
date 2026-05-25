"""Tests for export engine."""
import json
import csv
import io
import pytest
from backend.services.export.exporter import ExportEngine


class TestExportEngine:
    """Test data export and report generation."""

    def setup_method(self):
        self.engine = ExportEngine()
        self.sample_leads = [
            {
                "first_name": "Alice", "last_name": "Smith", "email": "alice@company.com",
                "phone": "+1234567890", "job_title": "CTO", "company_name": "Acme Corp",
                "city": "New York", "country": "US", "status": "qualified",
                "source": "linkedin_scrape", "score": 85, "tags": ["saas", "enterprise"],
                "linkedin_url": "https://linkedin.com/in/alice", "website": "acme.com",
                "is_enriched": True,
            },
            {
                "first_name": "Bob", "last_name": "Jones", "email": "bob@startup.io",
                "phone": "", "job_title": "Founder", "company_name": "StartupX",
                "city": "SF", "country": "US", "status": "new",
                "source": "google_maps", "score": 62, "tags": ["startup"],
                "linkedin_url": "", "website": "startupx.io",
                "is_enriched": False,
            },
            {
                "first_name": "Charlie", "last_name": "Brown", "email": "charlie@big.co",
                "phone": "+9876543210", "job_title": "VP Sales", "company_name": "BigCo",
                "city": "London", "country": "UK", "status": "converted",
                "source": "hubspot", "score": 92, "tags": ["enterprise"],
                "linkedin_url": "https://linkedin.com/in/charlie", "website": "big.co",
                "is_enriched": True,
            },
        ]

    def test_export_csv(self):
        """CSV export should produce valid CSV with headers."""
        content = self.engine.export_leads_csv(self.sample_leads)
        assert isinstance(content, bytes)

        reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
        rows = list(reader)
        assert len(rows) == 3
        assert rows[0]["email"] == "alice@company.com"
        assert rows[0]["first_name"] == "Alice"

    def test_export_csv_custom_columns(self):
        """CSV export with custom column selection."""
        columns = ["email", "company_name", "score"]
        content = self.engine.export_leads_csv(self.sample_leads, columns=columns)
        reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
        rows = list(reader)
        assert list(rows[0].keys()) == ["email", "company_name", "score"]

    def test_export_json(self):
        """JSON export should produce valid JSON array."""
        content = self.engine.export_leads_json(self.sample_leads)
        data = json.loads(content)
        assert len(data) == 3
        assert data[0]["email"] == "alice@company.com"

    def test_export_json_custom_columns(self):
        """JSON export with column filtering."""
        columns = ["email", "score"]
        content = self.engine.export_leads_json(self.sample_leads, columns=columns)
        data = json.loads(content)
        assert set(data[0].keys()) == {"email", "score"}

    def test_summary_report(self):
        """Summary report should have correct metrics."""
        report = self.engine.generate_report(self.sample_leads, "summary")
        assert report["report_type"] == "summary"
        assert report["total_leads"] == 3
        assert report["hot_leads"] == 2  # score >= 75: Alice(85) + Charlie(92)
        assert report["warm_leads"] == 1  # score 45-74: Bob(62)
        assert report["enriched"] == 2  # Alice + Charlie

    def test_pipeline_report(self):
        """Pipeline report should show funnel stages."""
        report = self.engine.generate_report(self.sample_leads, "pipeline")
        assert report["report_type"] == "pipeline"
        assert "stages" in report
        assert report["stages"]["qualified"]["count"] == 1
        assert report["stages"]["new"]["count"] == 1
        assert report["stages"]["converted"]["count"] == 1

    def test_performance_report(self):
        """Performance report should compute rates."""
        leads_with_engagement = [
            {**self.sample_leads[0], "emails_sent": 5, "emails_opened": 3, "emails_clicked": 1},
            {**self.sample_leads[1], "emails_sent": 3, "emails_opened": 1, "emails_clicked": 0},
        ]
        report = self.engine.generate_report(leads_with_engagement, "performance")
        assert report["report_type"] == "performance"
        assert report["emails_sent"] == 8
        assert report["emails_opened"] == 4
        assert report["open_rate"] == 50.0  # 4/8 * 100

    def test_source_report(self):
        """Source report should analyze by lead source."""
        report = self.engine.generate_report(self.sample_leads, "source_analysis")
        assert report["report_type"] == "source_analysis"
        assert len(report["sources"]) == 3
        # linkedin_scrape, google_maps, hubspot
        source_names = [s["source"] for s in report["sources"]]
        assert "linkedin_scrape" in source_names
        assert "hubspot" in source_names

    def test_export_empty_data(self):
        """Export should handle empty data gracefully."""
        csv_content = self.engine.export_leads_csv([])
        assert b"first_name" in csv_content  # Headers still present

        json_content = self.engine.export_leads_json([])
        assert json.loads(json_content) == []

    def test_excel_export(self):
        """Excel export should produce bytes (xlsx)."""
        content = self.engine.export_leads_excel(self.sample_leads)
        assert isinstance(content, bytes)
        assert len(content) > 100  # Should have real content

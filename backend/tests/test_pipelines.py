"""Tests for data pipeline engine."""
import pytest
import asyncio
from backend.services.pipelines.pipeline_engine import PipelineEngine, StepType


class TestPipelineEngine:
    """Test the ETL pipeline engine."""

    def setup_method(self):
        self.engine = PipelineEngine()

    def test_create_pipeline(self):
        """Create a pipeline with multiple steps."""
        pipeline = self.engine.create_pipeline(
            name="Test Pipeline",
            steps=[
                {"type": "filter", "name": "Has Email", "config": {"field": "email", "operator": "exists"}},
                {"type": "deduplicate", "name": "Dedup", "config": {"match_on": "email"}},
                {"type": "validate", "name": "Validate", "config": {"require": ["email", "first_name"]}},
            ],
            description="Test pipeline for unit tests",
        )
        assert pipeline.name == "Test Pipeline"
        assert len(pipeline.steps) == 3
        assert pipeline.trigger == "manual"
        assert pipeline.is_active is False

    @pytest.mark.asyncio
    async def test_run_filter_step(self):
        """Filter step should remove records that don't match."""
        pipeline = self.engine.create_pipeline(
            name="Filter Test",
            steps=[
                {"type": "filter", "name": "Score 50+", "config": {"field": "score", "operator": "gte", "value": 50}},
            ],
        )
        input_data = [
            {"email": "a@test.com", "score": 80},
            {"email": "b@test.com", "score": 30},
            {"email": "c@test.com", "score": 55},
            {"email": "d@test.com", "score": 10},
        ]
        run = await self.engine.run_pipeline(pipeline.id, input_data)
        assert run.status == "completed"
        assert run.records_input == 4
        assert run.records_output == 2  # Only a and c pass
        assert run.records_filtered == 2

    @pytest.mark.asyncio
    async def test_run_deduplicate_step(self):
        """Deduplicate step should remove duplicate emails."""
        pipeline = self.engine.create_pipeline(
            name="Dedup Test",
            steps=[
                {"type": "deduplicate", "name": "Dedup", "config": {"match_on": "email"}},
            ],
        )
        input_data = [
            {"email": "john@test.com", "first_name": "John"},
            {"email": "jane@test.com", "first_name": "Jane"},
            {"email": "john@test.com", "first_name": "John D."},  # duplicate
            {"email": "bob@test.com", "first_name": "Bob"},
        ]
        run = await self.engine.run_pipeline(pipeline.id, input_data)
        assert run.status == "completed"
        assert run.records_output == 3

    @pytest.mark.asyncio
    async def test_run_validate_step(self):
        """Validate step should reject records missing required fields."""
        pipeline = self.engine.create_pipeline(
            name="Validate Test",
            steps=[
                {"type": "validate", "name": "Require email+name", "config": {"require": ["email", "first_name"]}},
            ],
        )
        input_data = [
            {"email": "a@test.com", "first_name": "Alice"},  # valid
            {"email": "b@test.com"},  # missing first_name
            {"first_name": "Charlie"},  # missing email
            {"email": "d@test.com", "first_name": "Dave"},  # valid
        ]
        run = await self.engine.run_pipeline(pipeline.id, input_data)
        assert run.records_output == 2

    @pytest.mark.asyncio
    async def test_multi_step_pipeline(self):
        """Pipeline with multiple steps should chain correctly."""
        pipeline = self.engine.create_pipeline(
            name="Multi-step",
            steps=[
                {"type": "validate", "name": "Has Email", "config": {"require": ["email"]}},
                {"type": "deduplicate", "name": "Dedup", "config": {"match_on": "email"}},
                {"type": "filter", "name": "Score 40+", "config": {"field": "score", "operator": "gte", "value": 40}},
            ],
        )
        input_data = [
            {"email": "a@test.com", "score": 80},
            {"email": "b@test.com", "score": 30},
            {"email": "a@test.com", "score": 80},  # dup
            {"score": 90},  # no email
            {"email": "c@test.com", "score": 50},
        ]
        run = await self.engine.run_pipeline(pipeline.id, input_data)
        # 5 input → 4 valid → 3 unique → 2 score>=40
        assert run.records_output == 2
        assert len(run.step_results) == 3

    @pytest.mark.asyncio
    async def test_empty_input(self):
        """Pipeline with no input data should complete cleanly."""
        pipeline = self.engine.create_pipeline(
            name="Empty",
            steps=[{"type": "filter", "name": "Any", "config": {"field": "x", "operator": "exists"}}],
        )
        run = await self.engine.run_pipeline(pipeline.id, [])
        assert run.status == "completed"
        assert run.records_output == 0

    @pytest.mark.asyncio
    async def test_transform_step(self):
        """Transform step should rename fields and apply defaults."""
        pipeline = self.engine.create_pipeline(
            name="Transform",
            steps=[
                {"type": "transform", "name": "Map fields", "config": {
                    "field_map": {"full_name": "first_name", "company": "company_name"},
                    "defaults": {"source": "imported"},
                }},
            ],
        )
        input_data = [
            {"full_name": "Alice", "company": "Acme", "email": "a@acme.com"},
        ]
        run = await self.engine.run_pipeline(pipeline.id, input_data)
        assert run.records_output == 1

    @pytest.mark.asyncio
    async def test_dry_run(self):
        """Dry run should process but not persist."""
        pipeline = self.engine.create_pipeline(
            name="DryRun",
            steps=[{"type": "filter", "name": "All", "config": {"field": "email", "operator": "exists"}}],
        )
        input_data = [{"email": "a@b.com"}]
        run = await self.engine.run_pipeline(pipeline.id, input_data, dry_run=True)
        assert run.status == "completed"
        assert run.records_output == 1

    def test_pipeline_stats_update(self):
        """Running a pipeline should update its stats."""
        pipeline = self.engine.create_pipeline(
            name="Stats Test",
            steps=[{"type": "filter", "name": "Pass", "config": {"field": "x", "operator": "exists"}}],
        )
        assert pipeline.total_runs == 0
        asyncio.run(self.engine.run_pipeline(pipeline.id, [{"x": 1}]))
        assert pipeline.total_runs == 1
        assert pipeline.last_run_status == "completed"

    def test_get_templates(self):
        """Should return pre-built templates."""
        templates = self.engine.get_templates()
        assert len(templates) >= 5
        assert any("LinkedIn" in t["name"] for t in templates)
        assert any("CSV" in t["name"] for t in templates)

    def test_list_pipelines(self):
        """Should list created pipelines."""
        self.engine.create_pipeline(name="P1", steps=[])
        self.engine.create_pipeline(name="P2", steps=[])
        result = self.engine.list_pipelines()
        assert len(result) == 2

    def test_get_run_status(self):
        """Should return run status."""
        pipeline = self.engine.create_pipeline(
            name="Status",
            steps=[{"type": "filter", "name": "X", "config": {"field": "x", "operator": "exists"}}],
        )
        run = asyncio.run(self.engine.run_pipeline(pipeline.id, [{"x": 1}, {"y": 2}]))
        status = self.engine.get_run_status(run.id)
        assert status is not None
        assert status["status"] == "completed"
        assert status["records_input"] == 2
        assert status["records_output"] == 1

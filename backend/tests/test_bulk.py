"""Tests for bulk operations processor."""
import pytest
import asyncio
from backend.services.bulk.bulk_processor import BulkProcessor, BulkJobStatus


class TestBulkProcessor:
    """Test bulk operations."""

    def setup_method(self):
        self.processor = BulkProcessor(max_concurrent=3, batch_size=10)

    def test_create_job(self):
        """Create a bulk job."""
        job = self.processor.create_job(
            operation="enrich",
            lead_ids=["l1", "l2", "l3"],
            params={"depth": "standard"},
            team_id="team_1",
        )
        assert job.operation == "enrich"
        assert job.total_items == 3
        assert job.status == BulkJobStatus.PENDING

    @pytest.mark.asyncio
    async def test_run_bulk_tag(self):
        """Bulk tag should tag all leads."""
        job = await self.processor.bulk_tag(
            lead_ids=["l1", "l2", "l3", "l4"],
            tags=["hot", "priority"],
            team_id="team_1",
        )
        assert job.status == BulkJobStatus.COMPLETED
        assert job.succeeded == 4
        assert job.failed == 0
        assert job.progress_percent == 100.0

    @pytest.mark.asyncio
    async def test_run_bulk_delete(self):
        """Bulk delete should process all items."""
        job = await self.processor.bulk_delete(
            lead_ids=["l1", "l2", "l3"],
            team_id="team_1",
        )
        assert job.status == BulkJobStatus.COMPLETED
        assert job.succeeded == 3

    @pytest.mark.asyncio
    async def test_run_bulk_assign(self):
        """Bulk assign should assign all leads to rep."""
        job = await self.processor.bulk_assign(
            lead_ids=["l1", "l2"],
            rep_id="rep_alice",
            team_id="team_1",
        )
        assert job.status == BulkJobStatus.COMPLETED
        assert job.succeeded == 2

    @pytest.mark.asyncio
    async def test_run_bulk_update_status(self):
        """Bulk status update should update all leads."""
        job = await self.processor.bulk_update_status(
            lead_ids=["l1", "l2", "l3"],
            new_status="qualified",
            team_id="team_1",
        )
        assert job.succeeded == 3

    def test_cancel_job(self):
        """Should be able to cancel a running job."""
        job = self.processor.create_job(
            operation="enrich",
            lead_ids=[f"l{i}" for i in range(100)],
        )
        # Before running, cancel shouldn't work (not running yet)
        result = self.processor.cancel_job(job.id)
        assert result is False  # Not running

    def test_get_job_status(self):
        """Get job status with progress info."""
        job = self.processor.create_job(
            operation="score",
            lead_ids=["l1", "l2"],
            team_id="team_1",
        )
        status = self.processor.get_job_status(job.id)
        assert status["id"] == job.id
        assert status["operation"] == "score"
        assert status["total_items"] == 2
        assert status["status"] == "pending"

    def test_list_jobs(self):
        """List bulk jobs with filtering."""
        self.processor.create_job("enrich", ["l1"], team_id="team_1")
        self.processor.create_job("score", ["l2"], team_id="team_1")
        self.processor.create_job("tag", ["l3"], team_id="team_2")

        all_jobs = self.processor.list_jobs()
        assert len(all_jobs) == 3

        team1_jobs = self.processor.list_jobs(team_id="team_1")
        assert len(team1_jobs) == 2

    @pytest.mark.asyncio
    async def test_job_with_errors(self):
        """Jobs should handle errors gracefully."""
        job = self.processor.create_job("custom", ["l1", "l2", "l3"])

        call_count = 0

        async def failing_processor(lead_id, params):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ValueError("Simulated error")
            return {"ok": True}

        completed_job = await self.processor.run_job(job.id, failing_processor)
        assert completed_job.status == BulkJobStatus.COMPLETED
        assert completed_job.succeeded == 2
        assert completed_job.failed == 1
        assert len(completed_job.errors) == 1

    @pytest.mark.asyncio
    async def test_large_batch(self):
        """Should handle large batches with concurrency control."""
        lead_ids = [f"lead_{i}" for i in range(50)]
        job = self.processor.create_job("score", lead_ids, team_id="team_1")

        async def simple_processor(lead_id, params):
            await asyncio.sleep(0.01)  # Simulate work
            return {"scored": True}

        completed = await self.processor.run_job(job.id, simple_processor)
        assert completed.succeeded == 50
        assert completed.progress_percent == 100.0

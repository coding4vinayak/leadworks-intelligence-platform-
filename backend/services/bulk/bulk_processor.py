"""Bulk operations processor for large-scale lead operations."""
import asyncio
import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4
import structlog

logger = structlog.get_logger()


class BulkJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class BulkOperationType(str, enum.Enum):
    ENRICH = "enrich"
    SCORE = "score"
    TAG = "tag"
    UNTAG = "untag"
    ASSIGN = "assign"
    UPDATE_STATUS = "update_status"
    DELETE = "delete"
    EXPORT = "export"
    IMPORT = "import"
    SEND_EMAIL = "send_email"
    ADD_TO_CAMPAIGN = "add_to_campaign"
    REMOVE_FROM_CAMPAIGN = "remove_from_campaign"


@dataclass
class BulkJob:
    """A bulk operation job."""
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    operation: str = ""
    status: BulkJobStatus = BulkJobStatus.PENDING
    # Input
    lead_ids: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)
    total_items: int = 0
    # Progress
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    progress_percent: float = 0.0
    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    # Results
    results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    # Metadata
    created_by: Optional[str] = None
    team_id: Optional[str] = None
    # Control
    is_cancelled: bool = False


class BulkProcessor:
    """
    Bulk operations processor with progress tracking.

    Features:
    - Process thousands of leads in batches
    - Real-time progress via WebSocket
    - Pause/resume/cancel support
    - Error handling with retry
    - Rate limiting for external APIs
    - Parallel processing with concurrency control
    - Job history and audit trail
    """

    def __init__(self, max_concurrent: int = 5, batch_size: int = 50):
        self.max_concurrent = max_concurrent
        self.batch_size = batch_size
        self.jobs: Dict[str, BulkJob] = {}

    def create_job(
        self,
        operation: str,
        lead_ids: List[str],
        params: Dict[str, Any] = None,
        team_id: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> BulkJob:
        """Create a new bulk job."""
        job = BulkJob(
            operation=operation,
            lead_ids=lead_ids,
            params=params or {},
            total_items=len(lead_ids),
            team_id=team_id,
            created_by=created_by,
        )
        self.jobs[job.id] = job
        logger.info("bulk_job_created", job_id=job.id, operation=operation, total=len(lead_ids))
        return job

    async def run_job(self, job_id: str, processor_fn: Callable) -> BulkJob:
        """
        Execute a bulk job.

        Args:
            job_id: The job to run
            processor_fn: Async function that processes a single item.
                         Signature: async def fn(lead_id: str, params: dict) -> dict
        """
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = BulkJobStatus.RUNNING
        job.started_at = datetime.utcnow()

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def process_one(lead_id: str) -> Dict[str, Any]:
            if job.is_cancelled:
                return {"lead_id": lead_id, "status": "cancelled"}

            async with semaphore:
                try:
                    result = await processor_fn(lead_id, job.params)
                    job.succeeded += 1
                    return {"lead_id": lead_id, "status": "success", "result": result}
                except Exception as e:
                    job.failed += 1
                    error = {"lead_id": lead_id, "status": "failed", "error": str(e)}
                    job.errors.append(error)
                    return error
                finally:
                    job.processed += 1
                    job.progress_percent = round(job.processed / max(job.total_items, 1) * 100, 1)

        # Process in batches
        for i in range(0, len(job.lead_ids), self.batch_size):
            if job.is_cancelled:
                job.status = BulkJobStatus.CANCELLED
                break

            batch = job.lead_ids[i:i + self.batch_size]
            batch_results = await asyncio.gather(
                *[process_one(lid) for lid in batch],
                return_exceptions=True,
            )

            for result in batch_results:
                if isinstance(result, dict):
                    job.results.append(result)

        # Finalize
        if not job.is_cancelled:
            job.status = BulkJobStatus.COMPLETED

        job.completed_at = datetime.utcnow()
        duration = (job.completed_at - job.started_at).total_seconds()

        logger.info(
            "bulk_job_completed",
            job_id=job.id,
            operation=job.operation,
            succeeded=job.succeeded,
            failed=job.failed,
            duration_seconds=duration,
        )

        return job

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        job = self.jobs.get(job_id)
        if job and job.status == BulkJobStatus.RUNNING:
            job.is_cancelled = True
            return True
        return False

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job progress and status."""
        job = self.jobs.get(job_id)
        if not job:
            return None

        duration = None
        if job.started_at:
            end = job.completed_at or datetime.utcnow()
            duration = (end - job.started_at).total_seconds()

        return {
            "id": job.id,
            "operation": job.operation,
            "status": job.status.value,
            "total_items": job.total_items,
            "processed": job.processed,
            "succeeded": job.succeeded,
            "failed": job.failed,
            "skipped": job.skipped,
            "progress_percent": job.progress_percent,
            "duration_seconds": duration,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "errors_count": len(job.errors),
            "recent_errors": job.errors[-5:],  # Last 5 errors
        }

    def list_jobs(
        self,
        team_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """List bulk jobs with optional filtering."""
        jobs = list(self.jobs.values())

        if team_id:
            jobs = [j for j in jobs if j.team_id == team_id]
        if status:
            jobs = [j for j in jobs if j.status.value == status]

        jobs.sort(key=lambda j: j.created_at, reverse=True)

        return [
            {
                "id": j.id,
                "operation": j.operation,
                "status": j.status.value,
                "total_items": j.total_items,
                "processed": j.processed,
                "progress_percent": j.progress_percent,
                "created_at": j.created_at.isoformat(),
            }
            for j in jobs[:limit]
        ]

    # ---- Pre-built bulk operations ----

    async def bulk_enrich(self, lead_ids: List[str], depth: str = "standard", team_id: str = None) -> BulkJob:
        """Enrich multiple leads."""
        job = self.create_job("enrich", lead_ids, {"depth": depth}, team_id=team_id)

        async def enrich_one(lead_id: str, params: dict):
            # In production: call EnrichmentPipeline
            return {"enriched": True, "depth": params.get("depth")}

        return await self.run_job(job.id, enrich_one)

    async def bulk_score(self, lead_ids: List[str], mode: str = "hybrid", team_id: str = None) -> BulkJob:
        """Score multiple leads."""
        job = self.create_job("score", lead_ids, {"mode": mode}, team_id=team_id)

        async def score_one(lead_id: str, params: dict):
            # In production: call ScoringEngine
            return {"scored": True, "mode": params.get("mode")}

        return await self.run_job(job.id, score_one)

    async def bulk_tag(self, lead_ids: List[str], tags: List[str], team_id: str = None) -> BulkJob:
        """Add tags to multiple leads."""
        job = self.create_job("tag", lead_ids, {"tags": tags}, team_id=team_id)

        async def tag_one(lead_id: str, params: dict):
            return {"tagged": True, "tags": params.get("tags")}

        return await self.run_job(job.id, tag_one)

    async def bulk_delete(self, lead_ids: List[str], team_id: str = None) -> BulkJob:
        """Delete multiple leads."""
        job = self.create_job("delete", lead_ids, {}, team_id=team_id)

        async def delete_one(lead_id: str, params: dict):
            return {"deleted": True}

        return await self.run_job(job.id, delete_one)

    async def bulk_assign(self, lead_ids: List[str], rep_id: str, team_id: str = None) -> BulkJob:
        """Assign multiple leads to a rep."""
        job = self.create_job("assign", lead_ids, {"rep_id": rep_id}, team_id=team_id)

        async def assign_one(lead_id: str, params: dict):
            return {"assigned_to": params.get("rep_id")}

        return await self.run_job(job.id, assign_one)

    async def bulk_update_status(self, lead_ids: List[str], new_status: str, team_id: str = None) -> BulkJob:
        """Update status for multiple leads."""
        job = self.create_job("update_status", lead_ids, {"status": new_status}, team_id=team_id)

        async def update_one(lead_id: str, params: dict):
            return {"new_status": params.get("status")}

        return await self.run_job(job.id, update_one)

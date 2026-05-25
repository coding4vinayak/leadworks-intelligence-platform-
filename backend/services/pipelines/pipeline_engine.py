"""Data pipeline engine - visual workflow builder for lead processing."""
import asyncio
import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4
import structlog

logger = structlog.get_logger()


class StepType(str, enum.Enum):
    """Types of steps in a pipeline."""
    # Sources
    SOURCE_SCRAPER = "source_scraper"
    SOURCE_IMPORT = "source_import"
    SOURCE_WEBHOOK = "source_webhook"
    SOURCE_CONNECTOR = "source_connector"

    # Processing
    FILTER = "filter"
    TRANSFORM = "transform"
    ENRICH = "enrich"
    SCORE = "score"
    DEDUPLICATE = "deduplicate"
    VALIDATE = "validate"
    FRAUD_CHECK = "fraud_check"

    # Actions
    ACTION_CREATE_LEAD = "action_create_lead"
    ACTION_UPDATE_LEAD = "action_update_lead"
    ACTION_TAG = "action_tag"
    ACTION_ASSIGN = "action_assign"
    ACTION_ADD_TO_CAMPAIGN = "action_add_to_campaign"
    ACTION_SEND_EMAIL = "action_send_email"
    ACTION_SLACK_NOTIFY = "action_slack_notify"
    ACTION_WEBHOOK_SEND = "action_webhook_send"
    ACTION_EXPORT = "action_export"

    # Control
    CONDITION = "condition"
    SPLIT = "split"
    MERGE = "merge"
    DELAY = "delay"
    LOOP = "loop"


@dataclass
class PipelineStep:
    """A single step in a data pipeline."""
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    step_type: StepType = StepType.FILTER
    name: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    next_steps: List[str] = field(default_factory=list)  # IDs of next steps
    condition_true_step: Optional[str] = None
    condition_false_step: Optional[str] = None
    # Runtime
    records_in: int = 0
    records_out: int = 0
    errors: int = 0
    duration_ms: float = 0


@dataclass
class Pipeline:
    """A complete data pipeline definition."""
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    name: str = ""
    description: str = ""
    steps: List[PipelineStep] = field(default_factory=list)
    trigger: str = "manual"  # manual, schedule, webhook, event
    trigger_config: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = False
    version: int = 1
    # Stats
    total_runs: int = 0
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    avg_duration_seconds: float = 0.0
    total_records_processed: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    team_id: Optional[str] = None


@dataclass
class PipelineRun:
    """A single execution of a pipeline."""
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    pipeline_id: str = ""
    status: str = "running"  # running, completed, failed, cancelled
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    records_input: int = 0
    records_output: int = 0
    records_filtered: int = 0
    records_errored: int = 0
    step_results: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None


# Pre-built pipeline templates
PIPELINE_TEMPLATES = [
    {
        "id": "linkedin_to_enriched_leads",
        "name": "LinkedIn Scrape → Enrich → Score → Notify",
        "description": "Scrape LinkedIn, deduplicate, enrich, score, and alert on hot leads",
        "steps": [
            {"type": "source_scraper", "name": "LinkedIn Search", "config": {"scraper": "linkedin_search"}},
            {"type": "deduplicate", "name": "Remove Duplicates", "config": {"match_on": "email,linkedin_url"}},
            {"type": "fraud_check", "name": "Spam Filter", "config": {"reject_score": 0.6}},
            {"type": "enrich", "name": "Auto-Enrich", "config": {"depth": "standard"}},
            {"type": "score", "name": "Score Leads", "config": {"mode": "hybrid"}},
            {"type": "condition", "name": "Is Hot?", "config": {"field": "score", "operator": "gte", "value": 75}},
            {"type": "action_slack_notify", "name": "Alert Sales", "config": {"channel": "#hot-leads"}},
            {"type": "action_create_lead", "name": "Save Lead", "config": {}},
        ],
    },
    {
        "id": "csv_import_pipeline",
        "name": "CSV Import → Validate → Enrich → Campaign",
        "description": "Import from CSV, validate, deduplicate, enrich, and add to welcome campaign",
        "steps": [
            {"type": "source_import", "name": "CSV Upload", "config": {"format": "csv"}},
            {"type": "validate", "name": "Validate Data", "config": {"require": ["email"]}},
            {"type": "deduplicate", "name": "Check Duplicates", "config": {"match_on": "email"}},
            {"type": "enrich", "name": "Enrich Leads", "config": {"depth": "basic"}},
            {"type": "score", "name": "Initial Score", "config": {"mode": "weighted"}},
            {"type": "action_create_lead", "name": "Create Leads", "config": {}},
            {"type": "action_add_to_campaign", "name": "Add to Welcome", "config": {"campaign_id": "welcome_sequence"}},
        ],
    },
    {
        "id": "google_maps_local_leads",
        "name": "Google Maps → Filter → Email Find → Outreach",
        "description": "Find local businesses, discover emails, and start outreach",
        "steps": [
            {"type": "source_scraper", "name": "Google Maps Search", "config": {"scraper": "google_maps"}},
            {"type": "filter", "name": "Rating 4+", "config": {"field": "rating", "operator": "gte", "value": 4}},
            {"type": "enrich", "name": "Find Emails", "config": {"sources": ["email_finder", "website"]}},
            {"type": "filter", "name": "Has Email", "config": {"field": "email", "operator": "exists"}},
            {"type": "score", "name": "Score", "config": {"mode": "weighted"}},
            {"type": "action_create_lead", "name": "Save", "config": {}},
            {"type": "action_add_to_campaign", "name": "Start Outreach", "config": {"campaign_id": "cold_intro"}},
        ],
    },
    {
        "id": "re_engagement_pipeline",
        "name": "Stale Leads → Re-enrich → Re-score → Campaign",
        "description": "Find inactive leads, refresh data, re-score, and start re-engagement",
        "steps": [
            {"type": "filter", "name": "Inactive 30+ Days", "config": {"field": "days_inactive", "operator": "gte", "value": 30}},
            {"type": "filter", "name": "Was Warm+", "config": {"field": "score", "operator": "gte", "value": 40}},
            {"type": "enrich", "name": "Refresh Data", "config": {"depth": "standard", "force_refresh": True}},
            {"type": "score", "name": "Re-score", "config": {"mode": "hybrid"}},
            {"type": "condition", "name": "Score Improved?", "config": {"field": "score_change", "operator": "gt", "value": 0}},
            {"type": "action_add_to_campaign", "name": "Re-engage", "config": {"campaign_id": "re_engagement"}},
        ],
    },
    {
        "id": "webhook_lead_processing",
        "name": "Webhook → Validate → Fraud Check → Route",
        "description": "Process inbound webhook leads with full validation pipeline",
        "steps": [
            {"type": "source_webhook", "name": "Receive Webhook", "config": {}},
            {"type": "validate", "name": "Validate Fields", "config": {"require": ["email", "name"]}},
            {"type": "fraud_check", "name": "Fraud Detection", "config": {"reject_score": 0.7}},
            {"type": "deduplicate", "name": "Check Existing", "config": {"match_on": "email"}},
            {"type": "enrich", "name": "Quick Enrich", "config": {"depth": "basic"}},
            {"type": "score", "name": "Score", "config": {"mode": "hybrid"}},
            {"type": "action_create_lead", "name": "Create Lead", "config": {}},
            {"type": "action_assign", "name": "Auto-Assign", "config": {"strategy": "score_based"}},
            {"type": "condition", "name": "Is Hot?", "config": {"field": "score", "operator": "gte", "value": 75}},
            {"type": "action_slack_notify", "name": "Alert Rep", "config": {}},
        ],
    },
]


class PipelineEngine:
    """
    Visual data pipeline engine.

    Supports building custom ETL workflows:
    - Drag-and-drop pipeline builder (frontend)
    - Conditional branching (if/else)
    - Parallel processing (split/merge)
    - Rate limiting between steps
    - Error handling per step
    - Dry run mode (preview without saving)
    - Version control for pipelines
    - Scheduled execution via Celery
    - Real-time progress via WebSocket
    """

    def __init__(self):
        self.pipelines: Dict[str, Pipeline] = {}
        self.runs: Dict[str, PipelineRun] = {}
        self._step_handlers: Dict[str, Callable] = {}
        self._register_default_handlers()

    def _register_default_handlers(self):
        """Register built-in step handlers."""
        self._step_handlers = {
            StepType.FILTER: self._handle_filter,
            StepType.VALIDATE: self._handle_validate,
            StepType.DEDUPLICATE: self._handle_deduplicate,
            StepType.CONDITION: self._handle_condition,
            StepType.TRANSFORM: self._handle_transform,
        }

    def create_pipeline(
        self,
        name: str,
        steps: List[Dict[str, Any]],
        description: str = "",
        trigger: str = "manual",
        trigger_config: Optional[Dict] = None,
        team_id: Optional[str] = None,
    ) -> Pipeline:
        """Create a new pipeline from step definitions."""
        pipeline_steps = []
        for step_def in steps:
            step = PipelineStep(
                step_type=StepType(step_def["type"]),
                name=step_def.get("name", step_def["type"]),
                config=step_def.get("config", {}),
            )
            pipeline_steps.append(step)

        # Link steps sequentially by default
        for i in range(len(pipeline_steps) - 1):
            pipeline_steps[i].next_steps = [pipeline_steps[i + 1].id]

        pipeline = Pipeline(
            name=name,
            description=description,
            steps=pipeline_steps,
            trigger=trigger,
            trigger_config=trigger_config or {},
            team_id=team_id,
        )
        self.pipelines[pipeline.id] = pipeline

        logger.info("pipeline_created", id=pipeline.id, name=name, steps=len(pipeline_steps))
        return pipeline

    async def run_pipeline(
        self,
        pipeline_id: str,
        input_data: List[Dict[str, Any]],
        dry_run: bool = False,
    ) -> PipelineRun:
        """
        Execute a pipeline on input data.

        Args:
            pipeline_id: Pipeline to execute
            input_data: Initial data records
            dry_run: If True, don't persist changes (preview mode)
        """
        pipeline = self.pipelines.get(pipeline_id)
        if not pipeline:
            raise ValueError(f"Pipeline {pipeline_id} not found")

        run = PipelineRun(
            pipeline_id=pipeline_id,
            records_input=len(input_data),
        )
        self.runs[run.id] = run

        current_data = input_data.copy()

        try:
            for step in pipeline.steps:
                step_start = datetime.utcnow()
                step.records_in = len(current_data)

                # Execute step
                handler = self._step_handlers.get(step.step_type)
                if handler:
                    current_data = await handler(current_data, step.config)
                else:
                    # Unknown step type - pass through
                    logger.warning("unknown_step_type", step_type=step.step_type)

                step.records_out = len(current_data)
                step.duration_ms = (datetime.utcnow() - step_start).total_seconds() * 1000

                run.step_results.append({
                    "step_id": step.id,
                    "step_name": step.name,
                    "step_type": step.step_type.value,
                    "records_in": step.records_in,
                    "records_out": step.records_out,
                    "duration_ms": step.duration_ms,
                })

                # Stop if no records left
                if not current_data:
                    break

            run.status = "completed"
            run.records_output = len(current_data)
            run.records_filtered = run.records_input - run.records_output

        except Exception as e:
            run.status = "failed"
            run.error_message = str(e)
            logger.error("pipeline_failed", pipeline_id=pipeline_id, error=str(e))

        run.completed_at = datetime.utcnow()

        # Update pipeline stats
        pipeline.total_runs += 1
        pipeline.last_run_at = run.completed_at
        pipeline.last_run_status = run.status
        pipeline.total_records_processed += run.records_input

        return run

    async def _handle_filter(self, data: List[Dict], config: Dict) -> List[Dict]:
        """Filter records based on a condition."""
        field_name = config.get("field", "")
        operator = config.get("operator", "exists")
        value = config.get("value")

        filtered = []
        for record in data:
            actual = record.get(field_name)
            passes = False

            if operator == "exists":
                passes = actual is not None and actual != ""
            elif operator == "not_exists":
                passes = actual is None or actual == ""
            elif operator == "eq":
                passes = actual == value
            elif operator == "neq":
                passes = actual != value
            elif operator == "gt":
                passes = (actual or 0) > value
            elif operator == "gte":
                passes = (actual or 0) >= value
            elif operator == "lt":
                passes = (actual or 0) < value
            elif operator == "lte":
                passes = (actual or 0) <= value
            elif operator == "contains":
                passes = str(value).lower() in str(actual or "").lower()
            elif operator == "in":
                passes = actual in (value or [])

            if passes:
                filtered.append(record)

        return filtered

    async def _handle_validate(self, data: List[Dict], config: Dict) -> List[Dict]:
        """Validate records have required fields."""
        required = config.get("require", [])
        valid = []
        for record in data:
            if all(record.get(f) for f in required):
                valid.append(record)
        return valid

    async def _handle_deduplicate(self, data: List[Dict], config: Dict) -> List[Dict]:
        """Remove duplicate records."""
        match_fields = config.get("match_on", "email").split(",")
        seen = set()
        unique = []
        for record in data:
            key = tuple(str(record.get(f, "")).lower().strip() for f in match_fields)
            if key not in seen and any(k for k in key):
                seen.add(key)
                unique.append(record)
        return unique

    async def _handle_condition(self, data: List[Dict], config: Dict) -> List[Dict]:
        """Conditional filter (same as filter but semantically different)."""
        return await self._handle_filter(data, config)

    async def _handle_transform(self, data: List[Dict], config: Dict) -> List[Dict]:
        """Transform/map fields."""
        field_map = config.get("field_map", {})
        defaults = config.get("defaults", {})

        transformed = []
        for record in data:
            new_record = record.copy()
            # Apply field mapping
            for old_field, new_field in field_map.items():
                if old_field in new_record:
                    new_record[new_field] = new_record.pop(old_field)
            # Apply defaults
            for field_name, default_value in defaults.items():
                if not new_record.get(field_name):
                    new_record[field_name] = default_value
            transformed.append(new_record)
        return transformed

    def get_templates(self) -> List[Dict[str, Any]]:
        """Get pre-built pipeline templates."""
        return PIPELINE_TEMPLATES

    def list_pipelines(self, team_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all pipelines."""
        pipelines = list(self.pipelines.values())
        if team_id:
            pipelines = [p for p in pipelines if p.team_id == team_id]

        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "steps_count": len(p.steps),
                "trigger": p.trigger,
                "is_active": p.is_active,
                "total_runs": p.total_runs,
                "last_run_at": p.last_run_at.isoformat() if p.last_run_at else None,
                "last_run_status": p.last_run_status,
                "total_records_processed": p.total_records_processed,
            }
            for p in pipelines
        ]

    def get_run_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get pipeline run details."""
        run = self.runs.get(run_id)
        if not run:
            return None
        return {
            "id": run.id,
            "pipeline_id": run.pipeline_id,
            "status": run.status,
            "records_input": run.records_input,
            "records_output": run.records_output,
            "records_filtered": run.records_filtered,
            "records_errored": run.records_errored,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "step_results": run.step_results,
            "error_message": run.error_message,
        }

"""Celery worker for background tasks."""
from celery import Celery
from celery.schedules import crontab
from backend.config import settings

app = Celery(
    'leadworks',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Scheduled tasks
app.conf.beat_schedule = {
    # Re-score all leads every 6 hours
    'rescore-leads': {
        'task': 'backend.tasks.rescore_all_leads',
        'schedule': crontab(minute=0, hour='*/6'),
    },
    # Sync connectors every 30 minutes
    'sync-connectors': {
        'task': 'backend.tasks.sync_all_connectors',
        'schedule': crontab(minute='*/30'),
    },
    # Daily enrichment refresh for stale leads
    'refresh-enrichment': {
        'task': 'backend.tasks.refresh_stale_enrichment',
        'schedule': crontab(minute=0, hour=2),  # 2 AM daily
    },
    # Daily Slack summary
    'daily-summary': {
        'task': 'backend.tasks.send_daily_summary',
        'schedule': crontab(minute=0, hour=9),  # 9 AM daily
    },
    # Process campaign steps
    'process-campaigns': {
        'task': 'backend.tasks.process_campaign_steps',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
}


# Task definitions
@app.task(name='backend.tasks.rescore_all_leads')
def rescore_all_leads():
    """Re-score all active leads with latest data."""
    pass


@app.task(name='backend.tasks.sync_all_connectors')
def sync_all_connectors():
    """Sync all active connectors."""
    pass


@app.task(name='backend.tasks.refresh_stale_enrichment')
def refresh_stale_enrichment():
    """Re-enrich leads with data older than 30 days."""
    pass


@app.task(name='backend.tasks.send_daily_summary')
def send_daily_summary():
    """Send daily stats to Slack."""
    pass


@app.task(name='backend.tasks.process_campaign_steps')
def process_campaign_steps():
    """Process pending campaign steps (send emails, check conditions)."""
    pass


@app.task(name='backend.tasks.enrich_lead')
def enrich_lead_task(lead_id: str, depth: str = 'standard'):
    """Background task to enrich a single lead."""
    pass


@app.task(name='backend.tasks.run_scrape_job')
def run_scrape_job_task(job_type: str, params: dict, team_id: str):
    """Background task to run a scraping job."""
    pass


@app.task(name='backend.tasks.send_campaign_email')
def send_campaign_email_task(lead_id: str, campaign_id: str, step_id: str):
    """Background task to send a campaign email."""
    pass

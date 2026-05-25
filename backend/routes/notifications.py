"""Notification routes - manage notifications and preferences."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.routes.auth import get_current_user
from backend.services.notifications import NotificationEngine

router = APIRouter()
notification_engine = NotificationEngine()


class MarkReadRequest(BaseModel):
    notification_ids: Optional[List[str]] = None  # None = mark all read


class PreferencesUpdate(BaseModel):
    daily_digest_enabled: Optional[bool] = None
    weekly_report_enabled: Optional[bool] = None
    muted_channels: Optional[List[str]] = None
    channel_overrides: Optional[dict] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    timezone: Optional[str] = None


class MuteRequest(BaseModel):
    duration_minutes: int = 60


@router.get("/")
async def get_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    """Get user's notification feed."""
    user_id = current_user["sub"]
    return notification_engine.get_notifications(
        user_id=user_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )


@router.get("/unread-count")
async def get_unread_count(current_user: dict = Depends(get_current_user)):
    """Get unread notification count (for badge)."""
    user_id = current_user["sub"]
    return {"unread_count": notification_engine.get_unread_count(user_id)}


@router.post("/mark-read")
async def mark_read(
    request: MarkReadRequest,
    current_user: dict = Depends(get_current_user),
):
    """Mark notifications as read."""
    user_id = current_user["sub"]
    count = notification_engine.mark_read(user_id, request.notification_ids)
    return {"marked_read": count}


@router.get("/preferences")
async def get_preferences(current_user: dict = Depends(get_current_user)):
    """Get notification preferences."""
    user_id = current_user["sub"]
    prefs = notification_engine._preferences.get(user_id)
    if not prefs:
        return {"user_id": user_id, "default": True}
    return {
        "user_id": user_id,
        "daily_digest_enabled": prefs.daily_digest_enabled,
        "weekly_report_enabled": prefs.weekly_report_enabled,
        "muted_channels": prefs.muted_channels,
        "quiet_hours_start": prefs.quiet_hours_start,
        "quiet_hours_end": prefs.quiet_hours_end,
        "timezone": prefs.timezone,
    }


@router.patch("/preferences")
async def update_preferences(
    request: PreferencesUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update notification preferences."""
    user_id = current_user["sub"]
    prefs = notification_engine.update_preferences(
        user_id,
        request.dict(exclude_none=True),
    )
    return {"updated": True, "user_id": user_id}


@router.post("/mute")
async def mute_notifications(
    request: MuteRequest,
    current_user: dict = Depends(get_current_user),
):
    """Mute all notifications for a duration."""
    user_id = current_user["sub"]
    notification_engine.mute(user_id, request.duration_minutes)
    return {"muted": True, "duration_minutes": request.duration_minutes}

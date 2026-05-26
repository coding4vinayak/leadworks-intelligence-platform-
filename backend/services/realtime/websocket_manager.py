"""WebSocket manager for real-time lead updates and live dashboard."""
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect
import structlog

logger = structlog.get_logger()


class WSEventType(str, Enum):
    """WebSocket event types pushed to clients."""
    # Lead events
    LEAD_CREATED = "lead.created"
    LEAD_UPDATED = "lead.updated"
    LEAD_SCORED = "lead.scored"
    LEAD_ENRICHED = "lead.enriched"
    LEAD_STATUS_CHANGED = "lead.status_changed"
    LEAD_ASSIGNED = "lead.assigned"

    # Engagement
    EMAIL_OPENED = "email.opened"
    EMAIL_REPLIED = "email.replied"
    VISITOR_ACTIVE = "visitor.active"
    FORM_SUBMITTED = "form.submitted"

    # System
    SCRAPE_STARTED = "scrape.started"
    SCRAPE_COMPLETED = "scrape.completed"
    ENRICHMENT_COMPLETED = "enrichment.completed"
    CAMPAIGN_SENT = "campaign.sent"
    IMPORT_PROGRESS = "import.progress"
    IMPORT_COMPLETED = "import.completed"

    # Notifications
    NOTIFICATION = "notification"

    # Dashboard
    STATS_UPDATED = "stats.updated"
    SCORE_DISTRIBUTION_CHANGED = "score_distribution.changed"


@dataclass
class WSEvent:
    """A WebSocket event to broadcast."""
    event_type: WSEventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    team_id: Optional[str] = None
    user_id: Optional[str] = None  # If targeting specific user


class WebSocketManager:
    """
    Manages WebSocket connections for real-time updates.

    Features:
    - Per-team rooms (all team members see team events)
    - Per-user targeting (notifications, assignments)
    - Event filtering (clients subscribe to event types)
    - Auto-reconnection support
    - Connection health monitoring (ping/pong)
    - Broadcast to all, team, or specific user
    - Event history buffer (catch-up on reconnect)
    """

    def __init__(self, history_size: int = 100):
        # team_id -> set of WebSocket connections
        self._team_connections: Dict[str, Set[WebSocket]] = {}
        # user_id -> WebSocket connection
        self._user_connections: Dict[str, WebSocket] = {}
        # Connection metadata
        self._connection_meta: Dict[WebSocket, Dict[str, Any]] = {}
        # Recent event history per team (for reconnection catch-up)
        self._event_history: Dict[str, List[Dict]] = {}
        self._history_size = history_size
        # Stats
        self._total_connections = 0
        self._total_messages_sent = 0

    async def connect(
        self,
        websocket: WebSocket,
        team_id: str,
        user_id: str,
        subscriptions: Optional[List[str]] = None,
    ):
        """
        Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket connection
            team_id: Team for room-based broadcasting
            user_id: User for targeted messages
            subscriptions: Event types to subscribe to (None = all)
        """
        await websocket.accept()

        # Register in team room
        if team_id not in self._team_connections:
            self._team_connections[team_id] = set()
        self._team_connections[team_id].add(websocket)

        # Register user connection
        self._user_connections[user_id] = websocket

        # Store metadata
        self._connection_meta[websocket] = {
            "team_id": team_id,
            "user_id": user_id,
            "connected_at": datetime.utcnow().isoformat(),
            "subscriptions": subscriptions or ["*"],
        }

        self._total_connections += 1

        logger.info(
            "ws_connected",
            team_id=team_id,
            user_id=user_id,
            active_connections=len(self._team_connections.get(team_id, set())),
        )

        # Send catch-up events from history
        await self._send_history(websocket, team_id)

    def disconnect(self, websocket: WebSocket):
        """Remove a disconnected WebSocket."""
        meta = self._connection_meta.pop(websocket, {})
        team_id = meta.get("team_id")
        user_id = meta.get("user_id")

        if team_id and team_id in self._team_connections:
            self._team_connections[team_id].discard(websocket)
            if not self._team_connections[team_id]:
                del self._team_connections[team_id]

        if user_id and user_id in self._user_connections:
            if self._user_connections[user_id] == websocket:
                del self._user_connections[user_id]

        logger.info("ws_disconnected", team_id=team_id, user_id=user_id)

    async def broadcast_to_team(self, team_id: str, event: WSEvent):
        """Send an event to all connections in a team."""
        connections = self._team_connections.get(team_id, set())
        if not connections:
            return

        message = self._serialize_event(event)

        # Store in history
        self._add_to_history(team_id, message)

        # Send to all team members
        dead_connections = set()
        for ws in connections:
            if self._should_send(ws, event):
                try:
                    await ws.send_json(message)
                    self._total_messages_sent += 1
                except Exception:
                    dead_connections.add(ws)

        # Clean up dead connections
        for ws in dead_connections:
            self.disconnect(ws)

    async def send_to_user(self, user_id: str, event: WSEvent):
        """Send an event to a specific user."""
        ws = self._user_connections.get(user_id)
        if not ws:
            return

        message = self._serialize_event(event)

        try:
            await ws.send_json(message)
            self._total_messages_sent += 1
        except Exception:
            self.disconnect(ws)

    async def broadcast_all(self, event: WSEvent):
        """Broadcast to all connected clients."""
        message = self._serialize_event(event)

        dead_connections = set()
        for team_connections in self._team_connections.values():
            for ws in team_connections:
                try:
                    await ws.send_json(message)
                    self._total_messages_sent += 1
                except Exception:
                    dead_connections.add(ws)

        for ws in dead_connections:
            self.disconnect(ws)

    # ---- Convenience methods for common events ----

    async def notify_lead_created(self, team_id: str, lead: Dict[str, Any]):
        """Notify team of a new lead."""
        await self.broadcast_to_team(team_id, WSEvent(
            event_type=WSEventType.LEAD_CREATED,
            data={
                "lead_id": lead.get("id"),
                "name": f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip(),
                "email": lead.get("email"),
                "company": lead.get("company_name"),
                "source": lead.get("source"),
                "score": lead.get("score", 0),
            },
            team_id=team_id,
        ))

    async def notify_lead_scored(self, team_id: str, lead_id: str, old_score: float, new_score: float):
        """Notify team of a score change."""
        await self.broadcast_to_team(team_id, WSEvent(
            event_type=WSEventType.LEAD_SCORED,
            data={
                "lead_id": lead_id,
                "old_score": old_score,
                "new_score": new_score,
                "direction": "up" if new_score > old_score else "down",
                "category": "hot" if new_score >= 75 else ("warm" if new_score >= 45 else "cold"),
            },
            team_id=team_id,
        ))

    async def notify_scrape_completed(self, team_id: str, job_type: str, records_found: int):
        """Notify of scrape job completion."""
        await self.broadcast_to_team(team_id, WSEvent(
            event_type=WSEventType.SCRAPE_COMPLETED,
            data={"job_type": job_type, "records_found": records_found},
            team_id=team_id,
        ))

    async def notify_visitor_active(self, team_id: str, visitor_data: Dict):
        """Notify of a visitor on site."""
        await self.broadcast_to_team(team_id, WSEvent(
            event_type=WSEventType.VISITOR_ACTIVE,
            data=visitor_data,
            team_id=team_id,
        ))

    async def send_import_progress(self, team_id: str, user_id: str, progress: Dict):
        """Send import progress to the user who triggered it."""
        await self.send_to_user(user_id, WSEvent(
            event_type=WSEventType.IMPORT_PROGRESS,
            data=progress,
            team_id=team_id,
            user_id=user_id,
        ))

    async def send_notification(self, user_id: str, notification: Dict):
        """Push a notification to a specific user."""
        await self.send_to_user(user_id, WSEvent(
            event_type=WSEventType.NOTIFICATION,
            data=notification,
            user_id=user_id,
        ))

    # ---- Internal helpers ----

    def _serialize_event(self, event: WSEvent) -> Dict[str, Any]:
        """Serialize event for JSON transmission."""
        return {
            "type": event.event_type.value,
            "data": event.data,
            "timestamp": event.timestamp,
        }

    def _should_send(self, ws: WebSocket, event: WSEvent) -> bool:
        """Check if this connection subscribed to this event type."""
        meta = self._connection_meta.get(ws, {})
        subs = meta.get("subscriptions", ["*"])
        if "*" in subs:
            return True
        return event.event_type.value in subs

    def _add_to_history(self, team_id: str, message: Dict):
        """Add event to history buffer."""
        if team_id not in self._event_history:
            self._event_history[team_id] = []
        self._event_history[team_id].append(message)
        # Trim to size
        if len(self._event_history[team_id]) > self._history_size:
            self._event_history[team_id] = self._event_history[team_id][-self._history_size:]

    async def _send_history(self, ws: WebSocket, team_id: str):
        """Send recent event history to a newly connected client."""
        history = self._event_history.get(team_id, [])
        if history:
            try:
                await ws.send_json({
                    "type": "history",
                    "data": {"events": history[-20:]},  # Last 20 events
                    "timestamp": datetime.utcnow().isoformat(),
                })
            except Exception:
                pass

    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics."""
        return {
            "total_connections_ever": self._total_connections,
            "active_connections": sum(len(c) for c in self._team_connections.values()),
            "active_teams": len(self._team_connections),
            "total_messages_sent": self._total_messages_sent,
            "connections_per_team": {
                team: len(conns) for team, conns in self._team_connections.items()
            },
        }


# Global instance
ws_manager = WebSocketManager()

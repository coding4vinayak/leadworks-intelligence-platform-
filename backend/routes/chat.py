"""AI Chat routes - conversational interface for lead intelligence."""
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.routes.auth import get_current_user
from backend.services.chatbot import SalesAssistant

router = APIRouter()
assistant = SalesAssistant()


class ChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None  # current_lead, current_page, etc.


class BriefingRequest(BaseModel):
    period: str = "today"


class NextActionsRequest(BaseModel):
    lead_data: dict


class AskRequest(BaseModel):
    question: str
    data_context: dict = {}


@router.post("/message")
async def chat_message(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """Send a message to the AI sales assistant."""
    result = await assistant.chat(
        message=request.message,
        user_id=current_user["sub"],
        team_id=current_user.get("team_id"),
        context=request.context,
    )
    return result


@router.get("/briefing")
async def daily_briefing(
    current_user: dict = Depends(get_current_user),
):
    """Get AI-generated daily sales briefing."""
    team_id = current_user.get("team_id", "default")
    return await assistant.get_daily_briefing(team_id)


@router.post("/next-actions")
async def next_actions(
    request: NextActionsRequest,
    current_user: dict = Depends(get_current_user),
):
    """Get AI-suggested next actions for a lead."""
    actions = await assistant.suggest_next_actions(request.lead_data)
    return {"actions": actions}


@router.post("/ask")
async def ask_question(
    request: AskRequest,
    current_user: dict = Depends(get_current_user),
):
    """Ask a data question with context."""
    answer = await assistant.answer_question(request.question, request.data_context)
    return {"answer": answer, "question": request.question}


@router.post("/clear-history")
async def clear_chat_history(current_user: dict = Depends(get_current_user)):
    """Clear conversation history."""
    assistant.clear_history()
    return {"cleared": True}

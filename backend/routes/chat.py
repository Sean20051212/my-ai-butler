from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.conversation import run_turn

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
async def chat(request: ChatRequest, req: Request):
    """One-shot HTTP turn. Shares the same brain as the WebSocket transport."""
    return await run_turn(request.message, req.app.state.character, req.app.state.memory)

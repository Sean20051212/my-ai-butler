from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.models.character import CharacterState
from backend.routes.chat import router as chat_router
from backend.services.memory import MemoryService
from backend.services.vision import start_vision_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────
    app.state.character = CharacterState()
    app.state.memory    = MemoryService()
    start_vision_loop(app.state.character)
    print("Hiyori is ready.")
    yield
    # ── Shutdown ───────────────────────────────────────────────────────
    print("Hiyori shutting down.")


app = FastAPI(title="my-ai-butler", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)

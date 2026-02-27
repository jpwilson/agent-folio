from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from routers.agent import router as agent_router
from routers.admin import router as admin_router
from services.db import init_db, close_db
from config import HOST, PORT, GHOSTFOLIO_PUBLIC_URL
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(title="Agent-Folio", description="AI Financial Agent for Ghostfolio", lifespan=lifespan)

# CORS — allow Ghostfolio frontend and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(agent_router)
app.include_router(admin_router)

# Serve static files (chat UI)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    """Serve the agent chat UI."""
    html_path = os.path.join(static_dir, "agent-chat.html")
    if os.path.exists(html_path):
        return FileResponse(
            html_path,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
    return {"status": "ok", "service": "agent-folio"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/v1/agent/config")
async def get_config():
    """Public config for the chat UI."""
    return {"ghostfolioUrl": GHOSTFOLIO_PUBLIC_URL}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)

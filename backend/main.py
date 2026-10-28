"""FastAPI application entry point."""
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router as chat_router
from backend.api.stream import router as stream_router
from backend.api.auth import router as auth_router
from backend.api.traces import router as traces_router
from backend.config.logging_config import setup_logging

# Register ALL SQLAlchemy models before any query can fire
import backend.models  # noqa: F401
from backend.models.base import init_db

# Initialize structured logging
setup_logging()

app = FastAPI(title="Real Estate Rent Agent", version="2.0.0")

# CORS — allow frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(chat_router, prefix="/api")
app.include_router(stream_router, prefix="/api")
app.include_router(auth_router, prefix="/api/auth")
app.include_router(traces_router, prefix="/api")


@app.on_event("startup")
async def startup():
    await init_db()
    from backend.repositories.user_repository import UserRepository
    await UserRepository().ensure_admin_user()


# Health check
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "system": "multi-agent"}


# Serve frontend static files
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

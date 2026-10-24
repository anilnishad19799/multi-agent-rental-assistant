from fastapi import APIRouter
from backend.streaming.sse_manager import SSEManager

router = APIRouter()
sse = SSEManager()

@router.get("/stream/{session_id}")
async def stream(session_id: str):
    return sse.stream(session_id)
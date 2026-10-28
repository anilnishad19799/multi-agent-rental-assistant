"""Observability API routes for traces, agent spans, and LangSmith status.
Access is strictly protected for administrators (admin@gmail.com).
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.models import User
from backend.api.dependencies import require_admin
from backend.observability.tracing import (
    get_recent_traces,
    get_trace_by_id,
    get_langsmith_info,
    get_distinct_users_with_traces,
    get_traces_summary_stats,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/traces", tags=["observability"])


@router.get("")
async def list_traces(
    limit: int = Query(50, ge=1, le=500, description="Max traces to return"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    user_email: Optional[str] = Query(None, description="Filter by user email"),
    agent: Optional[str] = Query(None, description="Filter by agent invoked"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (SUCCESS / ERROR)"),
    current_admin: User = Depends(require_admin),
):
    """Retrieve recent traces across all API calls, filtered user-wise, agent-wise, or status-wise.
    Restricted to Administrator only.
    """
    try:
        traces = await get_recent_traces(
            limit=limit,
            user_id=user_id,
            user_email=user_email,
            agent=agent,
            status=status_filter,
        )
        return {
            "total": len(traces),
            "traces": traces,
        }
    except Exception as e:
        logger.error(f"Error fetching traces: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve traces: {str(e)}",
        )


@router.get("/users")
async def list_trace_users(current_admin: User = Depends(require_admin)):
    """List all distinct users who have executed requests/traces for user-wise inspection.
    Restricted to Administrator only.
    """
    try:
        users = await get_distinct_users_with_traces()
        return {"users": users, "total": len(users)}
    except Exception as e:
        logger.error(f"Error fetching trace users: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve trace users: {str(e)}",
        )


@router.get("/stats")
async def traces_statistics(current_admin: User = Depends(require_admin)):
    """Retrieve aggregate observability stats (runs, avg latency, success rate, agent breakdown).
    Restricted to Administrator only.
    """
    try:
        return await get_traces_summary_stats()
    except Exception as e:
        logger.error(f"Error calculating trace stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute trace metrics: {str(e)}",
        )


@router.get("/config/langsmith")
async def langsmith_status(current_admin: User = Depends(require_admin)):
    """Get LangSmith cloud configuration, status, and direct project dashboard link.
    Restricted to Administrator only.
    """
    return get_langsmith_info()


@router.get("/{trace_id}")
async def get_trace(trace_id: str, current_admin: User = Depends(require_admin)):
    """Get full details and execution span tree for a specific trace.
    Restricted to Administrator only.
    """
    trace = await get_trace_by_id(trace_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace with ID '{trace_id}' not found",
        )
    return trace

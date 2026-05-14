from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(tags=["Logs"])


def _logger(request: Request):
    return request.app.state.logger


@router.get("/logs")
def get_logs(request: Request, limit: int = Query(default=100, ge=1, le=1000)):
    try:
        logs = _logger(request).get_logs(limit=limit)
        return {"count": len(logs), "items": logs}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

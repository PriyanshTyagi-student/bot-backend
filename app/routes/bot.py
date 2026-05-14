from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/bot", tags=["Bot Control"])


def _engine(request: Request):
    return request.app.state.bot_engine


@router.post("/start")
def start_bot(request: Request):
    try:
        return _engine(request).start()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/stop")
def stop_bot(request: Request):
    try:
        return _engine(request).stop()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/emergency-stop")
def emergency_stop_bot(request: Request):
    try:
        return _engine(request).emergency_stop()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/status")
def bot_status(request: Request):
    try:
        return _engine(request).status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

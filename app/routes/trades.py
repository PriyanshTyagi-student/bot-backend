from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/trades", tags=["Trading"])


def _mt5(request: Request):
    return request.app.state.mt5_service


@router.get("")
def get_open_trades(request: Request):
    try:
        trades = _mt5(request).get_open_trades()
        return {"count": len(trades), "items": trades}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/history")
def get_trade_history(request: Request):
    try:
        trades = _mt5(request).get_trade_history()
        return {"count": len(trades), "items": trades}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

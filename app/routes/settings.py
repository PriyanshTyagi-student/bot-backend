from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import (
    AccountSchema,
    MT5ConnectionStatusSchema,
    MT5SettingsUpdateRequest,
    MT5SettingsView,
    StrategySettings,
    StrategyUpdateRequest,
)

router = APIRouter(tags=["Settings"])


def _strategy(request: Request):
    return request.app.state.strategy_service


def _mt5(request: Request):
    return request.app.state.mt5_service


@router.get("/mt5/settings", response_model=MT5SettingsView)
def get_mt5_settings(request: Request):
    try:
        return _mt5(request).get_settings_view()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/mt5/status", response_model=MT5ConnectionStatusSchema)
def get_mt5_status(request: Request):
    try:
        return _mt5(request).get_connection_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/mt5/connect", response_model=MT5ConnectionStatusSchema)
def connect_mt5(payload: MT5SettingsUpdateRequest, request: Request):
    try:
        return _mt5(request).connect_with_settings(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/mt5/disconnect", response_model=MT5ConnectionStatusSchema)
def disconnect_mt5(request: Request):
    try:
        return _mt5(request).disconnect()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/strategy", response_model=StrategySettings)
def get_strategy_settings(request: Request):
    try:
        return _strategy(request).get_settings()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/strategy/update", response_model=StrategySettings)
def update_strategy_settings(payload: StrategyUpdateRequest, request: Request):
    try:
        return _strategy(request).update_settings(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/account", response_model=AccountSchema)
def get_account_info(request: Request):
    try:
        return _mt5(request).get_account_info()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

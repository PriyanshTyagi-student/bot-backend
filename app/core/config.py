from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from app.models.schemas import AppSettings, MT5Settings, RiskSettings, StrategySettings

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SETTINGS_PATH = ROOT_DIR / "data" / "settings.json"


class ConfigManager:
    def __init__(self, settings_path: str | Path | None = None) -> None:
        self.settings_path = Path(settings_path or os.getenv("FOREX_BOT_SETTINGS_PATH", DEFAULT_SETTINGS_PATH))
        self._lock = threading.RLock()
        self._settings = self._load_or_create()

    def _load_or_create(self) -> AppSettings:
        if not self.settings_path.exists():
            settings = AppSettings()
            self._write_settings(settings)
            return settings

        try:
            raw_data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return AppSettings.model_validate(raw_data)
        except Exception:
            settings = AppSettings()
            self._write_settings(settings)
            return settings

    def _write_settings(self, settings: AppSettings) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        payload = settings.model_dump(mode="json")
        self.settings_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get_settings(self) -> AppSettings:
        with self._lock:
            return self._settings.model_copy(deep=True)

    def save_settings(self, settings: AppSettings) -> AppSettings:
        with self._lock:
            self._settings = settings.model_copy(deep=True)
            self._write_settings(self._settings)
            return self.get_settings()

    def update_settings(self, **updates: Any) -> AppSettings:
        with self._lock:
            current = self._settings.model_dump()
            for key, value in updates.items():
                if value is not None:
                    current[key] = value
            self._settings = AppSettings.model_validate(current)
            self._write_settings(self._settings)
            return self.get_settings()

    def get_api_settings(self):
        return self.get_settings().api

    def get_bot_settings(self):
        return self.get_settings().bot

    def get_strategy_settings(self) -> StrategySettings:
        return self.get_settings().strategy

    def update_strategy_settings(self, payload: StrategySettings | dict[str, Any]) -> StrategySettings:
        with self._lock:
            current = self._settings.model_dump()
            strategy_dict = current["strategy"]
            if isinstance(payload, StrategySettings):
                strategy_dict = payload.model_dump()
            else:
                strategy_dict.update({key: value for key, value in payload.items() if value is not None})
            current["strategy"] = strategy_dict
            self._settings = AppSettings.model_validate(current)
            self._write_settings(self._settings)
            return self._settings.strategy.model_copy(deep=True)

    def get_risk_settings(self) -> RiskSettings:
        return self.get_settings().risk

    def update_risk_settings(self, payload: RiskSettings | dict[str, Any]) -> RiskSettings:
        with self._lock:
            current = self._settings.model_dump()
            risk_dict = current["risk"]
            if isinstance(payload, RiskSettings):
                risk_dict = payload.model_dump()
            else:
                risk_dict.update({key: value for key, value in payload.items() if value is not None})
            current["risk"] = risk_dict
            self._settings = AppSettings.model_validate(current)
            self._write_settings(self._settings)
            return self._settings.risk.model_copy(deep=True)

    def get_mt5_settings(self) -> MT5Settings:
        return self.get_settings().mt5

    def update_mt5_settings(self, payload: MT5Settings | dict[str, Any]) -> MT5Settings:
        with self._lock:
            current = self._settings.model_dump()
            mt5_dict = current["mt5"]
            if isinstance(payload, MT5Settings):
                mt5_dict = payload.model_dump()
            else:
                mt5_dict.update({key: value for key, value in payload.items() if value is not None})
            current["mt5"] = mt5_dict
            self._settings = AppSettings.model_validate(current)
            self._write_settings(self._settings)
            return self._settings.mt5.model_copy(deep=True)

    def get_log_settings(self):
        return self.get_settings().logging

    def get_snapshot(self) -> dict[str, Any]:
        return self.get_settings().model_dump(mode="json")

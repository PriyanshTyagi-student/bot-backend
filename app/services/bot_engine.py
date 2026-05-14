from __future__ import annotations

import threading
from datetime import UTC, date, datetime
from typing import Any

from app.core.config import ConfigManager
from app.core.logger import BotLogger
from app.models.schemas import BotStatusSchema
from app.services.mt5_service import MT5Service
from app.services.risk_management import RiskManagementService
from app.services.strategy import StrategyService


class BotEngine:
    def __init__(
        self,
        mt5_service: MT5Service,
        strategy_service: StrategyService,
        risk_service: RiskManagementService,
        logger: BotLogger,
        config_manager: ConfigManager,
    ) -> None:
        self.mt5_service = mt5_service
        self.strategy_service = strategy_service
        self.risk_service = risk_service
        self.logger = logger
        self.config_manager = config_manager
        self._state_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self._emergency_stopped = False
        self._last_run_at: datetime | None = None
        self._last_error: str | None = None
        self._last_signal: str | None = None
        self._trades_today = 0
        self._active_day = date.today()

    def start(self) -> dict[str, Any]:
        with self._state_lock:
            if self._running:
                return {"success": True, "message": "Bot is already running.", "status": self.status().model_dump(mode="json")}

            self._stop_event.clear()
            self._emergency_stopped = False
            self._last_error = None
            connect_result = self.mt5_service.connect()
            self._running = True
            self._thread = threading.Thread(target=self._run_loop, name="ForexBotEngine", daemon=True)
            self._thread.start()
            self.logger.info("Bot engine started", source="bot", metadata=connect_result)
            return {"success": True, "message": "Bot started.", "status": self.status().model_dump(mode="json")}

    def stop(self) -> dict[str, Any]:
        self._request_stop("Bot stop requested.")
        return {"success": True, "message": "Bot stopped.", "status": self.status().model_dump(mode="json")}

    def emergency_stop(self) -> dict[str, Any]:
        self._emergency_stopped = True
        close_result = self.mt5_service.close_all_open_trades() if self.config_manager.get_bot_settings().emergency_close_positions else {"success": True, "closed_count": 0, "errors": []}
        self._request_stop("Emergency stop requested.")
        self.logger.warning("Emergency stop executed", source="bot", metadata=close_result)
        return {"success": close_result.get("success", True), "message": "Emergency stop executed.", "status": self.status().model_dump(mode="json")}

    def status(self) -> BotStatusSchema:
        open_trades = self.mt5_service.get_open_trades()
        settings = self.config_manager.get_bot_settings()
        self._reset_daily_counters_if_needed()
        return BotStatusSchema(
            running=self._running,
            emergency_stopped=self._emergency_stopped,
            last_run_at=self._last_run_at,
            strategy_interval_seconds=settings.strategy_interval_seconds,
            open_trades=len(open_trades),
            trades_today=self._trades_today,
            last_signal=self._last_signal,
            last_error=self._last_error,
            mode=self.mt5_service.mode,
        )

    def _request_stop(self, message: str) -> None:
        with self._state_lock:
            self._stop_event.set()
            self._running = False
            if self._thread and self._thread.is_alive() and threading.current_thread() is not self._thread:
                self._thread.join(timeout=5)
            self._thread = None
            self.logger.info(message, source="bot")

    def _reset_daily_counters_if_needed(self) -> None:
        current_day = date.today()
        if current_day != self._active_day:
            self._active_day = current_day
            self._trades_today = 0

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._execute_cycle()
            except Exception as exc:  # pragma: no cover - defensive runtime guard
                self._last_error = str(exc)
                self.logger.error(f"Bot cycle failed: {exc}", source="bot")

            interval = max(1, self.config_manager.get_bot_settings().strategy_interval_seconds)
            if self._stop_event.wait(interval):
                break

        with self._state_lock:
            self._running = False

    def _execute_cycle(self) -> None:
        settings = self.config_manager.get_bot_settings()
        if not settings.enabled:
            self._last_run_at = datetime.now(UTC)
            self.logger.info("Bot is disabled in settings; cycle skipped.", source="bot")
            return

        self._reset_daily_counters_if_needed()
        self._last_run_at = datetime.now(UTC)

        account_info = self.mt5_service.get_account_info()
        open_trades = self.mt5_service.get_open_trades()
        risk_decision = self.risk_service.evaluate(open_trades, self._trades_today, account_info)
        # If TEST_MODE is enabled, override risk blocking so forced test trades can run
        try:
            if getattr(self.strategy_service, "TEST_MODE", False) or globals().get("TEST_MODE", False):
                risk_decision = {"allowed": True, "should_stop_bot": False, "reasons": []}
        except Exception:
            pass

        if risk_decision["should_stop_bot"]:
            self._last_error = "; ".join(risk_decision["reasons"]) or "Risk control stopped the bot."
            self.logger.warning(self._last_error, source="bot")
            self._request_stop(self._last_error)
            return

        if not risk_decision["allowed"]:
            self._last_error = "; ".join(risk_decision["reasons"])
            return

        # Generate signal using strategy service (strategy now fetches its own candle data)
        signal = self.strategy_service.generate_signal(settings.symbol)
        self._last_signal = signal.get("signal")

        # If TEST_MODE is enabled in strategy, override risk blocking so test trades can run
        try:
            if getattr(self.strategy_service, "TEST_MODE", False) or globals().get("TEST_MODE", False):
                risk_decision = {"allowed": True, "should_stop_bot": False, "reasons": []}
        except Exception:
            pass

        if signal.get("signal") not in {"buy", "sell"}:
            self.logger.info("No trade signal generated.", source="strategy", metadata=signal)
            return

        # Safety: ensure no open positions (one trade at a time)
        if len(open_trades) > 0:
            self.logger.info("Existing open trades found; skipping new order.", source="bot", metadata={"open_trades": len(open_trades)})
            return

        # Safety: ensure symbol is visible/available and market data present
        if not self.mt5_service.ensure_symbol_visible(settings.symbol):
            self.logger.error(f"Symbol {settings.symbol} not available; skipping order.", source="bot")
            return

        order_result = self.mt5_service.place_order(
            side=signal["signal"],
            symbol=settings.symbol,
            volume=settings.lot_size,
            sl_pips=self.config_manager.get_strategy_settings().stop_loss_pips,
            tp_pips=self.config_manager.get_strategy_settings().take_profit_pips,
            comment=settings.comment,
            magic_number=settings.magic_number,
        )

        if order_result.get("success"):
            self._trades_today += 1
            self._last_error = None
            self.logger.info("Trade executed successfully.", source="bot", metadata=order_result)
            return

        self._last_error = order_result.get("message", "Order execution failed.")
        self.logger.error(self._last_error, source="bot", metadata=order_result)

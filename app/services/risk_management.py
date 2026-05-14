from __future__ import annotations

from typing import Any

from app.core.config import ConfigManager
from app.core.logger import BotLogger


class RiskManagementService:
    def __init__(self, config_manager: ConfigManager, logger: BotLogger) -> None:
        self.config_manager = config_manager
        self.logger = logger

    def evaluate(self, open_trades: list[dict[str, Any]], trades_today: int, account_info: dict[str, Any]) -> dict[str, Any]:
        settings = self.config_manager.get_risk_settings()
        reasons: list[str] = []
        stop_bot = False

        if settings.one_trade_at_a_time and len(open_trades) >= 1:
            reasons.append("Only one trade is allowed at a time.")

        if len(open_trades) > settings.max_open_positions:
            reasons.append("The open position limit has been reached.")

        if trades_today >= settings.max_trades_per_day:
            reasons.append("The daily trade limit has been reached.")

        balance = float(account_info.get("balance") or 0.0)
        equity = float(account_info.get("equity") or balance)
        if balance > 0:
            daily_loss_percent = max(0.0, (balance - equity) / balance * 100)
            if daily_loss_percent >= settings.max_daily_loss_percent:
                reasons.append("Daily loss threshold has been exceeded.")
                stop_bot = True
        else:
            daily_loss_percent = 0.0

        allowed = not reasons
        decision = {
            "allowed": allowed,
            "should_stop_bot": stop_bot,
            "reasons": reasons,
            "daily_loss_percent": daily_loss_percent,
        }

        if not allowed:
            self.logger.warning("Risk check blocked a trade", source="risk", metadata=decision)

        return decision

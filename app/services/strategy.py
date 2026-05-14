from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, List, Tuple

from app.core.config import ConfigManager
from app.core.logger import BotLogger
from app.models.schemas import BotSignal, StrategySettings, StrategyUpdateRequest
from app.services.mt5_service import MT5Service

# Toggle for forcing a test trade (useful for debugging/demo)
TEST_MODE = True


class StrategyService:
    """Strategy service that computes indicators and returns trade signals.

    Refactored into helper functions:
    - get_data: fetches candle history
    - calculate_indicators: compute MA50, MA200, RSI
    - generate_signal: decide BUY/SELL/HOLD
    """

    def __init__(self, config_manager: ConfigManager, logger: BotLogger, mt5_service: MT5Service) -> None:
        self.config_manager = config_manager
        self.logger = logger
        self.mt5_service = mt5_service
        self._lock = threading.RLock()
        # expose TEST_MODE on the instance for other components to read
        self.TEST_MODE = TEST_MODE

    def get_settings(self) -> StrategySettings:
        return self.config_manager.get_strategy_settings()

    def update_settings(self, payload: StrategyUpdateRequest | dict[str, Any]) -> StrategySettings:
        data = payload.model_dump(exclude_unset=True) if isinstance(payload, StrategyUpdateRequest) else payload
        updated = self.config_manager.update_strategy_settings(data)
        self.logger.info("Strategy settings updated", source="strategy", metadata=updated.model_dump())
        return updated

    def get_data(self, symbol: str, count: int = 300) -> list[dict[str, Any]]:
        """Fetch candles ensuring we have sufficient history for indicators."""
        # Ensure MT5 is initialized and symbol visible
        if not self.mt5_service.ensure_symbol_visible(symbol):
            self.logger.error(f"Symbol {symbol} not visible or available.", source="strategy")
            return []

        candles = self.mt5_service.get_candles(symbol, count=count)
        if not candles:
            self.logger.warning(f"No candle data for {symbol}", source="strategy")
        return candles

    def calculate_indicators(self, closes: List[float]) -> Tuple[float, float, float]:
        """Calculate MA50, MA200 and RSI(14) from list of close prices.

        Returns (ma50, ma200, rsi)
        """
        # moving averages
        def ma(values: List[float], n: int) -> float:
            if len(values) < n:
                return sum(values) / len(values) if values else 0.0
            return sum(values[-n:]) / n

        ma50 = ma(closes, 50)
        ma200 = ma(closes, 200)

        # RSI(14)
        period = 14
        gains = 0.0
        losses = 0.0
        for i in range(-period, -1):
            diff = closes[i+1] - closes[i]
            if diff > 0:
                gains += diff
            else:
                losses -= diff

        if gains + losses == 0:
            rsi = 50.0
        else:
            avg_gain = gains / period
            avg_loss = losses / period if losses != 0 else 0.000001
            rs = avg_gain / avg_loss if avg_loss else float('inf')
            rsi = 100 - (100 / (1 + rs))

        return round(ma50, 6), round(ma200, 6), round(rsi, 2)

    def generate_signal(self, symbol: str) -> dict[str, Any]:
        """Main signal generator. Returns dict with signal and debug info.

        Logic:
        - If TEST_MODE enabled -> force BUY (for demo/testing)
        - BUY when MA50 > MA200
        - SELL when MA50 < MA200
        - RSI is optional filter and does not block signals by default
        """
        settings = self.get_settings()

        # Fetch candles
        candles = self.get_data(symbol, count=300)
        closes = [c.get("close") for c in candles if c.get("close") is not None]

        # Forced test trade - run regardless of candle availability
        if getattr(self, "TEST_MODE", False):
            self.logger.info("TEST_MODE enabled - forcing BUY signal", source="strategy")
            price = closes[-1] if closes else None
            self.logger.info(f"PRICE: {price}", source="strategy")
            return {"signal": "buy", "reason": "TEST_MODE forced buy", "symbol": symbol, "ma50": None, "ma200": None, "rsi": None}

        if len(closes) < 50:
            return {"signal": "hold", "reason": "Not enough candle data", "symbol": symbol}

        ma50, ma200, rsi = self.calculate_indicators(closes)

        # Logging the key debug values
        self.logger.info(f"PRICE: {closes[-1]}", source="strategy")
        self.logger.info(f"MA50: {ma50} | MA200: {ma200} | RSI: {rsi}", source="strategy")

        # Simple MA cross logic
        if ma50 > ma200:
            signal = "buy"
            reason = "MA50 > MA200"
        elif ma50 < ma200:
            signal = "sell"
            reason = "MA50 < MA200"
        else:
            signal = "hold"
            reason = "MAs are equal"

        return {"signal": signal, "reason": reason, "symbol": symbol, "ma50": ma50, "ma200": ma200, "rsi": rsi}

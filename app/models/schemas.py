from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

BotSignal = Literal["buy", "sell", "hold"]
TradeSide = Literal["buy", "sell"]


class ApiResponse(BaseModel):
    message: str
    success: bool = True
    data: dict[str, Any] | list[Any] | None = None


class ApiSettings(BaseModel):
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    title: str = "Forex Trading Bot API"
    debug: bool = False


class BotSettings(BaseModel):
    enabled: bool = True
    strategy_interval_seconds: int = 5
    symbol: str = "EURUSD"
    lot_size: float = 0.01
    magic_number: int = 20260504
    comment: str = "Forex Trading Bot"
    emergency_close_positions: bool = True


class StrategySettings(BaseModel):
    symbol: str = "EURUSD"
    momentum_threshold: float = 0.0005
    spread_limit: float = 0.0003
    fast_ma_period: int = 9
    slow_ma_period: int = 21
    take_profit_pips: int = 50
    stop_loss_pips: int = 25


class StrategyUpdateRequest(BaseModel):
    symbol: str | None = None
    momentum_threshold: float | None = None
    spread_limit: float | None = None
    fast_ma_period: int | None = None
    slow_ma_period: int | None = None
    take_profit_pips: int | None = None
    stop_loss_pips: int | None = None


class RiskSettings(BaseModel):
    one_trade_at_a_time: bool = True
    max_trades_per_day: int = 5
    max_daily_loss_percent: float = 5.0
    max_open_positions: int = 1


class MT5Settings(BaseModel):
    terminal_path: str | None = None
    login: int | None = None
    password: str | None = None
    server: str | None = None
    timeout: int = 60000
    portable: bool = False
    demo_balance: float = 10000.0
    demo_currency: str = "USD"
    demo_leverage: int = 100


class MT5SettingsUpdateRequest(BaseModel):
    terminal_path: str | None = None
    login: int | None = None
    password: str | None = None
    server: str | None = None
    timeout: int | None = None
    portable: bool | None = None
    demo_balance: float | None = None
    demo_currency: str | None = None
    demo_leverage: int | None = None


class MT5SettingsView(BaseModel):
    terminal_path: str | None = None
    login: int | None = None
    server: str | None = None
    timeout: int = 60000
    portable: bool = False
    demo_balance: float = 10000.0
    demo_currency: str = "USD"
    demo_leverage: int = 100


class MT5ConnectionStatusSchema(BaseModel):
    connected: bool
    mode: str
    message: str
    terminal_path: str | None = None
    login: int | None = None
    server: str | None = None
    timeout: int | None = None
    portable: bool | None = None
    source: str = "mt5"


class LoggingSettings(BaseModel):
    max_in_memory_logs: int = 1000
    log_file: str = "logs/bot.log"
    persist_to_file: bool = True


class AppSettings(BaseModel):
    api: ApiSettings = Field(default_factory=ApiSettings)
    bot: BotSettings = Field(default_factory=BotSettings)
    strategy: StrategySettings = Field(default_factory=StrategySettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    mt5: MT5Settings = Field(default_factory=MT5Settings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


class TradeSchema(BaseModel):
    ticket: int
    symbol: str
    side: TradeSide
    volume: float
    price_open: float | None = None
    price_current: float | None = None
    profit: float | None = None
    sl: float | None = None
    tp: float | None = None
    time_open: datetime | None = None
    time_close: datetime | None = None
    magic_number: int | None = None
    comment: str | None = None
    source: str = "mt5"


class AccountSchema(BaseModel):
    login: int | None = None
    balance: float
    equity: float
    margin: float | None = None
    free_margin: float | None = None
    profit: float | None = None
    currency: str = "USD"
    leverage: int | None = None
    server: str | None = None
    source: str = "mt5"


class LogEntrySchema(BaseModel):
    timestamp: datetime
    level: str
    message: str
    source: str = "system"
    metadata: dict[str, Any] | None = None


class BotStatusSchema(BaseModel):
    running: bool
    emergency_stopped: bool
    last_run_at: datetime | None = None
    strategy_interval_seconds: int
    open_trades: int = 0
    trades_today: int = 0
    last_signal: BotSignal | None = None
    last_error: str | None = None
    mode: str = "simulation"


class BotActionResponse(BaseModel):
    success: bool = True
    message: str
    status: BotStatusSchema | None = None

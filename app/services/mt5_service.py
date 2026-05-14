from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
import random

from app.core.config import ConfigManager
from app.core.logger import BotLogger
from app.models.schemas import MT5ConnectionStatusSchema, MT5Settings, MT5SettingsUpdateRequest

try:
    import MetaTrader5 as mt5  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    mt5 = None


class MT5Service:
    def __init__(self, config_manager: ConfigManager, logger: BotLogger) -> None:
        self.config_manager = config_manager
        self.logger = logger
        self._connected = False
        self._mode = "simulation"
        self._simulation_ticket = 100000
        self._simulation_prices: dict[str, float] = {}
        self._simulation_positions: list[dict[str, Any]] = []
        self._simulation_history: list[dict[str, Any]] = []

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> dict[str, Any]:
        settings = self.config_manager.get_mt5_settings()
        if mt5 is None:
            self._connected = False
            self._mode = "simulation"
            message = "MetaTrader 5 package is unavailable. Running in simulation mode."
            self.logger.warning(message, source="mt5")
            return {"connected": False, "mode": self._mode, "message": message}

        initialize_kwargs: dict[str, Any] = {
            "timeout": settings.timeout,
            "portable": settings.portable,
        }
        if settings.terminal_path:
            initialize_kwargs["path"] = settings.terminal_path

        if not mt5.initialize(**initialize_kwargs):
            error_message = f"MT5 initialize failed: {mt5.last_error()}"
            self._connected = False
            self._mode = "simulation"
            self.logger.error(error_message, source="mt5")
            return {"connected": False, "mode": self._mode, "message": error_message}

        if settings.login and settings.password and settings.server:
            if not mt5.login(settings.login, password=settings.password, server=settings.server):
                error_message = f"MT5 login failed: {mt5.last_error()}"
                mt5.shutdown()
                self._connected = False
                self._mode = "simulation"
                self.logger.error(error_message, source="mt5")
                return {"connected": False, "mode": self._mode, "message": error_message}

        self._connected = True
        self._mode = "live"
        message = "Connected to MetaTrader 5."
        self.logger.info(message, source="mt5")
        return {"connected": True, "mode": self._mode, "message": message}

    def update_settings(self, payload: MT5SettingsUpdateRequest | dict[str, Any]) -> MT5Settings:
        data = payload.model_dump(exclude_unset=True) if isinstance(payload, MT5SettingsUpdateRequest) else payload
        updated = self.config_manager.update_mt5_settings(data)
        self.logger.info("MT5 settings updated", source="mt5", metadata=updated.model_dump())
        return updated

    def connect_with_settings(self, payload: MT5SettingsUpdateRequest | dict[str, Any]) -> MT5ConnectionStatusSchema:
        updated = self.update_settings(payload)
        connect_result = self.connect()
        return MT5ConnectionStatusSchema(
            connected=bool(connect_result.get("connected")),
            mode=str(connect_result.get("mode", self.mode)),
            message=str(connect_result.get("message", "")),
            terminal_path=updated.terminal_path,
            login=updated.login,
            server=updated.server,
            timeout=updated.timeout,
            portable=updated.portable,
        )

    def get_settings_view(self) -> dict[str, Any]:
        settings = self.config_manager.get_mt5_settings()
        return {
            "terminal_path": settings.terminal_path,
            "login": settings.login,
            "server": settings.server,
            "timeout": settings.timeout,
            "portable": settings.portable,
            "demo_balance": settings.demo_balance,
            "demo_currency": settings.demo_currency,
            "demo_leverage": settings.demo_leverage,
        }

    def get_connection_status(self) -> MT5ConnectionStatusSchema:
        settings = self.config_manager.get_mt5_settings()
        message = "Connected to MetaTrader 5." if self._connected else "MetaTrader 5 is not connected."
        return MT5ConnectionStatusSchema(
            connected=self._connected,
            mode=self._mode,
            message=message,
            terminal_path=settings.terminal_path,
            login=settings.login,
            server=settings.server,
            timeout=settings.timeout,
            portable=settings.portable,
        )

    def shutdown(self) -> None:
        if mt5 is not None and self._connected:
            mt5.shutdown()
        self._connected = False
        self._mode = "simulation"

    def disconnect(self) -> MT5ConnectionStatusSchema:
        self.shutdown()
        return self.get_connection_status()

    def _build_simulation_tick(self, symbol: str) -> dict[str, Any]:
        base_price = self._simulation_prices.get(symbol, 1.10000)
        price = max(0.0001, base_price + random.uniform(-0.0004, 0.0004))
        self._simulation_prices[symbol] = round(price, 5)
        return {
            "symbol": symbol,
            "bid": round(price - 0.0001, 5),
            "ask": round(price + 0.0001, 5),
            "last": round(price, 5),
            "time": datetime.now(UTC),
            "source": "simulation",
        }

    def get_symbol_tick(self, symbol: str) -> dict[str, Any]:
        if self._mode == "live" and mt5 is not None:
            tick = mt5.symbol_info_tick(symbol)
            if tick is not None:
                return {
                    "symbol": symbol,
                    "bid": tick.bid,
                    "ask": tick.ask,
                    "last": getattr(tick, "last", tick.bid),
                    "time": datetime.fromtimestamp(tick.time, tz=UTC) if getattr(tick, "time", None) else datetime.now(UTC),
                    "source": "mt5",
                }
        return self._build_simulation_tick(symbol)

    def get_candles(self, symbol: str, timeframe: int = None, count: int = 300) -> list[dict[str, Any]]:
        """Return recent candles for `symbol`.

        - In live mode uses MetaTrader5.copy_rates_from_pos / copy_rates_from
        - In simulation mode returns generated synthetic candles based on simulation tick
        """
        # Ensure at least 300 candles for indicator stability
        count = max(300, int(count or 300))

        if self._mode == "live" and mt5 is not None:
            try:
                tf = timeframe if timeframe is not None else mt5.TIMEFRAME_M1
                # copy_rates_from_pos(symbol, start_pos, count, timeframe) is common; use from pos 0
                rates = mt5.copy_rates_from_pos(symbol, 0, count, tf)
                if rates is None:
                    return []
                candles: list[dict[str, Any]] = []
                for r in rates:
                    row = r._asdict() if hasattr(r, "_asdict") else dict(r)
                    candles.append({
                        "time": datetime.fromtimestamp(row.get("time", datetime.now().timestamp()), tz=UTC),
                        "open": float(row.get("open", 0.0)),
                        "high": float(row.get("high", 0.0)),
                        "low": float(row.get("low", 0.0)),
                        "close": float(row.get("close", 0.0)),
                        "tick_volume": int(row.get("tick_volume", 0)),
                    })
                return candles
            except Exception as exc:
                self.logger.error(f"Failed to fetch candles from MT5: {exc}", source="mt5")
                return []

        # Simulation mode: generate simple synthetic candles based on last known price
        candles = []
        base = self._simulation_prices.get(symbol, 1.10000)
        price = base
        for i in range(count):
            # create small random walk
            o = price
            c = max(0.0001, round(o + random.uniform(-0.0010, 0.0010), 5))
            h = max(o, c) + random.uniform(0.0, 0.0005)
            l = min(o, c) - random.uniform(0.0, 0.0005)
            candles.append({
                "time": datetime.now(UTC) - timedelta(minutes=(count - i)),
                "open": round(o, 5),
                "high": round(h, 5),
                "low": round(l, 5),
                "close": round(c, 5),
                "tick_volume": random.randint(1, 10),
            })
            price = c

        # persist last price
        self._simulation_prices[symbol] = price
        return candles

    def ensure_symbol_visible(self, symbol: str) -> bool:
        """Ensure `symbol` exists in Market Watch; attempt to add if missing (live mode)."""
        if self._mode == "live" and mt5 is not None:
            info = mt5.symbol_info(symbol)
            if info is None:
                try:
                    # attempt to add symbol to Market Watch
                    added = mt5.symbol_select(symbol, True)
                    if not added:
                        self.logger.error(f"Symbol {symbol} not available in MT5.", source="mt5")
                        return False
                    return True
                except Exception as exc:
                    self.logger.error(f"Error selecting symbol {symbol}: {exc}", source="mt5")
                    return False
            return True
        # simulation mode assumed available
        return True

    def get_account_info(self) -> dict[str, Any]:
        settings = self.config_manager.get_mt5_settings()
        if self._mode == "live" and mt5 is not None:
            account = mt5.account_info()
            if account is not None:
                data = account._asdict()
                data["source"] = "mt5"
                return data

        return {
            "login": settings.login,
            "balance": settings.demo_balance,
            "equity": settings.demo_balance,
            "margin": 0.0,
            "free_margin": settings.demo_balance,
            "profit": 0.0,
            "currency": settings.demo_currency,
            "leverage": settings.demo_leverage,
            "server": settings.server,
            "source": "simulation",
        }

    def get_open_trades(self) -> list[dict[str, Any]]:
        if self._mode == "live" and mt5 is not None:
            positions = mt5.positions_get()
            if positions is None:
                return []
            return [self._normalize_position(position._asdict()) for position in positions]
        return list(self._simulation_positions)

    def get_trade_history(self, days: int = 30) -> list[dict[str, Any]]:
        if self._mode == "live" and mt5 is not None:
            end_date = datetime.now(UTC)
            start_date = end_date - timedelta(days=days)
            history = mt5.history_deals_get(start_date, end_date)
            if history is None:
                return []
            return [self._normalize_deal(deal._asdict()) for deal in history]
        return list(self._simulation_history)

    def place_order(
        self,
        side: str,
        symbol: str,
        volume: float,
        sl_pips: int,
        tp_pips: int,
        comment: str,
        magic_number: int,
    ) -> dict[str, Any]:
        tick = self.get_symbol_tick(symbol)
        price = float(tick["ask"] if side == "buy" else tick["bid"])
        sl_price = self._calc_price_offset(price, sl_pips, side, inverse=True)
        tp_price = self._calc_price_offset(price, tp_pips, side, inverse=False)

        if self._mode == "live" and mt5 is not None:
            order_type = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": 20,
                "magic": magic_number,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            if result is None:
                message = f"MT5 order_send returned no result: {mt5.last_error()}"
                self.logger.error(message, source="mt5")
                return {"success": False, "message": message}
            # Convert result to dict if possible and log full content for debugging
            payload = result._asdict() if hasattr(result, "_asdict") else {"result": str(result)}
            retcode = payload.get("retcode")
            success = retcode == mt5.TRADE_RETCODE_DONE
            if success:
                message = "Order placed successfully."
            elif retcode == 10027:
                message = "Order rejected: Auto-trading is disabled in MetaTrader 5. Please enable the 'Algo Trading' button in your MT5 terminal."
            else:
                message = f"Order rejected (retcode={retcode}): {payload}"
            # Log full result for auditing/debugging
            if success:
                self.logger.info(message, source="mt5", metadata=payload)
            else:
                self.logger.error(message, source="mt5", metadata=payload)
            # Include retcode and raw payload in returned structure
            return {"success": success, "message": message, "retcode": retcode, "result": payload}

        ticket = self._simulation_ticket + 1
        self._simulation_ticket = ticket
        trade = {
            "ticket": ticket,
            "symbol": symbol,
            "side": side,
            "volume": volume,
            "price_open": price,
            "price_current": price,
            "profit": 0.0,
            "sl": sl_price,
            "tp": tp_price,
            "time_open": datetime.now(UTC),
            "time_close": None,
            "magic_number": magic_number,
            "comment": comment,
            "source": "simulation",
        }
        self._simulation_positions = [trade]
        self.logger.info("Simulated order placed", source="mt5", metadata=trade)
        return {"success": True, "message": "Simulated order placed.", "result": trade}

    def close_all_open_trades(self) -> dict[str, Any]:
        if self._mode == "live" and mt5 is not None:
            positions = mt5.positions_get()
            closed_count = 0
            errors: list[str] = []
            if positions:
                for position in positions:
                    tick = mt5.symbol_info_tick(position.symbol)
                    if tick is None:
                        errors.append(f"Missing tick data for {position.symbol}")
                        continue
                    order_type = mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
                    price = tick.bid if position.type == mt5.POSITION_TYPE_BUY else tick.ask
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "position": position.ticket,
                        "symbol": position.symbol,
                        "volume": position.volume,
                        "type": order_type,
                        "price": price,
                        "deviation": 20,
                        "magic": position.magic,
                        "comment": "Emergency close",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    result = mt5.order_send(request)
                    payload = result._asdict() if result is not None and hasattr(result, "_asdict") else {"result": str(result)}
                    if result is not None and payload.get("retcode") == mt5.TRADE_RETCODE_DONE:
                        closed_count += 1
                    else:
                        errors.append(f"Failed to close ticket {position.ticket}: {payload}")
            return {"success": not errors, "closed_count": closed_count, "errors": errors}

        closed_positions = list(self._simulation_positions)
        self._simulation_positions = []
        for trade in closed_positions:
            closed_trade = {**trade, "time_close": datetime.now(UTC), "profit": trade.get("profit", 0.0)}
            self._simulation_history.append(closed_trade)
        return {"success": True, "closed_count": len(closed_positions), "errors": []}

    def _normalize_position(self, data: dict[str, Any]) -> dict[str, Any]:
        side = "buy" if data.get("type") == 0 else "sell"
        return {
            "ticket": data.get("ticket"),
            "symbol": data.get("symbol"),
            "side": side,
            "volume": data.get("volume"),
            "price_open": data.get("price_open"),
            "price_current": data.get("price_current"),
            "profit": data.get("profit"),
            "sl": data.get("sl"),
            "tp": data.get("tp"),
            "time_open": datetime.fromtimestamp(data.get("time", datetime.now(UTC).timestamp()), tz=UTC) if data.get("time") else None,
            "time_close": None,
            "magic_number": data.get("magic"),
            "comment": data.get("comment"),
            "source": "mt5",
        }

    def _normalize_deal(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "ticket": data.get("ticket") or data.get("deal"),
            "symbol": data.get("symbol"),
            "side": "buy" if data.get("type") in (0, 2) else "sell",
            "volume": data.get("volume"),
            "price_open": data.get("price"),
            "price_current": data.get("price"),
            "profit": data.get("profit"),
            "sl": data.get("sl"),
            "tp": data.get("tp"),
            "time_open": datetime.fromtimestamp(data.get("time", datetime.now(UTC).timestamp()), tz=UTC) if data.get("time") else None,
            "time_close": datetime.fromtimestamp(data.get("time", datetime.now(UTC).timestamp()), tz=UTC) if data.get("time") else None,
            "magic_number": data.get("magic"),
            "comment": data.get("comment"),
            "source": "mt5",
        }

    def _calc_price_offset(self, price: float, pips: int, side: str, inverse: bool) -> float:
        pip_value = 0.0001
        offset = pips * pip_value
        if inverse:
            return round(price - offset if side == "buy" else price + offset, 5)
        return round(price + offset if side == "buy" else price - offset, 5)

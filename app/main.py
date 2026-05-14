from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import ConfigManager
from app.core.logger import BotLogger
from app.routes.bot import router as bot_router
from app.routes.logs import router as logs_router
from app.routes.settings import router as settings_router
from app.routes.trades import router as trades_router
from app.services.bot_engine import BotEngine
from app.services.mt5_service import MT5Service
from app.services.risk_management import RiskManagementService
from app.services.strategy import StrategyService


def create_app() -> FastAPI:
    config_manager = ConfigManager()
    logger = BotLogger(
        log_file=config_manager.get_log_settings().log_file,
        max_entries=config_manager.get_log_settings().max_in_memory_logs,
    )
    mt5_service = MT5Service(config_manager=config_manager, logger=logger)
    strategy_service = StrategyService(config_manager=config_manager, logger=logger, mt5_service=mt5_service)
    risk_service = RiskManagementService(config_manager=config_manager, logger=logger)
    bot_engine = BotEngine(
        mt5_service=mt5_service,
        strategy_service=strategy_service,
        risk_service=risk_service,
        logger=logger,
        config_manager=config_manager,
    )

    app = FastAPI(
        title=config_manager.get_api_settings().title,
        debug=config_manager.get_api_settings().debug,
        version="1.0.0",
    )

    app.state.config_manager = config_manager
    app.state.logger = logger
    app.state.mt5_service = mt5_service
    app.state.strategy_service = strategy_service
    app.state.risk_service = risk_service
    app.state.bot_engine = bot_engine

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config_manager.get_api_settings().cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(bot_router)
    app.include_router(trades_router)
    app.include_router(settings_router)
    app.include_router(logs_router)

    @app.get("/")
    def root() -> dict[str, str]:
        return {"message": "Forex Trading Bot API is running.", "status": "ok"}

    @app.on_event("startup")
    def on_startup() -> None:
        logger.info("Application startup complete.", source="app")

    @app.on_event("shutdown")
    def on_shutdown() -> None:
        bot_engine.stop()
        mt5_service.shutdown()
        logger.info("Application shutdown complete.", source="app")

    return app


app = create_app()

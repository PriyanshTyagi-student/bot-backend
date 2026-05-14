# Forex Trading Bot Backend

Production-structured FastAPI backend for a Forex trading bot with a background execution engine, strategy controls, trade endpoints, logs, and MetaTrader 5 integration.

## Features

- Start, stop, and emergency-stop the bot
- Fetch open trades and trade history
- Get and update strategy settings
- Fetch logs from memory and optional file storage
- Fetch account information from MetaTrader 5 or simulation mode
- CORS enabled for frontend integration
- JSON-backed configuration storage

## Run

1. Create and activate a Python environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the API server:

```bash
uvicorn app.main:app --reload
```

4. Open the docs:

- http://127.0.0.1:8000/docs

## Endpoints

- POST /bot/start
- POST /bot/stop
- POST /bot/emergency-stop
- GET /bot/status
- GET /trades
- GET /trades/history
- GET /strategy
- POST /strategy/update
- GET /logs
- GET /account

## Notes

- If MetaTrader 5 is unavailable, the backend falls back to simulation mode so the API remains usable.
- Settings are stored in `data/settings.json` on first run.
- Logs are kept in memory and can also be written to `logs/bot.log`.
"# bot-backend" 

# Session Context — AiTrading Options TradeUI
_Last updated: 2026-05-31_

## Project
- **Repo:** https://github.com/sireesh27/AiTrading-Options-TradeUI.git
- **Location:** `/Volumes/OWC Express 1M2/Work/Projects/TradeOptionsUI`
- **Stack:** Python FastAPI backend + React/Vite frontend

---

## How to Start Everything

```bash
# 1. IB Gateway (Live + Paper) — auto-login from .env
cd "/Volumes/OWC Express 1M2/Work/Projects/TradeOptionsUI"
./start_ibgateway.sh           # both live + paper
./start_ibgateway.sh status    # check ports

# 2. Backend (FastAPI)
venv/bin/python3.12 backend_server.py &
# → http://localhost:8000  (Swagger: http://localhost:8000/docs)

# 3. Frontend (Vite/React)
cd frontend && npm run dev &
# → http://localhost:5173
```

---

## Broker Connection Status

| Broker | Status | Details |
|---|---|---|
| **IBKR Live** | ✅ port 4001 | Account U22604784, via IB Gateway + IBC |
| **IBKR Paper** | ✅ port 4002 | via IB Gateway + IBC |
| **Alpaca Paper** | ✅ | Cash ~$95k, Portfolio ~$100k |
| **Alpaca Live** | ✅ | Cash $99, Portfolio $99 |
| **Tastytrade** | ⚠️ partial | Keys set; needs TASTY_USERNAME+TASTY_PASSWORD in .env (OAuthSession removed from lib) |

---

## Key Files & Fixes Applied

### Python Environment
- **Python 3.12** via Homebrew — system Python 3.9 was too old
- **venv** at `venv/` — activate with `venv/bin/python3.12`
- `ib-async` package now available (was missing earlier, now installs fine)

### Code Patches Made
1. **`main_tastytrade.py`** — removed `OAuthSession` import (no longer in tastytrade lib)
2. **`backend_server.py`** — wrapped `import ibkr_manager` in try/except for graceful fallback
3. **`ibkr_manager.py`** — added env-var based host/port config (reads `IBKR_HOST`, `IBKR_PORT`, `IBKR_CLIENT_ID`)

### IB Gateway Auto-Login Setup
- **IBC v3.23.0** installed at `ibc/`
- **Launch script:** `start_ibgateway.sh` (reads credentials from `.env`)
- **Config files:** `ibc/config.live.ini`, `ibc/config.paper.ini`
- **Jts config dirs:**
  - Live: `/Users/godev/JtsLive` (symlink → `/Volumes/OWC Express 1M2/JtsLive`)
  - Paper: `/Users/godev/JtsPaper` (symlink → `/Volumes/OWC Express 1M2/JtsPaper`)
  - Apps: `/Users/godev/IBKRApps` (symlink → `/Volumes/OWC Express 1M2/Applications`)
- **Why symlinks?** Home dir has spaces (`/Volumes/OWC Express 1M2`) which breaks ibcstart.sh's `find` command and Java `-DjtsConfigDir` arg parsing

### .env Keys Required
```
TASTY_CLIENT_SECRET=...
TASTY_REFRESH_TOKEN=...
TASTY_LIVE=True
ALPACA_PAPER_API_KEY=...
ALPACA_PAPER_API_SECRET=...
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
MASSIVE_API_KEY=...
IBKR_HOST=127.0.0.1
IBKR_PORT=4001
IBKR_CLIENT_ID=1
IBKR_USERNAME=siretrader1
IBKR_PASSWORD=...
```

---

## Known Issues / TODO
- **Tastytrade:** `OAuthSession` is gone from the lib. Need to add `TASTY_USERNAME` + `TASTY_PASSWORD` to `.env` for username/password auth to work
- **IBKR Paper port in .env:** `IBKR_PORT=4001` is live — if you want the backend to also connect to paper, add `IBKR_PAPER_PORT=4002` and update `ibkr_manager.py`
- **ibcstart.sh renames the .app** to `IB Gateway 10.45-1.app` on first run — if it gets stuck, restore with: `mv "/Volumes/OWC Express 1M2/Applications/IB Gateway 10.45/IB Gateway 10.45-1.app" "/Volumes/OWC Express 1M2/Applications/IB Gateway 10.45/IB Gateway 10.45.app"`
- **Frontend** not yet verified working end-to-end against backend

---

## Architecture
```
Frontend (React/Vite :5173)
    ↓
Backend (FastAPI :8000)
    ├── Tastytrade API (cloud)
    ├── Alpaca API (cloud)
    └── IB Gateway (:4001 live, :4002 paper)
            ↑
        IBC auto-login
        (credentials from .env)
```

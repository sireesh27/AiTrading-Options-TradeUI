# Tests

Validation suite for the trading dashboard backend + IBKR integration.

## Setup
```bash
pip install -r requirements-dev.txt
```

## Run
```bash
pytest                       # all unit + API + (auto-skipping) integration tests
pytest tests/test_ibkr_manager.py     # IBKRManager unit tests (no gateway needed)
pytest tests/test_api_endpoints.py    # FastAPI endpoints, broker layer mocked
pytest tests/test_integration_live.py # live end-to-end (skips if backend down)
pytest tests/gui                       # Playwright UI tests (needs playwright + browsers + running servers)
```

## What each suite covers

| File | Needs a live service? | Covers |
|------|----------------------|--------|
| `test_ibkr_manager.py` | No (IB mocked) | live/paper port+clientId separation, connection-status accuracy, `_collect_tickers` bounded streaming + early-exit, OCC parsing & correct `Option(currency=...)` construction, unknown-symbol guards |
| `test_api_endpoints.py` | No (managers mocked) | `/api/positions` structure + concurrency + accurate `isConnected`, stock-price unknown-symbol 404, option-chain shape & missing call/put handling, greeks-batch IBKR-first + Massive fallback, WebSocket quote/error frames |
| `test_integration_live.py` | Yes — auto-skips if not | latency budgets, real IBKR stock price / option chain / greeks, GOOGL regression, live WebSocket stream |
| `test_backend_api.py` | Uses TestClient | original smoke checks |
| `gui/` | Yes (Playwright) | browser UI flows |

Integration tests **skip** (never fail) when the backend on `:8000` is unreachable
or the IB Gateway is disconnected, so the default `pytest` run is safe in CI.

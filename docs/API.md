# TradeOptionsUI — Backend API Reference

REST + WebSocket API served by `backend_server.py` (FastAPI).

- **Base URL:** `http://localhost:8000`
- **WebSocket base:** `ws://localhost:8000`
- **Auth:** none (local app). CORS is open (`*`).
- **Content type:** JSON.
- **Interactive docs:** FastAPI auto-generates Swagger UI at `GET /docs` and ReDoc at `GET /redoc`.

Brokers/data sources referenced below:
- **IBKR** — Interactive Brokers via `ib_async`, through a running IB Gateway/TWS (live port 4001, paper 4002). Primary source for live quotes, option chains, greeks and trading.
- **Tastytrade** — via the `tastytrade` SDK / DXLink streamer.
- **Massive** — the Massive Options API (`massive_options`).

Common error shape (FastAPI):
```json
{ "detail": "human-readable message" }
```
Typical status codes: `400` invalid request / order rejected, `404` symbol or data not found, `503` broker/gateway unavailable, `500` unexpected error.

---

## Contents
- [Health](#health)
- [Accounts & Positions](#accounts--positions)
- [Portfolio Greeks](#portfolio-greeks)
- [Market Data — Stock Quotes](#market-data--stock-quotes)
- [Market Data — Live Stream (WebSocket)](#market-data--live-stream-websocket)
- [Option Chains](#option-chains)
- [Greeks](#greeks)
- [Symbol Search (Autocomplete)](#symbol-search-autocomplete)
- [Trading (Orders)](#trading-orders)
- [Comparison / Diagnostics](#comparison--diagnostics)

---

## Health

### `GET /`
Liveness check.

**Response**
```json
{ "message": "Trading Backend API is running", "version": "1.0" }
```

---

## Accounts & Positions

### `GET /api/positions`
Aggregated balances + positions across all brokers. Brokers are fetched **concurrently**; a failing broker degrades gracefully (`isConnected: false`).

**Response** — keys: `tastytrade`, `alpaca_live`, `alpaca_paper`, `ibkr_live`, `ibkr_paper`. Each:
```json
{
  "totalValue": 1574.0,
  "equity": 1574.0,
  "buyingPower": 1574.0,
  "dayPL": 0.0,
  "dayTrades": "N/A",
  "isConnected": true,
  "positions": [
    {
      "symbol": "AAPL",
      "qty": 11,
      "avgPrice": 180.2,
      "currentPrice": 307.78,
      "value": 3385.58,
      "pl": 1402.0,
      "plPercent": 70.8,
      "source": "IBKR Live"
    }
  ]
}
```
**Notes:** `isConnected` reflects the real socket state (no stale "green"). Option positions use the OCC `localSymbol`.

---

## Portfolio Greeks

### `GET /api/portfolio-greeks`
Portfolio-level greeks aggregated across all positions, grouped by underlying. (Greeks currently sourced from the Massive API.)

**Response**
```json
{
  "portfolio_totals": {
    "net_delta": 633.4, "net_gamma": 2.359, "net_theta": -24.73, "net_vega": 19.98,
    "total_positions": 8, "total_value": 28740.81, "num_underlyings": 7
  },
  "by_underlying": {
    "AAPL": {
      "underlying": "AAPL",
      "net_delta": 11.0, "net_gamma": 0.0, "net_theta": 0.0, "net_vega": 0.0,
      "total_value": 3385.58,
      "positions": [
        { "symbol": "AAPL", "type": "stock", "qty": 11, "delta": 1.0, "delta_exposure": 11.0,
          "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0, "iv": 0.0,
          "value": 3385.58, "broker": "IBKR Live", "pl": 1402.0, "avgPrice": 180.2,
          "currentPrice": 307.78, "plPercent": 70.8 }
      ]
    }
  }
}
```

---

## Market Data — Stock Quotes

All three return the same shape: `{ "symbol", "price", "bid", "ask" }` (IBKR/Tastytrade also include `"broker"`). Price priority for IBKR is **last → mid(bid,ask) → close**.

### `GET /api/ibkr/stock-price/{symbol}`
Live IBKR snapshot quote.
```bash
curl http://localhost:8000/api/ibkr/stock-price/AAPL
```
```json
{ "broker": "ibkr", "symbol": "AAPL", "price": 307.78, "bid": 307.70, "ask": 307.95 }
```
**Errors:** `404` unknown symbol (`"Unknown symbol 'XYZ'…"`); `503` if IBKR not connected.

### `GET /api/tastytrade/stock-price/{symbol}`
Real-time quote via Tastytrade DXLink. `401` if auth fails, `404` if no quote.

### `GET /api/stock-price/{symbol}`
Quote via the Massive API. `{ "symbol", "price", "bid", "ask" }`.

---

## Market Data — Live Stream (WebSocket)

### `WS /ws/ibkr/stock-price/{symbol}`
Streams live IBKR quotes — one JSON frame per tick until the client disconnects.

```js
const ws = new WebSocket("ws://localhost:8000/ws/ibkr/stock-price/AAPL");
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

**Tick frame**
```json
{ "broker": "ibkr", "symbol": "AAPL", "price": 307.78, "bid": 307.70,
  "ask": 307.95, "last": 307.78, "close": 306.31, "volume": 251986,
  "high": 0, "low": 0 }
```
**Error frame** (then the socket closes):
```json
{ "error": "Unknown symbol 'XYZ'. Check the ticker and try again." }
```
```json
{ "error": "IBKR not available. Ensure IB Gateway/TWS is running …" }
```

---

## Option Chains

All chain endpoints return the same envelope:
```json
{
  "broker": "ibkr",
  "underlying": "AAPL",
  "underlyingPrice": 307.78,
  "expirations": ["20260608", "20260610", "..."],
  "selectedExpiration": "20260608",
  "chain": {
    "20260608": {
      "calls": [ { /* OptionContract */ } ],
      "puts":  [ { /* OptionContract */ } ]
    }
  }
}
```
**OptionContract**
```json
{ "symbol": "AAPL  260608C00310000", "strike": 310.0, "expiration": "20260608",
  "type": "call", "bid": 2.14, "ask": 2.38, "last": 2.25, "volume": 11527,
  "openInterest": 0, "delta": 0.399, "gamma": 0.05, "theta": -0.11,
  "vega": 0.06, "rho": 0.0, "iv": 0.299 }
```

### `GET /api/ibkr/option-chain/{underlying}`
Live IBKR chain. Returns the **full list of expirations**; per-strike data is loaded for the **selected expiration only** (nearest by default).

**Query params**
| Param | Default | Description |
|-------|---------|-------------|
| `expiration` | nearest | `YYYYMMDD`; load this expiration's strikes |
| `strikes` | `20` | Number of strikes nearest ATM (clamped 2–100) |

```bash
curl "http://localhost:8000/api/ibkr/option-chain/AAPL?expiration=20260620&strikes=40"
```
**Notes**
- Greeks come from IBKR `modelGreeks`; the underlying must stream for them to compute.
- `openInterest` requires live market hours (IBKR doesn't send OI for frozen/weekend data).
- `404` if the chain/expiration can't be resolved; `503` if IBKR unavailable.

### `GET /api/tastytrade/option-chain/{underlying}`
Option chain via Tastytrade (multiple expirations populated in `chain`).

### `GET /api/option-chain/{underlying}`
Option chain via the Massive API. Optional `?expiration=YYYY-MM-DD`.

---

## Greeks

### `POST /api/greeks-batch`
Greeks for a list of option symbols. **IBKR-first** (model greeks), with **Massive as a per-symbol fallback** for anything IBKR can't price.

**Request**
```json
{ "symbols": ["AAPL  260608C00310000", "O:SPY251219C00450000"] }
```
**Response** — map of symbol → greeks (or `null` if unavailable / not an option):
```json
{
  "AAPL  260608C00310000": { "delta": 0.40, "gamma": 0.05, "theta": -0.11,
                              "vega": 0.06, "rho": 0.0, "iv": 0.30 },
  "O:SPY251219C00450000": null
}
```
Accepts OCC symbols with or without an `O:` prefix and with or without spaces.

### `GET /api/option-greeks/{underlying}/{option_symbol}`
Greeks + quote for a single option via the Massive API.
```bash
curl http://localhost:8000/api/option-greeks/SPY/O:SPY251219C00650000
```
```json
{ "underlying": "SPY", "option_symbol": "O:SPY251219C00650000",
  "greeks": { "delta": 0.5, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0, "iv": 0.0 },
  "quote": { "bid": 0.0, "ask": 0.0 } }
```

---

## Symbol Search (Autocomplete)

### `GET /api/ibkr/search/{query}`
Type-ahead symbol search via IBKR `reqMatchingSymbols`. Ranked: exact → prefix → USD → stock → alphabetical.

```bash
curl http://localhost:8000/api/ibkr/search/APP
```
```json
{
  "query": "APP",
  "results": [
    { "symbol": "APP", "name": "APPLOVIN CORP-CLASS A", "secType": "STK",
      "exchange": "NASDAQ", "currency": "USD", "hasOptions": true }
  ]
}
```

---

## Trading (Orders)

Order routing is selected per request via the `account` field: **`paper` (default)** or **`live`**. Paper → IB Gateway port 4002; live → 4001.

### `GET /api/ibkr/position/{symbol}`
Net quantity currently held (drives whether SELL is allowed and the max sellable).

**Query params:** `sec_type` (`stock` | `option`, default `stock`), `account` (`paper` | `live`, default `paper`).
```bash
curl "http://localhost:8000/api/ibkr/position/AAPL?sec_type=stock&account=paper"
```
```json
{ "account": "paper", "symbol": "AAPL", "secType": "stock", "quantity": 0.0 }
```

### `POST /api/ibkr/order`
Place a stock or option order.

**Request**
```json
{
  "account": "paper",
  "secType": "stock",
  "symbol": "AAPL",
  "action": "BUY",
  "quantity": 1,
  "orderType": "LMT",
  "limitPrice": 305.00,
  "stopPrice": null
}
```
| Field | Type | Notes |
|-------|------|-------|
| `account` | string | `paper` (default) or `live` |
| `secType` | string | `stock` or `option` (OCC symbol for options) |
| `symbol` | string | ticker, or OCC e.g. `AAPL  260608C00310000` |
| `action` | string | `BUY` or `SELL` |
| `quantity` | number | shares (stock) or contracts (option, ×100) |
| `orderType` | string | `MKT` · `LMT` · `STP` · `STP LMT` |
| `limitPrice` | number? | required for `LMT` / `STP LMT` |
| `stopPrice` | number? | required for `STP` / `STP LMT` |

**Response**
```json
{ "ok": true, "account": "paper", "orderId": 12, "symbol": "AAPL",
  "secType": "stock", "action": "BUY", "quantity": 1, "orderType": "LMT",
  "limitPrice": 305.0, "stopPrice": null, "status": "PreSubmitted",
  "filled": 0, "remaining": 1, "avgFillPrice": 0 }
```
**Errors (`400`):** missing limit/stop price, bad quantity/action, unresolvable symbol.

### `GET /api/ibkr/orders`
Open/working orders. **Query param:** `account` (default `paper`).
```json
{ "account": "paper", "orders": [
  { "orderId": 12, "symbol": "AAPL", "secType": "STK", "action": "BUY",
    "quantity": 1, "orderType": "LMT", "limitPrice": 305.0, "stopPrice": null,
    "status": "PreSubmitted", "filled": 0, "remaining": 1 }
] }
```

### `POST /api/ibkr/order/cancel`
Cancel an open order.
```json
{ "account": "paper", "orderId": 12 }
```
```json
{ "ok": true, "orderId": 12, "status": "Cancelled" }
```

---

## Comparison / Diagnostics

### `GET /api/compare/{symbol}`
Side-by-side comparison of stock price + option chain across Massive and Tastytrade (diagnostic).
```json
{ "symbol": "AAPL",
  "stock_comparison": { "massive": { "price": 307.78, "bid": 307.7, "ask": 307.9, "spread": 0.2 },
                         "tastytrade": null, "difference": null },
  "options_comparison": { "massive": { "expirations_count": 0, "first_expiration": null },
                          "tastytrade": null, "sample_strikes": [] },
  "errors": [] }
```

### `GET /api/tastytrade/test`
Tastytrade connectivity/auth diagnostic.

---

## Conventions & gotchas

- **OCC option symbols**: `ROOT + YYMMDD + C|P + strike×1000 (8 digits)`, e.g. `AAPL  260608C00310000` = AAPL, 2026-06-08, Call, strike 310.00. Endpoints accept them with/without `O:` and internal spaces.
- **Expirations** are `YYYYMMDD` strings.
- **Greeks/IV** are decimals (e.g. `iv: 0.30` = 30%). Values are model-derived and may differ slightly from other providers (different rate/dividend models).
- **Market hours**: outside RTH, IBKR serves *frozen* (last-close) data; bid/ask may be 0 and open interest is not delivered.
- **Performance**: `/api/positions` and `/api/portfolio-greeks` return in ~0.1s warm; option chains ~1.5–3s (cached) and use a bounded streaming window. Connection-failure paths fail fast (~4s) rather than hanging.

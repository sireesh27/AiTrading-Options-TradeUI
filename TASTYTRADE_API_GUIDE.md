# Tastytrade API & Streaming Guide

Complete guide for fetching and streaming live stock and options data from Tastytrade.

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Environment Variables](#2-environment-variables)
3. [REST API Endpoints](#3-rest-api-endpoints)
4. [DXLink Streaming](#4-dxlink-streaming)
5. [Data Types & Greeks](#5-data-types--greeks)
6. [Symbol Formats](#6-symbol-formats)
7. [Code Examples](#7-code-examples)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Authentication

### OAuth2 Authentication (Recommended)

Tastytrade uses OAuth2 for authentication. Username/password auth was deprecated December 1, 2025.

#### Step 1: Get Refresh Token

1. Log into [Tastytrade Developer Portal](https://developer.tastytrade.com/)
2. Create an application to get your `client_secret`
3. Complete OAuth flow to obtain `refresh_token`

#### Step 2: Authenticate in Code

```python
from tastytrade import OAuthSession

session = OAuthSession(
    client_secret="your_client_secret",
    refresh_token="your_refresh_token",
    is_test=False  # False for LIVE, True for certification/sandbox
)
```

### Authentication Flow

```
┌─────────────────┐
│  Client App     │
└────────┬────────┘
         │ 1. POST /oauth/token (refresh_token)
         ▼
┌─────────────────┐
│ api.tastyworks  │ ──► Returns access_token (expires in 900s)
│     .com        │
└────────┬────────┘
         │ 2. GET /api-quote-tokens
         ▼
┌─────────────────┐
│ Quote Token     │ ──► Used for DXLink WebSocket connection
└─────────────────┘
```

---

## 2. Environment Variables

Create a `.env` file in your project root:

```env
# Tastytrade OAuth2 Credentials (Required)
TASTY_CLIENT_SECRET=your_client_secret_here
TASTY_REFRESH_TOKEN=your_refresh_token_here

# Environment: "true" for LIVE, "false" for certification
TASTY_LIVE=true

# Legacy (Deprecated - DO NOT USE)
# TASTY_USERNAME=your_username
# TASTY_PASSWORD=your_password
```

### Account Information

| Field | Value |
|-------|-------|
| Account Number | 5WZ90597 |
| Account Type | Individual |
| Is Funded | Yes |
| Quote Type | REAL-TIME |

> **Note:** Funded accounts receive real-time quotes. Unfunded accounts receive 15-20 minute delayed quotes.

---

## 3. REST API Endpoints

### Base URLs

| Environment | Base URL |
|-------------|----------|
| Production (LIVE) | `https://api.tastyworks.com` |
| Certification (Sandbox) | `https://api.cert.tastyworks.com` |

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/oauth/token` | Exchange refresh token for access token |
| GET | `/api-quote-tokens` | Get quote token for DXLink streaming |

### Account Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/customers/me/accounts` | Get all accounts |
| GET | `/accounts/{account_id}/balances` | Get account balances |
| GET | `/accounts/{account_id}/positions` | Get account positions |

### Option Chain Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/option-chains/{symbol}/nested` | Get full nested option chain |
| GET | `/option-chains/{symbol}/compact` | Get compact option chain |

### Example: Get Option Chain

```python
from tastytrade.instruments import NestedOptionChain

chain = NestedOptionChain.get(session, "SPY")

# Access expirations
for exp in chain.expirations:
    print(f"Expiration: {exp.expiration_date}")

    for strike in exp.strikes:
        print(f"  Strike: ${strike.strike_price}")
        print(f"    Call: {strike.call}")  # OCC symbol
        print(f"    Put: {strike.put}")    # OCC symbol
```

---

## 4. DXLink Streaming

### Overview

DXLink is Tastytrade's real-time market data streaming service built on WebSockets.

### Connection Flow

```
1. Authenticate ──► Get Session Token
                          │
2. Get Quote Token ◄──────┘
         │
3. Connect WebSocket ──► wss://tasty-openapi-ws.dxfeed.com/realtime
         │
4. Subscribe to Symbols
         │
5. Receive Real-time Events (Quote, Trade, Greeks, Summary)
```

### WebSocket URL

```
wss://tasty-openapi-ws.dxfeed.com/realtime?token={quote_token}
```

### Event Types

| Event Type | Description | Fields |
|------------|-------------|--------|
| `Quote` | Bid/Ask quotes | eventSymbol, bidPrice, askPrice, bidSize, askSize |
| `Trade` | Last trade | eventSymbol, price, size, time |
| `Greeks` | Option greeks | eventSymbol, delta, gamma, theta, vega, rho, volatility |
| `Summary` | Daily summary | eventSymbol, openInterest, dayVolume, dayHigh, dayLow |

### Subscription Message Format

```json
{
  "type": "FEED_SUBSCRIPTION",
  "channel": 7,
  "add": [
    {"symbol": "SPY", "type": "Quote"},
    {"symbol": "AAPL", "type": "Quote"},
    {"symbol": ".SPY260112C694", "type": "Greeks"}
  ]
}
```

### Data Message Format

```json
{
  "type": "FEED_DATA",
  "channel": 7,
  "data": [
    "Quote",
    ["SPY", 0, 0, 0, 0, "Q", 0, "Q", 693.74, 695.08, "NaN", "NaN"]
  ]
}
```

---

## 5. Data Types & Greeks

### Quote Event Fields

| Field | Type | Description |
|-------|------|-------------|
| `event_symbol` | string | Symbol identifier |
| `bid_price` | Decimal | Current bid price |
| `ask_price` | Decimal | Current ask price |
| `bid_size` | int | Bid size in lots |
| `ask_size` | int | Ask size in lots |
| `bid_exchange_code` | string | Exchange code for bid |
| `ask_exchange_code` | string | Exchange code for ask |

### Greeks Event Fields

| Field | Type | Description |
|-------|------|-------------|
| `event_symbol` | string | Option symbol |
| `delta` | Decimal | Delta (-1 to 1) |
| `gamma` | Decimal | Gamma |
| `theta` | Decimal | Theta (daily decay) |
| `vega` | Decimal | Vega (IV sensitivity) |
| `rho` | Decimal | Rho (interest rate sensitivity) |
| `volatility` | Decimal | **Implied Volatility (IV)** |
| `price` | Decimal | Theoretical price |

> **Important:** The IV field is named `volatility`, not `impliedVolatility`.

### Summary Event Fields

| Field | Type | Description |
|-------|------|-------------|
| `event_symbol` | string | Symbol identifier |
| `open_interest` | int | Open interest |
| `day_volume` | int | Daily volume |
| `day_high` | Decimal | Daily high |
| `day_low` | Decimal | Daily low |

---

## 6. Symbol Formats

### Stock Symbols

Stocks use standard ticker symbols:
- `SPY`, `AAPL`, `TSLA`, `NVDA`, `QQQ`

### Option Symbol Formats

#### OCC Format (API Response)

Standard OCC option symbol format:
```
SPY260112C00694000
│   │     │ │
│   │     │ └── Strike price (694.00 * 1000)
│   │     └──── Option type (C=Call, P=Put)
│   └────────── Expiration (YYMMDD)
└────────────── Root symbol
```

#### DXLink Streamer Format

Streaming uses a different format:
```
.SPY260112C694
│ │  │     │ │
│ │  │     │ └── Strike price (integer or decimal)
│ │  │     └──── Option type (C=Call, P=Put)
│ │  └────────── Expiration (YYMMDD)
│ └───────────── Root symbol
└─────────────── Leading dot (required)
```

### Symbol Conversion

```python
def occ_to_streamer(occ_symbol):
    """Convert OCC symbol to DXLink streamer format."""
    # Example: SPY260112C00694000 -> .SPY260112C694

    root = occ_symbol[:6].rstrip()  # SPY
    date = occ_symbol[6:12]          # 260112
    opt_type = occ_symbol[12]        # C or P
    strike_raw = occ_symbol[13:21]   # 00694000

    # Convert strike: 00694000 -> 694
    strike = int(strike_raw) / 1000
    if strike == int(strike):
        strike_fmt = str(int(strike))
    else:
        strike_fmt = f"{strike:.2f}".replace(".", "")

    return f".{root}{date}{opt_type}{strike_fmt}"
```

---

## 7. Code Examples

### Example 1: Authenticate and Get Account Info

```python
import os
from dotenv import load_dotenv
from tastytrade import OAuthSession, Account

load_dotenv()

# Authenticate
session = OAuthSession(
    client_secret=os.getenv("TASTY_CLIENT_SECRET"),
    refresh_token=os.getenv("TASTY_REFRESH_TOKEN"),
    is_test=False
)

# Get accounts
accounts = Account.get_accounts(session)
for acc in accounts:
    print(f"Account: {acc.account_number}")
    print(f"Type: {acc.account_type_name}")

    # Get balances
    balances = acc.get_balances(session)
    print(f"Net Liq: ${balances.net_liquidating_value}")
    print(f"Cash: ${balances.cash_balance}")
```

### Example 2: Get Option Chain

```python
from tastytrade.instruments import NestedOptionChain

# Get full option chain
chain = NestedOptionChain.get(session, "SPY")
if isinstance(chain, list):
    chain = chain[0]

print(f"Expirations: {len(chain.expirations)}")

# Get first expiration
first_exp = chain.expirations[0]
print(f"First Expiration: {first_exp.expiration_date}")
print(f"Strikes: {len(first_exp.strikes)}")

# Get ATM strikes
for strike in first_exp.strikes:
    if 690 <= float(strike.strike_price) <= 700:
        print(f"Strike ${strike.strike_price}:")
        print(f"  Call: {strike.call}")
        print(f"  Put: {strike.put}")
```

### Example 3: Stream Real-Time Quotes

```python
import asyncio
from tastytrade import DXLinkStreamer
from tastytrade.dxfeed import Quote

async def stream_quotes(session):
    symbols = ["SPY", "AAPL", "TSLA"]

    async with DXLinkStreamer(session) as streamer:
        # Subscribe to quotes
        await streamer.subscribe(Quote, symbols)

        # Listen for events
        while True:
            event = await streamer.get_event(Quote)
            if event:
                print(f"{event.event_symbol}: "
                      f"Bid=${event.bid_price} "
                      f"Ask=${event.ask_price}")

# Run
asyncio.run(stream_quotes(session))
```

### Example 4: Stream Option Greeks

```python
import asyncio
from tastytrade import DXLinkStreamer
from tastytrade.dxfeed import Greeks

async def stream_greeks(session):
    # Option symbols in DXLink format
    option_symbols = [
        ".SPY260112C694",
        ".SPY260112P694",
        ".SPY260112C695",
        ".SPY260112P695"
    ]

    async with DXLinkStreamer(session) as streamer:
        # Subscribe to Greeks
        await streamer.subscribe(Greeks, option_symbols)

        # Listen for events
        while True:
            event = await streamer.get_event(Greeks)
            if event:
                print(f"{event.event_symbol}:")
                print(f"  Delta: {event.delta:.4f}")
                print(f"  Gamma: {event.gamma:.4f}")
                print(f"  Theta: {event.theta:.4f}")
                print(f"  Vega: {event.vega:.4f}")
                print(f"  IV: {float(event.volatility)*100:.2f}%")

# Run
asyncio.run(stream_greeks(session))
```

### Example 5: Full Streaming with Multiple Event Types

```python
import asyncio
from tastytrade import DXLinkStreamer
from tastytrade.dxfeed import Quote, Greeks, Summary

async def stream_all(session, stock_symbols, option_symbols):
    async with DXLinkStreamer(session) as streamer:
        # Subscribe to multiple event types
        await streamer.subscribe(Quote, stock_symbols)
        await streamer.subscribe(Quote, option_symbols)
        await streamer.subscribe(Greeks, option_symbols)
        await streamer.subscribe(Summary, option_symbols)

        # Poll for events
        while True:
            # Check Quote events
            try:
                event = await asyncio.wait_for(
                    streamer.get_event(Quote), timeout=0.1
                )
                if event:
                    print(f"QUOTE {event.event_symbol}: "
                          f"${event.bid_price} / ${event.ask_price}")
            except asyncio.TimeoutError:
                pass

            # Check Greeks events
            try:
                event = await asyncio.wait_for(
                    streamer.get_event(Greeks), timeout=0.1
                )
                if event:
                    iv = float(event.volatility) * 100
                    print(f"GREEKS {event.event_symbol}: "
                          f"D={event.delta:.3f} IV={iv:.1f}%")
            except asyncio.TimeoutError:
                pass

# Run
asyncio.run(stream_all(
    session,
    ["SPY", "AAPL"],
    [".SPY260112C694", ".SPY260112P694"]
))
```

---

## 8. Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `401 Unauthorized` | Expired token | Refresh OAuth token |
| `IV showing 0%` | Wrong field name | Use `event.volatility`, not `impliedVolatility` |
| `Symbol not found` | Wrong format | Use OCC format for API, DXLink format for streaming |
| `No data received` | Not subscribed | Call `streamer.subscribe()` first |
| `Delayed quotes` | Unfunded account | Fund account for real-time data |

### Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### API Rate Limits

- REST API: 120 requests/minute
- WebSocket: No explicit limit, but respect keepalive (60s)

### Keepalive

DXLink requires keepalive messages every 60 seconds:

```json
{"type": "KEEPALIVE", "channel": 0}
```

The `DXLinkStreamer` class handles this automatically.

---

## Quick Reference

### Authentication
```python
from tastytrade import OAuthSession
session = OAuthSession(client_secret, refresh_token, is_test=False)
```

### Get Quote Token
```python
# Handled automatically by DXLinkStreamer
# Manual: GET /api-quote-tokens
```

### Stream Quotes
```python
from tastytrade import DXLinkStreamer
from tastytrade.dxfeed import Quote, Greeks

async with DXLinkStreamer(session) as streamer:
    await streamer.subscribe(Quote, ["SPY", "AAPL"])
    await streamer.subscribe(Greeks, [".SPY260112C694"])

    event = await streamer.get_event(Quote)
```

### Key Fields
- **Quote:** `bid_price`, `ask_price`, `bid_size`, `ask_size`
- **Greeks:** `delta`, `gamma`, `theta`, `vega`, `volatility` (IV)
- **Summary:** `open_interest`, `day_volume`

---

*Last Updated: 2026-01-10*

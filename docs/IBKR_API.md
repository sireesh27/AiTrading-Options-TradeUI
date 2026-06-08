# IBKR API Reference (via `ib_async`)

What Interactive Brokers exposes to this project through the **`ib_async`** library
(v2.1.0) talking to a running **IB Gateway / TWS** (live port `4001`, paper `4002`).

This is the *upstream* capability map — what IBKR offers and which calls we already
use vs. what's available to build on. For our own HTTP/WebSocket endpoints see
[API.md](API.md).

- **Access object:** `IB()` (in `ibkr_manager.py` it's `self.ib`).
- **Async first:** most calls have a sync and an `…Async` variant; we use the
  `Async` ones inside FastAPI. 133 public methods total.
- **Connect:** `await ib.connectAsync(host, port, clientId=..., timeout=4)`.
  One session per `clientId`; live and paper must use different clientIds.
- **Market data type:** `ib.reqMarketDataType(2)` → live during RTH, frozen (last
  close) when the market is closed. Other modes: `1` live, `3` delayed, `4`
  delayed-frozen.

Legend: ✅ used in this project · ➕ available, not yet used.

---

## 1. Connection & session
| Method | Notes |
|--------|-------|
| `connectAsync(host, port, clientId, timeout)` ✅ | Open a session. |
| `isConnected()` ✅ | Real socket state (we expose this as `isConnected`). |
| `disconnect()` ✅ | Close the session. |
| `reqCurrentTimeAsync()` ➕ | Server time. |
| `reqUserInfoAsync()` ➕ | White-branding / user info. |
| `managedAccounts()` ➕ | List of account IDs on the login. |

---

## 2. Account & P&L
| Method | Notes |
|--------|-------|
| `accountSummaryAsync()` ✅ | NetLiquidation, BuyingPower, etc. (we map these in `get_portfolio_data`). |
| `portfolio()` ✅ | Current portfolio items (positions w/ market price & unrealized PnL). |
| `accountValues()` ➕ | Full raw account value rows. |
| `reqPnL()` / `pnl()` ➕ | Real-time account P&L subscription. |
| `reqPnLSingle()` / `pnlSingle()` ➕ | Real-time per-position P&L. |
| `reqAccountUpdatesAsync()` ➕ | Streaming account/portfolio updates. |
| `reqAccountSummaryAsync()` ➕ | Streaming summary subscription. |

---

## 3. Contracts & reference data
| Method | Notes |
|--------|-------|
| `qualifyContractsAsync(*contracts)` ✅ | Resolve `conId` (returns `None` for unqualifiable slots). |
| `reqMatchingSymbolsAsync(pattern)` ✅ | **Symbol search / autocomplete.** |
| `reqSecDefOptParamsAsync(symbol, '', secType, conId)` ✅ | Option chain params (expirations + strikes). |
| `reqContractDetailsAsync(contract)` ➕ | Full contract details (tick size, trading hours, multiplier, long name, etc.). |
| `reqMarketRuleAsync(ruleId)` ➕ | Price increment rules. |

Contract types used: `Stock(symbol,'SMART','USD')` ✅, `Option(root, 'YYYYMMDD', strike, 'C'/'P', 'SMART', currency='USD')` ✅. Also available ➕: `Future`, `Forex`, `Index`, `CFD`, `Crypto`, `Bond`, `FuturesOption`, `Bag` (combos/spreads).

---

## 4. Market data — quotes & greeks
| Method | Notes |
|--------|-------|
| `reqMktData(contract, genericTicks, snapshot, regSnapshot)` ✅ | Streaming ticks; `Ticker` updates in place. We pass generic ticks `100,101,106` (option volume, open interest, implied vol). |
| `cancelMktData(contract)` ✅ | Unsubscribe. |
| `reqTickersAsync(*contracts)` ✅(historically) | One-shot snapshot for many contracts (we replaced with a bounded streaming loop). |
| `reqMktDepth(contract)` ➕ | Level-II order book (DOM). |
| `reqTickByTickData(contract, type)` ➕ | Tick-by-tick (Last, BidAsk, MidPoint). |
| `reqRealTimeBars(contract, 5, ...)` ➕ | 5-second real-time bars. |
| `reqMarketDataType(n)` ✅ | live / frozen / delayed mode. |

**`Ticker` fields we read** ✅: `bid`, `ask`, `last`, `close`, `high`, `low`, `volume`,
`modelGreeks` (`delta`, `gamma`, `theta`, `vega`, `impliedVol`), `callOpenInterest` /
`putOpenInterest`. Available ➕: `bidSize`/`askSize`, `markPrice`, `histVolatility`,
`bidGreeks`/`askGreeks`/`lastGreeks`, `dividends`.

> **Greeks note:** IBKR computes `modelGreeks` only while the underlying is also
> streaming (we subscribe to the underlying during greeks/chain fetches). Open
> interest is not delivered for frozen/weekend data.

---

## 5. Options analytics
| Method | Notes |
|--------|-------|
| `calculateImpliedVolatilityAsync(contract, optionPrice, underPrice)` ➕ | IV for a given option price. |
| `calculateOptionPriceAsync(contract, volatility, underPrice)` ➕ | Theoretical price for a given IV. |
| `exerciseOptions(contract, action, qty, account, override)` ➕ | Exercise / lapse options. |

---

## 6. Historical data
| Method | Notes |
|--------|-------|
| `reqHistoricalDataAsync(contract, end, duration, barSize, whatToShow, useRTH)` ➕ | OHLCV bars (charts/backtests). |
| `reqHistoricalTicksAsync(...)` ➕ | Historical tick data. |
| `reqHeadTimeStampAsync(contract, ...)` ➕ | Earliest available data point. |
| `reqHistogramDataAsync(contract, ...)` ➕ | Price histogram. |
| `reqHistoricalScheduleAsync(...)` ➕ | Trading schedule. |

> Not yet used — a natural next feature for price charts on the ticker detail view.

---

## 7. Orders & trading
| Method | Notes |
|--------|-------|
| `placeOrder(contract, order)` ✅ | Submit; returns a live `Trade` object. |
| `cancelOrder(order)` ✅ | Cancel one order. |
| `reqOpenOrdersAsync()` / `openTrades()` ✅ | Working orders. |
| `reqGlobalCancel()` ➕ | Cancel **all** open orders at once. |
| `whatIfOrderAsync(contract, order)` ➕ | Margin/commission preview without sending — great for the trade ticket. |
| `reqCompletedOrdersAsync()` ➕ | Today's completed orders. |
| `bracketOrder(...)` ➕ | Parent + take-profit + stop-loss in one call. |
| `oneCancelsAll(orders, ...)` ➕ | OCA group. |

**Order types** (via `ib_async`): `MarketOrder` ✅, `LimitOrder` ✅, `Order(orderType='STP', auxPrice=…)` ✅, `Order(orderType='STP LMT', lmtPrice, auxPrice)` ✅. Also ➕: `StopLimitOrder`, trailing stops (`TRAIL`, `TRAIL LIMIT`), `MidPrice`, `MOC`/`LOC`, `tif` (DAY/GTC/IOC/OPG), `outsideRth`, `account` selection.

---

## 8. Positions & executions
| Method | Notes |
|--------|-------|
| `reqPositionsAsync()` / `positions()` ✅ | Net positions across accounts (we use for SELL gating). |
| `reqExecutionsAsync()` / `executions()` ➕ | Trade executions. |
| `fills()` ➕ | Fills with commission reports. |
| `trades()` / `openTrades()` ✅ | All / open `Trade` objects this session. |

---

## 9. News
| Method | Notes |
|--------|-------|
| `reqNewsProvidersAsync()` ➕ | Subscribed news providers. |
| `reqHistoricalNewsAsync(conId, providerCodes, ...)` ➕ | Headlines for a contract. |
| `reqNewsArticleAsync(providerCode, articleId)` ➕ | Full article body. |
| `reqNewsBulletins(allMsgs)` ➕ | Exchange bulletins. |

> The positions table already has a "News" column placeholder — these power it.

---

## 10. Market scanner
| Method | Notes |
|--------|-------|
| `reqScannerParametersAsync()` ➕ | Available scan codes/filters (XML). |
| `reqScannerDataAsync(subscription)` ➕ | Run a scan (top gainers, most active, high IV, etc.). |
| `reqScannerSubscription(...)` / `cancelScannerSubscription(...)` ➕ | Streaming scanner. |

---

## 11. Fundamental & event data
| Method | Notes |
|--------|-------|
| `reqFundamentalDataAsync(contract, reportType)` ➕ | Company fundamentals (financials, ratios, estimates). |
| `getWshMetaDataAsync()` / `getWshEventDataAsync(...)` ➕ | Wall Street Horizon corporate events (earnings dates, dividends, splits). |

---

## Quick examples (`ib_async`)

```python
from ib_async import IB, Stock, Option, LimitOrder

ib = IB()
await ib.connectAsync("127.0.0.1", 4002, clientId=2, timeout=4)  # paper
ib.reqMarketDataType(2)

# Symbol search
matches = await ib.reqMatchingSymbolsAsync("APP")

# Option chain params
stk = Stock("AAPL", "SMART", "USD"); await ib.qualifyContractsAsync(stk)
chains = await ib.reqSecDefOptParamsAsync(stk.symbol, "", stk.secType, stk.conId)

# Streaming quote + greeks (OI via generic tick 101)
opt = Option("AAPL", "20260620", 310, "C", "SMART", currency="USD")
await ib.qualifyContractsAsync(opt)
t = ib.reqMktData(opt, "100,101,106", False, False)
await ib.sleep(2)
print(t.modelGreeks.delta, t.callOpenInterest)
ib.cancelMktData(opt)

# Margin preview, then place
order = LimitOrder("BUY", 1, 305.00)
preview = await ib.whatIfOrderAsync(stk, order)   # commission/margin, no send
trade = ib.placeOrder(stk, order)                  # actually submit
```

---

## Reference
- ib_async docs: https://ib-api-reloaded.github.io/ib_async/
- IBKR TWS API guide: https://interactivebrokers.github.io/tws-api/
- Generic tick types: https://interactivebrokers.github.io/tws-api/tick_types.html
- Requires market-data subscriptions on the logged-in IBKR username for live
  quotes/greeks; option open interest needs market hours.

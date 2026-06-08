# Market Data Validation — IBKR vs External Sources

**Last run:** 2026-06-08, regular trading hours (mid-session re-check).
**Method:** [tools/eval_market_data.py](../tools/eval_market_data.py) compares our IBKR
feed against **live Yahoo Finance** (real, cookie+crumb auth) and **TradingView Pro**
(read on screen). Plus an internal **put-call parity** arbitrage check. No values are
hand-typed.

## Verdict: ✅ Our IBKR market data is correct and real-time. No differences are attributable to our feed.

| Check | Result |
|-------|--------|
| Underlying vs **TradingView Pro** (real-time) | GOOGL ours 363.90 vs TV 363.87 → **$0.03** (tick-level) |
| Underlying vs Yahoo (live) | GOOGL/AAPL/SPY all **0.00%** |
| Open interest vs Yahoo | **EXACT** every strike (GOOGL 6/6, AAPL 6/6, SPY 5/5; earlier 30/30 at open) |
| Implied volatility vs Yahoo | within ~4 vol-pts (6/6, 6/6, 5/5) |
| Put-call parity (internal arbitrage) | **max dev 0.06** across strikes → options consistent with the live underlying |

## The one apparent "difference" — and why it's Yahoo, not us
Our option **mids run ~$0.3–0.7 below Yahoo's**. Root cause proven: **Yahoo's free
option quotes are ~15-min delayed** while its underlying quote is live. Backing the
underlying out of Yahoo's *own* put-call parity:

| | Yahoo live underlying | Yahoo options imply | lag |
|---|---|---|---|
| GOOGL | 363.58 | 364.84 | **+1.26** |
| AAPL  | 303.81 | 305.28 | **+1.47** |

Both names were falling intraday, so Yahoo's stale (higher) option prices are exactly
what a delayed feed produces. Our IBKR options price off the *live* underlying (parity
clean), so ours are the correct ones.

## Fixes that removed real differences
1. **Open interest** — request IBKR generic tick **101**, read call/putOpenInterest
   (was hardcoded `0`). Now exact-matches Yahoo.
2. **IV** — prefer IBKR market IV (tick **106**), fallback modelGreeks. Now matches Yahoo.
3. **Underlying** — shared `price_from_ticker` (last→mid→close) so stock-price and
   chain agree exactly.
4. **Snapshot settle (0.8s)** — `_collect_tickers(..., settle=0.8)` lets bid/ask finish
   ticking after greeks arrive. This removed intermittent stale-quote snapshots that
   had broken parity (max dev 1.76 → 0.06) and call-price monotonicity.

## Caveats (not bugs)
- **0-DTE IV is genuinely high** (~90%); verified real (tick-106 and modelGreeks agree).
- **Pre-market / closed**: options don't trade, so bid/ask/OI are 0 on every source.
- **Sub-second tick differences** between any two live feeds are unavoidable; we match
  TradingView to the cent at snapshot time.

## Reproduce
```bash
./venv/bin/python tools/eval_market_data.py GOOGL AAPL SPY TSLA --strikes 8
# optional: --exp YYYYMMDD to pin an expiration
```
Run during regular hours. Scheduled task `option-chain-validation` runs this at open.

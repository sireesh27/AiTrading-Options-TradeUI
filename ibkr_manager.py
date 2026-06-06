import asyncio
import logging
import os
from ib_async import *
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class IBKRManager:
    def __init__(self, account_type='live'):
        """Initialize IBKR Manager.

        Supports two connection modes (auto-detected via env vars):
          1. Docker / IB Gateway (recommended for always-on use):
             Set IBKR_HOST in .env (e.g. 127.0.0.1 when running Docker locally).
             Live port 4001, Paper port 4002.
          2. Local TWS (fallback):
             No IBKR_HOST set — connects to local TWS.
             Live port 7496, Paper port 7497.
        """
        self.ib = IB()
        self.connected = False
        self.account_type = account_type
        # Cache of qualified option contracts keyed by (symbol, expiration).
        # Contract definitions don't change intraday, so caching lets repeat
        # chain loads skip the slow per-contract qualification round-trips.
        self._option_contract_cache = {}

        is_live = account_type == 'live'

        # If IBKR_HOST is set, assume Docker/IB Gateway mode
        ibkr_host = os.getenv('IBKR_HOST', '').strip()
        if ibkr_host:
            self.host = ibkr_host
            gateway_default_port = '4001' if is_live else '4002'
        else:
            # Local TWS fallback
            self.host = '127.0.0.1'
            gateway_default_port = '7496' if is_live else '7497'

        # IMPORTANT: the generic IBKR_PORT / IBKR_CLIENT_ID env vars apply to the
        # LIVE account only. Applying them to both accounts makes paper collide
        # with live (same port + clientId), which causes a 10s "clientId already
        # in use" connect timeout on every request. Paper uses its own defaults
        # unless an explicit IBKR_PORT_PAPER / IBKR_CLIENT_ID_PAPER is provided.
        if is_live:
            self.port = int(os.getenv('IBKR_PORT_LIVE', os.getenv('IBKR_PORT', gateway_default_port)))
            self.client_id = int(os.getenv('IBKR_CLIENT_ID_LIVE', os.getenv('IBKR_CLIENT_ID', '1')))
        else:
            self.port = int(os.getenv('IBKR_PORT_PAPER', gateway_default_port))
            self.client_id = int(os.getenv('IBKR_CLIENT_ID_PAPER', '2'))

        logger.info(f"IBKR Manager initialized for {account_type.upper()} account ({self.host}:{self.port})")

    def is_connected(self):
        """Authoritative live-connection check.

        The underlying ib.isConnected() reflects the real socket state, unlike
        the cached self.connected flag which can go stale if the gateway dies.
        """
        connected = self.ib.isConnected()
        self.connected = connected
        return connected

    async def connect(self):
        if self.ib.isConnected():
            self.connected = True
            return True

        try:
            logger.info(f"Attempting to connect to IBKR {self.account_type.upper()} on port {self.port}...")
            # Short timeout: if a broker is unreachable/wedged we want to fail
            # fast (and let the other brokers' concurrent fetches return) rather
            # than blocking every request for the full default 10s.
            await self.ib.connectAsync(self.host, self.port, clientId=self.client_id, timeout=4)
            logger.info(f"Connected to IBKR {self.account_type.upper()} on port {self.port}!")
            self.connected = True

            # Market data type 2 = "frozen": returns the last recorded values at
            # market close when the market is closed, and behaves like realtime
            # while it's open. Without this, after-hours requests get no ticks and
            # option modelGreeks never compute.
            try:
                self.ib.reqMarketDataType(2)
            except Exception as e:
                logger.debug(f"reqMarketDataType failed: {e}")

            # Wait a moment for connection to stabilize and data to sync
            await asyncio.sleep(1)
            return True
        except Exception as e:
            logger.warning(f"Could not connect to IBKR {self.account_type.upper()} on port {self.port}: {e}")
            # Reset the cached flag so stale state from a prior connection
            # doesn't leak through as a false "connected" status.
            self.connected = False
            return False

    async def get_portfolio_data(self):
        if not await self.connect():
            logger.error("Failed to connect to IBKR")
            return {
                "totalValue": 0.0,
                "equity": 0.0,
                "buyingPower": 0.0,
                "dayPL": 0.0,
                "dayTrades": "N/A",
                "positions": [],
                "isConnected": False
            }

        try:
            # Request portfolio updates
            # ib.portfolio() returns the current state of the portfolio
            portfolio_items = self.ib.portfolio()

            positions = []
            for item in portfolio_items:
                contract = item.contract

                # Calculate PL Percent if possible
                avg_cost = item.averageCost
                market_price = item.marketPrice
                qty = item.position
                pl_percent = 0.0
                if avg_cost > 0:
                    pl_percent = ((market_price - avg_cost) / avg_cost) * 100

                # Use localSymbol for options to get the specific contract (OCC format)
                # If localSymbol is empty, fall back to symbol
                display_symbol = contract.localSymbol if contract.localSymbol else contract.symbol

                positions.append({
                    "symbol": display_symbol,
                    "qty": qty,
                    "avgPrice": avg_cost,
                    "currentPrice": market_price,
                    "value": qty * market_price,
                    "pl": item.unrealizedPNL,
                    "plPercent": pl_percent,
                    "source": "IBKR"
                })

            # Request account summary
            # Use async version to avoid blocking
            account_summary = await self.ib.accountSummaryAsync()

            summary_data = {
                "totalValue": 0.0,
                "equity": 0.0,
                "buyingPower": 0.0,
                "dayPL": 0.0,
                "dayTrades": "N/A", # IBKR doesn't provide day trades count easily in summary
                "positions": positions
            }

            desired_tags = {
                'NetLiquidation': 'totalValue',
                'BuyingPower': 'buyingPower',
                'AvailableFunds': 'buyingPower', # Fallback or alternative
                'UnrealizedPnL': 'unrealizedPL',
                'RealizedPnL': 'realizedPL',
                'DailyPnL': 'dayPL'
            }

            for item in account_summary:
                if item.tag in desired_tags:
                    # Prefer BuyingPower over AvailableFunds if both exist, or handle logic
                    # For now just map
                    if item.tag == 'NetLiquidation':
                        summary_data['totalValue'] = float(item.value)
                        summary_data['equity'] = float(item.value)  # Equity is same as Net Liquidation Value
                    elif item.tag == 'BuyingPower':
                        summary_data['buyingPower'] = float(item.value)
                    elif item.tag == 'DailyPnL':
                        summary_data['dayPL'] = float(item.value)
                    elif item.tag == 'UnrealizedPnL' and summary_data['dayPL'] == 0.0:
                        # Use UnrealizedPnL as fallback if DailyPnL not available
                        summary_data['dayPL'] = float(item.value)

            return summary_data

        except Exception as e:
            logger.error(f"Error fetching IBKR data: {e}")
            self.disconnect()
            return {
                "totalValue": 0.0,
                "equity": 0.0,
                "buyingPower": 0.0,
                "dayPL": 0.0,
                "dayTrades": "N/A",
                "positions": [],
                "isConnected": False
            }

    async def _collect_tickers(self, contracts, max_wait=4.0, want_greeks=True):
        """Collect market data for many contracts with a bounded time budget.

        reqTickersAsync issues *snapshot* requests and waits for every one to
        complete; illiquid option strikes that never return data each block for
        IBKR's full ~11s snapshot timeout, so a 40-leg chain can take 14s+.

        Instead we open streaming subscriptions and poll the ticker objects
        (which update in place) for at most `max_wait` seconds, returning early
        once all tickers have usable data. Worst case is bounded to max_wait.
        """
        tickers = [self.ib.reqMktData(c, '', False, False) for c in contracts]

        def has_data(t):
            def ok(v):
                return v is not None and v == v and v > 0  # not None, not NaN, >0
            # When greeks are required, a price alone does NOT count as "done" —
            # otherwise the loop exits as soon as a (fast) close price arrives,
            # before IBKR has computed modelGreeks.
            if want_greeks:
                return t.modelGreeks is not None
            return ok(t.bid) or ok(t.ask) or ok(t.last) or ok(t.close)

        loop = asyncio.get_event_loop()
        start = loop.time()
        while loop.time() - start < max_wait:
            await asyncio.sleep(0.2)
            if all(has_data(t) for t in tickers):
                break

        for c in contracts:
            try:
                self.ib.cancelMktData(c)
            except Exception:
                pass
        return tickers

    async def get_greeks_for_symbols(self, symbols):
        """Fetch model Greeks from IBKR for a list of OCC option symbols.

        Accepts symbols in OCC form, with or without an "O:" prefix and with or
        without internal spaces (IBKR localSymbols look like 'AAPL  260605C00310000').
        Returns {original_symbol: {delta,gamma,theta,vega,rho,iv}} for the
        contracts IBKR could price; symbols it can't resolve are simply omitted
        so the caller can fall back to another source.
        """
        if not await self.connect():
            return {}

        import re
        occ = re.compile(r'^([A-Z]+)\s*([0-9]{6})([CP])([0-9]{8})$')

        pairs = []  # (original_symbol, Option contract)
        roots = set()
        for sym in symbols:
            clean = sym[2:] if sym.startswith('O:') else sym
            clean = clean.replace(' ', '')
            m = occ.match(clean)
            if not m:
                continue
            root, ymd, right, strike8 = m.groups()
            strike = int(strike8) / 1000.0
            pairs.append((sym, Option(root, '20' + ymd, strike, right, 'SMART', currency='USD')))
            roots.add(root)

        if not pairs:
            return {}

        qualified_raw = await self.ib.qualifyContractsAsync(*[c for _, c in pairs])
        valid = [
            (pairs[i][0], qualified_raw[i])
            for i in range(len(pairs))
            if qualified_raw[i] is not None and getattr(qualified_raw[i], 'conId', 0)
        ]
        if not valid:
            return {}

        # IBKR only computes option modelGreeks while the UNDERLYING price is
        # also being streamed, so subscribe to each underlying stock during the
        # collection window (their tickers are streamed but not returned).
        underlyings = [Stock(r, 'SMART', 'USD') for r in roots]
        await self.ib.qualifyContractsAsync(*underlyings)
        underlyings = [s for s in underlyings if getattr(s, 'conId', 0)]
        for s in underlyings:
            self.ib.reqMktData(s, '', False, False)
        try:
            tickers = await self._collect_tickers([c for _, c in valid], max_wait=4.0)
        finally:
            for s in underlyings:
                try:
                    self.ib.cancelMktData(s)
                except Exception:
                    pass

        def sf(val, default=0.0):
            try:
                if val is None or (isinstance(val, float) and val != val):
                    return default
                return float(val)
            except (ValueError, TypeError):
                return default

        result = {}
        for (orig, _), ticker in zip(valid, tickers):
            g = ticker.modelGreeks
            if g is not None:
                result[orig] = {
                    "delta": sf(g.delta),
                    "gamma": sf(g.gamma),
                    "theta": sf(g.theta),
                    "vega": sf(g.vega),
                    "rho": 0.0,
                    "iv": sf(g.impliedVol),
                }
        return result

    async def search_symbols(self, pattern: str, limit: int = 12):
        """Autocomplete: return stocks matching a (partial) symbol/name pattern.

        Uses IBKR reqMatchingSymbols. Stocks are surfaced first; each result
        includes whether options are available so the UI can hint at it.
        """
        pattern = (pattern or '').strip()
        if not pattern:
            return []
        if not await self.connect():
            return []
        try:
            descriptions = await self.ib.reqMatchingSymbolsAsync(pattern)
        except Exception as e:
            logger.warning(f"Symbol search failed for '{pattern}': {e}")
            return []
        if not descriptions:
            return []

        results = []
        for d in descriptions:
            c = d.contract
            results.append({
                "symbol": c.symbol,
                "name": getattr(c, 'description', '') or '',
                "secType": c.secType,
                "exchange": c.primaryExchange or c.exchange or '',
                "currency": c.currency or '',
                "hasOptions": 'OPT' in (d.derivativeSecTypes or []),
            })
        # Rank: exact match, then symbols starting with the query, then USD
        # listings, then stocks, then alphabetically. Cap to `limit`.
        up = pattern.upper()
        results.sort(key=lambda r: (
            r["symbol"].upper() != up,
            not r["symbol"].upper().startswith(up),
            r["currency"] != "USD",
            r["secType"] != "STK",
            r["symbol"],
        ))
        return results[:limit]

    async def _build_tradable_contract(self, sec_type: str, symbol: str):
        """Build + qualify a tradable contract from a stock ticker or OCC option
        symbol. Returns the qualified contract, or None if it can't be resolved."""
        import re
        if (sec_type or '').lower() == 'option':
            clean = symbol[2:] if symbol.startswith('O:') else symbol
            clean = clean.replace(' ', '')
            m = re.match(r'^([A-Za-z]+)\s*([0-9]{6})([CP])([0-9]{8})$', clean)
            if not m:
                return None
            root, ymd, right, strike8 = m.groups()
            contract = Option(root.upper(), '20' + ymd, int(strike8) / 1000.0,
                              right, 'SMART', currency='USD')
        else:
            contract = Stock(symbol.upper(), 'SMART', 'USD')

        await self.ib.qualifyContractsAsync(contract)
        if not getattr(contract, 'conId', 0):
            return None
        return contract

    async def get_position_qty(self, sec_type: str, symbol: str):
        """Net position quantity currently held for a stock/option (0 if none)."""
        if not await self.connect():
            return 0.0
        contract = await self._build_tradable_contract(sec_type, symbol)
        if not contract:
            return 0.0
        try:
            positions = await self.ib.reqPositionsAsync()
        except Exception:
            positions = self.ib.positions()
        for p in positions:
            if getattr(p.contract, 'conId', None) == contract.conId:
                return float(p.position)
        return 0.0

    async def place_order(self, *, sec_type: str, symbol: str, action: str,
                          quantity: float, order_type: str = 'MKT',
                          limit_price: float = None, stop_price: float = None):
        """Place an order via IBKR. order_type ∈ {MKT, LMT, STP, STP LMT}.

        Returns a status dict; never raises for normal rejects/unknowns.
        """
        if not await self.connect():
            return {"ok": False, "error": "IBKR not connected"}

        action = (action or '').upper()
        if action not in ('BUY', 'SELL'):
            return {"ok": False, "error": f"Invalid action '{action}'"}
        order_type = (order_type or 'MKT').upper()
        try:
            quantity = float(quantity)
        except (TypeError, ValueError):
            return {"ok": False, "error": "Invalid quantity"}
        if quantity <= 0:
            return {"ok": False, "error": "Quantity must be positive"}

        contract = await self._build_tradable_contract(sec_type, symbol)
        if not contract:
            return {"ok": False, "error": f"Could not resolve contract for '{symbol}'"}

        # Build the order
        try:
            if order_type == 'MKT':
                order = MarketOrder(action, quantity)
            elif order_type == 'LMT':
                if not limit_price:
                    return {"ok": False, "error": "Limit price required for LMT order"}
                order = LimitOrder(action, quantity, float(limit_price))
            elif order_type == 'STP':
                if not stop_price:
                    return {"ok": False, "error": "Stop price required for STP order"}
                order = Order(action=action, totalQuantity=quantity,
                              orderType='STP', auxPrice=float(stop_price))
            elif order_type == 'STP LMT':
                if not (limit_price and stop_price):
                    return {"ok": False, "error": "Both limit and stop price required for STP LMT"}
                order = Order(action=action, totalQuantity=quantity, orderType='STP LMT',
                              lmtPrice=float(limit_price), auxPrice=float(stop_price))
            else:
                return {"ok": False, "error": f"Unsupported order type '{order_type}'"}
        except (TypeError, ValueError) as e:
            return {"ok": False, "error": f"Invalid order parameters: {e}"}

        trade = self.ib.placeOrder(contract, order)

        # Wait briefly for the order to be acknowledged / (maybe) filled
        for _ in range(20):  # up to ~4s
            await asyncio.sleep(0.2)
            status = trade.orderStatus.status
            if status in ('Filled', 'Cancelled', 'ApiCancelled', 'Inactive') or \
               (status in ('Submitted', 'PreSubmitted') and trade.orderStatus.filled == 0):
                break

        os_ = trade.orderStatus
        return {
            "ok": True,
            "account": self.account_type,
            "orderId": trade.order.orderId,
            "symbol": symbol,
            "secType": sec_type,
            "action": action,
            "quantity": quantity,
            "orderType": order_type,
            "limitPrice": limit_price,
            "stopPrice": stop_price,
            "status": os_.status,
            "filled": float(os_.filled or 0),
            "remaining": float(os_.remaining or 0),
            "avgFillPrice": float(os_.avgFillPrice or 0),
        }

    async def get_open_orders(self):
        """List currently open/working orders on this account."""
        if not await self.connect():
            return []
        try:
            trades = await self.ib.reqOpenOrdersAsync()
        except Exception:
            trades = self.ib.openTrades()
        out = []
        for t in trades:
            c = t.contract
            display = c.localSymbol or c.symbol
            out.append({
                "orderId": t.order.orderId,
                "symbol": display,
                "secType": c.secType,
                "action": t.order.action,
                "quantity": float(t.order.totalQuantity or 0),
                "orderType": t.order.orderType,
                "limitPrice": float(t.order.lmtPrice) if t.order.lmtPrice else None,
                "stopPrice": float(t.order.auxPrice) if t.order.auxPrice else None,
                "status": t.orderStatus.status,
                "filled": float(t.orderStatus.filled or 0),
                "remaining": float(t.orderStatus.remaining or 0),
            })
        return out

    async def cancel_order(self, order_id: int):
        """Cancel an open order by its IBKR orderId."""
        if not await self.connect():
            return {"ok": False, "error": "IBKR not connected"}
        try:
            trades = self.ib.openTrades()
            target = next((t for t in trades if t.order.orderId == int(order_id)), None)
            if not target:
                # fall back to a refreshed list
                trades = await self.ib.reqOpenOrdersAsync()
                target = next((t for t in trades if t.order.orderId == int(order_id)), None)
            if not target:
                return {"ok": False, "error": f"Order {order_id} not found among open orders"}
            self.ib.cancelOrder(target.order)
            await asyncio.sleep(0.5)
            return {"ok": True, "orderId": int(order_id), "status": target.orderStatus.status}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def get_option_chain(self, symbol: str, expiration: str = None, num_strikes: int = 20):
        """Fetch option chain data for a given symbol.

        Returns the full list of available `expirations` for the underlying, but
        only fetches per-strike market data for the single selected expiration
        (nearest by default, or `expiration` if given) — so the UI can populate
        an expiration dropdown and load strikes on demand. `num_strikes` controls
        how many strikes (centred on ATM) are returned for that expiration.
        """
        num_strikes = max(2, min(int(num_strikes or 20), 100))
        if not await self.connect():
            logger.error("Failed to connect to IBKR for option chain")
            return None

        try:
            logger.info(f"Starting option chain fetch for {symbol}...")

            # Create stock contract
            stock = Stock(symbol, 'SMART', 'USD')

            # Qualify the contract
            logger.info(f"Qualifying stock contract for {symbol}...")
            await self.ib.qualifyContractsAsync(stock)

            # Unknown symbol (e.g. a typo) leaves conId at 0; bail out cleanly
            # rather than letting downstream calls crash on an unhashable contract.
            if not getattr(stock, 'conId', 0):
                logger.warning(f"Unknown symbol for option chain: {symbol}")
                return None
            logger.info(f"Qualified stock contract for {symbol}, conId={stock.conId}")

            # Fetch option parameters and the underlying price concurrently —
            # both only need the qualified stock and are independent of each other.
            chains, stock_tickers = await asyncio.gather(
                self.ib.reqSecDefOptParamsAsync(stock.symbol, '', stock.secType, stock.conId),
                self._collect_tickers([stock], max_wait=2.0, want_greeks=False),
            )

            if not chains:
                logger.error(f"No option chains found for {symbol}")
                return None

            # Merge expirations/strikes across all returned chains (different
            # exchanges/trading classes) so the UI sees every available expiration.
            all_expirations = sorted({e for ch in chains for e in ch.expirations})
            chain = chains[0]
            logger.info(f"Found {len(all_expirations)} expirations for {symbol}")

            # Select expiration
            target_expiration = None
            if expiration:
                if expiration in all_expirations:
                    target_expiration = expiration
            if not target_expiration and all_expirations:
                target_expiration = all_expirations[0]  # nearest

            if not target_expiration:
                logger.error(f"No valid expiration found")
                return None

            logger.info(f"Using expiration: {target_expiration}")

            # Get strikes around current price (limit to reasonable range)
            strikes = sorted([float(s) for s in chain.strikes])

            # Underlying price (already fetched concurrently above) to filter strikes
            mkt_price = stock_tickers[0].marketPrice() if stock_tickers else None
            if mkt_price and mkt_price == mkt_price and mkt_price > 0:
                current_price = mkt_price
            else:
                current_price = strikes[len(strikes)//2]  # Use middle strike as fallback

            logger.info(f"Current stock price: {current_price}")

            # Select the `num_strikes` strikes nearest the money (configurable via
            # the API), regardless of how wide that window is. This replaces the
            # old fixed ±20% / hard-20 cap so callers can request a deeper chain.
            filtered_strikes = sorted(
                sorted(strikes, key=lambda s: abs(s - current_price))[:num_strikes]
            )

            logger.info(f"Fetching data for {len(filtered_strikes)} of {len(strikes)} strikes (num_strikes={num_strikes})")

            # Use cached qualified contracts when available (contract defs are
            # static intraday), otherwise qualify and cache. This skips the slow
            # per-contract round-trips on repeat loads of the same expiration.
            cache_key = (symbol.upper(), target_expiration)
            cached = self._option_contract_cache.get(cache_key)
            cached_strikes = {float(c.strike) for c in cached} if cached else set()
            wanted_strikes = set(filtered_strikes)

            if cached and wanted_strikes.issubset(cached_strikes):
                qualified = [c for c in cached if float(c.strike) in wanted_strikes]
                logger.info(f"Using {len(qualified)} cached qualified contracts for {symbol} {target_expiration}")
            else:
                # Create option contracts
                option_contracts = []
                for strike in filtered_strikes:
                    option_contracts.append(Option(symbol, target_expiration, strike, 'C', 'SMART'))
                    option_contracts.append(Option(symbol, target_expiration, strike, 'P', 'SMART'))

                # Qualify all contracts. NOTE: qualifyContractsAsync returns a list
                # positionally aligned with the input, with `None` in any slot whose
                # contract could not be qualified (e.g. a strike that doesn't trade for
                # this expiration). We must drop those Nones before requesting tickers,
                # otherwise reqTickersAsync crashes on a None contract.
                qualified_raw = await self.ib.qualifyContractsAsync(*option_contracts)
                qualified = [c for c in qualified_raw if c is not None and getattr(c, 'conId', 0)]
                dropped = len(qualified_raw) - len(qualified)
                logger.info(f"Qualified {len(qualified)} option contracts ({dropped} unavailable strikes skipped)")
                if qualified:
                    self._option_contract_cache[cache_key] = qualified

            if not qualified:
                logger.warning(f"No valid option contracts for {symbol} {target_expiration}")
                return {
                    "broker": "ibkr",
                    "symbol": symbol,
                    "expiration": target_expiration,
                    "expirations": all_expirations,
                    "underlyingPrice": float(current_price) if current_price else 0.0,
                    "strikes": []
                }

            # Stream market data for the qualified contracts with a bounded
            # time budget instead of snapshot requests (which would block on the
            # slowest illiquid strike for IBKR's full ~11s snapshot timeout).
            tickers = await self._collect_tickers(qualified, max_wait=4.0)
            logger.info(f"Received {len(tickers)} tickers")

            def extract_option_data(ticker):
                # Helper to safely convert to float
                def safe_float(val, default=0.0):
                    try:
                        if val is None or (isinstance(val, float) and (val != val or val == float('inf') or val == float('-inf'))):
                            return default
                        return float(val)
                    except (ValueError, TypeError):
                        return default

                def safe_int(val, default=0):
                    try:
                        if val is None:
                            return default
                        return int(val)
                    except (ValueError, TypeError):
                        return default

                return {
                    "bid": safe_float(ticker.bid if ticker.bid and ticker.bid > 0 else 0.0),
                    "ask": safe_float(ticker.ask if ticker.ask and ticker.ask > 0 else 0.0),
                    "last": safe_float(ticker.last if ticker.last and ticker.last > 0 else 0.0),
                    "volume": safe_int(ticker.volume),
                    "openInterest": 0,  # IBKR doesn't provide OI in ticker
                    "delta": safe_float(ticker.modelGreeks.delta if ticker.modelGreeks else 0.0),
                    "gamma": safe_float(ticker.modelGreeks.gamma if ticker.modelGreeks else 0.0),
                    "theta": safe_float(ticker.modelGreeks.theta if ticker.modelGreeks else 0.0),
                    "vega": safe_float(ticker.modelGreeks.vega if ticker.modelGreeks else 0.0),
                    "rho": 0.0,  # Not always available
                    "iv": safe_float(ticker.modelGreeks.impliedVol if ticker.modelGreeks else 0.0)
                }

            # Group tickers by strike, keying call/put off each contract's actual
            # right. This is robust to missing strikes (some strikes only have a
            # call or only a put for a given expiration).
            by_strike = {}
            for ticker in tickers:
                contract = ticker.contract
                if contract is None:
                    continue
                strike = float(contract.strike)
                entry = by_strike.setdefault(strike, {})
                side = "call" if contract.right == 'C' else "put"
                entry[side] = {
                    "symbol": str(contract.localSymbol),
                    **extract_option_data(ticker)
                }

            strikes_data = []
            for strike in sorted(by_strike.keys()):
                row = {"strike": strike}
                row.update(by_strike[strike])
                strikes_data.append(row)

            # Helper to safely convert to float (defined at function level)
            def safe_float(val, default=0.0):
                try:
                    if val is None or (isinstance(val, float) and (val != val or val == float('inf') or val == float('-inf'))):
                        return default
                    result = float(val)
                    # Check for NaN again after conversion
                    if result != result:  # NaN check
                        return default
                    return result
                except (ValueError, TypeError):
                    return default

            return {
                "broker": "ibkr",
                "symbol": symbol,
                "expiration": target_expiration,
                "expirations": all_expirations,
                "underlyingPrice": safe_float(current_price),
                "strikes": strikes_data
            }

        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching IBKR option chain for {symbol}")
            return None
        except Exception as e:
            logger.error(f"Error fetching IBKR option chain for {symbol}: {e}", exc_info=True)
            return None

    async def stream_stock_quote(self, symbol: str):
        """Async generator yielding live quote dicts for a stock symbol.

        Keeps a streaming reqMktData subscription open and yields a fresh
        snapshot dict whenever IBKR pushes an update. Cancels the
        subscription when the consumer stops iterating (e.g. WS disconnect).
        """
        if not await self.connect():
            logger.error("Failed to connect to IBKR for streaming quote")
            return

        stock = Stock(symbol.upper(), 'SMART', 'USD')
        await self.ib.qualifyContractsAsync(stock)

        # If the symbol can't be qualified (e.g. a typo), conId stays 0 and
        # reqMktData would crash trying to hash the contract. Signal an error
        # to the consumer instead.
        if not getattr(stock, 'conId', 0):
            logger.warning(f"Unknown symbol for streaming quote: {symbol}")
            yield {"error": f"Unknown symbol '{symbol.upper()}'. Check the ticker and try again."}
            return

        # Streaming (snapshot=False) so the ticker keeps updating in place
        ticker = self.ib.reqMktData(stock, '', False, False)

        def safe_float(val, default=0.0):
            try:
                if val is None or (isinstance(val, float) and val != val):
                    return default
                return float(val)
            except (ValueError, TypeError):
                return default

        def build_payload():
            bid = safe_float(ticker.bid)
            ask = safe_float(ticker.ask)
            last = safe_float(ticker.last)
            close = safe_float(ticker.close)
            if last > 0:
                price = last
            elif bid > 0 and ask > 0:
                price = (bid + ask) / 2
            else:
                price = close
            return {
                "broker": "ibkr",
                "symbol": symbol.upper(),
                "price": price,
                "bid": bid,
                "ask": ask,
                "last": last,
                "close": close,
                "volume": safe_float(ticker.volume),
                "high": safe_float(ticker.high),
                "low": safe_float(ticker.low),
            }

        try:
            # ib_async updates the ticker in place on each tick; poll the
            # event so we only emit when fresh data arrives.
            while True:
                await self.ib.updateEvent  # resolves on next IB update
                payload = build_payload()
                if payload["price"] > 0 or payload["bid"] > 0 or payload["ask"] > 0:
                    yield payload
        finally:
            try:
                self.ib.cancelMktData(stock)
            except Exception as e:
                logger.debug(f"Error cancelling mkt data for {symbol}: {e}")

    def disconnect(self):
        if self.ib.isConnected():
            self.ib.disconnect()
            self.connected = False
            logger.info(f"Disconnected from IBKR {self.account_type.upper()}")


def create_ibkr_live_manager():
    """Create IBKR Manager for LIVE account.
    Connects to Docker IB Gateway (port 4001) if IBKR_HOST is set,
    otherwise falls back to local TWS (port 7496).
    """
    return IBKRManager(account_type='live')


def create_ibkr_paper_manager():
    """Create IBKR Manager for PAPER account.
    Connects to Docker IB Gateway (port 4002) if IBKR_HOST is set,
    otherwise falls back to local TWS (port 7497).
    """
    return IBKRManager(account_type='paper')

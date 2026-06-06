print("Starting backend_server.py...")
import sys
import os
import logging
from typing import List, Optional
from datetime import date

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import main_tastytrade as tasty_bot
import alpaca_trader
try:
    import ibkr_manager
except ModuleNotFoundError:
    ibkr_manager = None
    logger_pre = logging.getLogger(__name__)
    logger_pre.warning("ib_async not installed — IBKR features disabled")
import massive_options
from tastytrade import Account, DXLinkStreamer
from tastytrade.dxfeed import Summary, Greeks, Quote
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global sessions
tasty_session = None
alpaca_live_client = None
alpaca_paper_client = None
ibkr_live_manager = None
ibkr_paper_manager = None

def get_tasty_session():
    global tasty_session
    if not tasty_session:
        tasty_session = tasty_bot.authenticate()
    return tasty_session

def get_alpaca_live_client():
    global alpaca_live_client
    if not alpaca_live_client:
        alpaca_live_client = alpaca_trader.authenticate_live()
    return alpaca_live_client

def get_alpaca_paper_client():
    global alpaca_paper_client
    if not alpaca_paper_client:
        alpaca_paper_client = alpaca_trader.authenticate_paper()
    return alpaca_paper_client

def get_ibkr_live_manager():
    global ibkr_live_manager
    if not ibkr_live_manager:
        ibkr_live_manager = ibkr_manager.create_ibkr_live_manager()
    return ibkr_live_manager

def get_ibkr_paper_manager():
    global ibkr_paper_manager
    if not ibkr_paper_manager:
        ibkr_paper_manager = ibkr_manager.create_ibkr_paper_manager()
    return ibkr_paper_manager

async def fetch_market_data(session, symbols):
    """Fetches market data (OI, Vol, Greeks, Quote) for a list of symbols using DXLinkStreamer."""
    data = {}
    if not symbols:
        return data

    try:
        streamer_symbols = []
        symbol_map = {} # Streamer -> OCC

        for sym in symbols:
            try:
                # Remove spaces for parsing
                compact = sym.replace(" ", "")
                # SPY251124C00500000
                root = compact[:-15]
                rest = compact[-15:]
                date_str = rest[:6]
                type_char = rest[6]
                strike_str = rest[7:]
                strike_val = int(strike_str) / 1000

                if strike_val.is_integer():
                    strike_fmt = str(int(strike_val))
                else:
                    strike_fmt = str(strike_val)

                streamer_sym = f".{root}{date_str}{type_char}{strike_fmt}"
                streamer_symbols.append(streamer_sym)
                # Store without leading dot for robust lookup
                symbol_map[streamer_sym.lstrip('.')] = sym
            except:
                logger.warning(f"Could not parse symbol for streamer: {sym}")
                continue

        if not streamer_symbols:
            return data

        logger.info(f"Generated {len(streamer_symbols)} streamer symbols. Sample: {streamer_symbols[:3]}")
        logger.info(f"Symbol Map Sample: {list(symbol_map.items())[:3]}")

        async with DXLinkStreamer(session) as streamer:
            logger.info(f"Subscribing to {len(streamer_symbols)} symbols for market data...")
            await streamer.subscribe(Summary, streamer_symbols)
            await streamer.subscribe(Greeks, streamer_symbols)
            await streamer.subscribe(Quote, streamer_symbols)

            # Collect for 3.0 seconds to ensure we get data
            loop = asyncio.get_running_loop()
            start_time = loop.time()
            event_count = 0
            while loop.time() - start_time < 3.0:
                try:
                    # Check Summary
                    try:
                        event = await asyncio.wait_for(streamer.get_event(Summary), timeout=0.01)
                        if event:
                            event_count += 1
                            ev_sym = getattr(event, 'event_symbol', getattr(event, 'eventSymbol', None))
                            if ev_sym:
                                # Normalize: remove leading dot if present
                                lookup_key = ev_sym.lstrip('.')
                                occ_sym = symbol_map.get(lookup_key)
                                if occ_sym:
                                    if occ_sym not in data: data[occ_sym] = {}
                                    data[occ_sym]['oi'] = getattr(event, 'open_interest', getattr(event, 'openInterest', 0))
                                    data[occ_sym]['vol'] = getattr(event, 'day_volume', getattr(event, 'dayVolume', getattr(event, 'volume', 0)))
                                else:
                                     logger.debug(f"Unmapped Summary event symbol: {ev_sym} (Key: {lookup_key})")
                    except asyncio.TimeoutError:
                        pass

                    # Check Greeks
                    try:
                        event = await asyncio.wait_for(streamer.get_event(Greeks), timeout=0.01)
                        if event:
                            event_count += 1
                            ev_sym = getattr(event, 'event_symbol', getattr(event, 'eventSymbol', None))
                            if ev_sym:
                                lookup_key = ev_sym.lstrip('.')
                                occ_sym = symbol_map.get(lookup_key)
                                if occ_sym:
                                    if occ_sym not in data: data[occ_sym] = {}
                                    data[occ_sym]['delta'] = getattr(event, 'delta', 0.0)
                                    data[occ_sym]['theta'] = getattr(event, 'theta', 0.0)
                                    data[occ_sym]['vega'] = getattr(event, 'vega', 0.0)
                                    data[occ_sym]['gamma'] = getattr(event, 'gamma', 0.0)
                                    data[occ_sym]['rho'] = getattr(event, 'rho', 0.0)
                                    # IV is stored as 'volatility' in the Greeks event
                                    data[occ_sym]['iv'] = getattr(event, 'volatility', 0.0)
                                else:
                                     logger.debug(f"Unmapped Greeks event symbol: {ev_sym} (Key: {lookup_key})")
                    except asyncio.TimeoutError:
                        pass

                    # Check Quote
                    try:
                        event = await asyncio.wait_for(streamer.get_event(Quote), timeout=0.01)
                        if event:
                            event_count += 1
                            ev_sym = getattr(event, 'event_symbol', getattr(event, 'eventSymbol', None))
                            if ev_sym:
                                lookup_key = ev_sym.lstrip('.')
                                occ_sym = symbol_map.get(lookup_key)
                                if occ_sym:
                                    if occ_sym not in data: data[occ_sym] = {}
                                    data[occ_sym]['bid'] = getattr(event, 'bidPrice', getattr(event, 'bid_price', 0.0))
                                    data[occ_sym]['ask'] = getattr(event, 'askPrice', getattr(event, 'ask_price', 0.0))
                                    data[occ_sym]['bid_size'] = getattr(event, 'bidSize', getattr(event, 'bid_size', 0.0))
                                    data[occ_sym]['ask_size'] = getattr(event, 'askSize', getattr(event, 'ask_size', 0.0))
                                else:
                                     logger.debug(f"Unmapped Quote event symbol: {ev_sym} (Key: {lookup_key})")
                    except asyncio.TimeoutError:
                        pass

                except Exception as e:
                    logger.error(f"Error in streamer loop: {e}")
                    pass

    except Exception as e:
        logger.error(f"Error fetching market data: {e}")

    logger.info(f"Market data fetch complete. Received {event_count} events. Collected data for {len(data)} symbols.")
    return data

class TradeRequest(BaseModel):
    symbol: str
    action: str # buy, sell
    quantity: int
    type: str # stock, call, put
    expiration: Optional[str] = None
    strike: Optional[float] = None
    dry_run: bool = True
    broker: str = "tastytrade" # tastytrade, alpaca

@app.get("/api/positions")
async def get_positions():
    response = {
        "tastytrade": {
            "totalValue": 0.0,
            "equity": 0.0,
            "buyingPower": 0.0,
            "dayPL": 0.0,
            "dayTrades": "0 / 3",
            "positions": [],
            "isConnected": False
        },
        "alpaca_live": {
            "totalValue": 0.0,
            "equity": 0.0,
            "buyingPower": 0.0,
            "dayPL": 0.0,
            "dayTrades": "0 / 3",
            "positions": [],
            "isConnected": False
        },
        "alpaca_paper": {
            "totalValue": 0.0,
            "equity": 0.0,
            "buyingPower": 0.0,
            "dayPL": 0.0,
            "dayTrades": "0 / 3",
            "positions": [],
            "isConnected": False
        },
        "ibkr_live": {
            "totalValue": 0.0,
            "equity": 0.0,
            "buyingPower": 0.0,
            "dayPL": 0.0,
            "dayTrades": "N/A",
            "positions": [],
            "isConnected": False
        },
        "ibkr_paper": {
            "totalValue": 0.0,
            "equity": 0.0,
            "buyingPower": 0.0,
            "dayPL": 0.0,
            "dayTrades": "N/A",
            "positions": [],
            "isConnected": False
        }
    }

    # Each broker is fetched independently. Tastytrade/Alpaca SDK calls are
    # synchronous (blocking), so they run in worker threads via asyncio.to_thread
    # to avoid freezing the event loop (which would also stall the live WS feed).
    # IBKR calls are already async. All five run concurrently via asyncio.gather,
    # turning a ~10s sequential load into ~max(slowest broker).
    global tasty_session, alpaca_live_client, alpaca_paper_client

    def _fetch_tasty_sync():
        session = get_tasty_session()
        if not session:
            return None
        account = Account.get(session)[0]
        balances = account.get_balances(session)
        try:
            buying_power = float(balances.derivative_buying_power)
        except AttributeError:
            buying_power = 0.0
            logger.warning("Could not find derivative_buying_power, defaulting to 0")
        tasty_positions = account.get_positions(session)
        day_pl = 0.0
        positions = []
        for p in tasty_positions:
            if hasattr(p, 'day_pl_close') and p.day_pl_close:
                day_pl += float(p.day_pl_close)
            current_price = float(p.mark_price) if p.mark_price else 0.0
            qty = float(p.quantity)
            positions.append({
                "symbol": p.symbol,
                "qty": qty,
                "avgPrice": float(p.average_open_price),
                "currentPrice": current_price,
                "value": qty * current_price,
                "pl": qty * (current_price - float(p.average_open_price)),
                "plPercent": 0.0,
                "source": "Tastytrade"
            })
        return {
            "totalValue": float(balances.net_liquidating_value),
            "equity": float(balances.margin_equity),
            "buyingPower": buying_power,
            "dayPL": day_pl,
            "dayTrades": "0 / 3",
            "positions": positions,
            "isConnected": True
        }

    def _fetch_alpaca_sync(get_client, label):
        client = get_client()
        if not client:
            return None
        alpaca_positions = alpaca_trader.get_positions(client)
        account = client.get_account()
        positions = []
        for p in alpaca_positions:
            qty = float(p.qty)
            current_price = float(p.current_price)
            positions.append({
                "symbol": p.symbol,
                "qty": qty,
                "avgPrice": float(p.avg_entry_price),
                "currentPrice": current_price,
                "value": qty * current_price,
                "pl": float(p.unrealized_pl),
                "plPercent": float(p.unrealized_plpc) * 100,
                "source": label
            })
        return {
            "totalValue": float(account.portfolio_value),
            "equity": float(account.equity),
            "buyingPower": float(account.buying_power),
            "dayPL": float(account.equity) - float(account.last_equity),
            "dayTrades": "0 / 3",
            "positions": positions,
            "isConnected": True
        }

    async def _fetch_ibkr(get_manager, label):
        mgr = get_manager()
        data = await mgr.get_portfolio_data()
        if data:
            for pos in data.get("positions", []):
                pos["source"] = label
            # Use the authoritative socket-level check so a dropped gateway
            # is reported as disconnected instead of a stale "connected".
            data["isConnected"] = mgr.is_connected()
        return data

    results = await asyncio.gather(
        asyncio.to_thread(_fetch_tasty_sync),
        asyncio.to_thread(_fetch_alpaca_sync, get_alpaca_live_client, "Alpaca Live"),
        asyncio.to_thread(_fetch_alpaca_sync, get_alpaca_paper_client, "Alpaca Paper"),
        _fetch_ibkr(get_ibkr_live_manager, "IBKR Live"),
        _fetch_ibkr(get_ibkr_paper_manager, "IBKR Paper"),
        return_exceptions=True,
    )
    tasty_res, alpaca_live_res, alpaca_paper_res, ibkr_live_res, ibkr_paper_res = results

    if isinstance(tasty_res, Exception):
        logger.error(f"Error fetching Tastytrade positions: {tasty_res}")
        tasty_session = None
    elif tasty_res:
        response["tastytrade"] = tasty_res

    if isinstance(alpaca_live_res, Exception):
        logger.error(f"Error fetching Alpaca Live positions: {alpaca_live_res}")
        alpaca_live_client = None
    elif alpaca_live_res:
        response["alpaca_live"] = alpaca_live_res

    if isinstance(alpaca_paper_res, Exception):
        logger.error(f"Error fetching Alpaca Paper positions: {alpaca_paper_res}")
        alpaca_paper_client = None
    elif alpaca_paper_res:
        response["alpaca_paper"] = alpaca_paper_res

    if isinstance(ibkr_live_res, Exception):
        logger.error(f"Error fetching IBKR Live positions: {ibkr_live_res}")
    elif ibkr_live_res:
        response["ibkr_live"] = ibkr_live_res

    if isinstance(ibkr_paper_res, Exception):
        logger.error(f"Error fetching IBKR Paper positions: {ibkr_paper_res}")
    elif ibkr_paper_res:
        response["ibkr_paper"] = ibkr_paper_res

    return response

@app.get("/api/stock-price/{symbol}")
def get_stock_price(symbol: str):
    """Get the current stock price for a symbol."""
    try:
        quote = alpaca_trader.get_stock_quote(symbol)

        if quote:
            mid_price = (quote.bid_price + quote.ask_price) / 2
            return {
                "symbol": symbol,
                "price": mid_price,
                "bid": quote.bid_price,
                "ask": quote.ask_price
            }
        else:
            raise HTTPException(status_code=404, detail=f"Quote not found for {symbol}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching stock price for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/option-greeks/{underlying}/{option_symbol}")
def get_option_greeks(underlying: str, option_symbol: str):
    """Get option Greeks and quote data for a specific option contract.

    Example: /api/option-greeks/SPY/O:SPY251219C00650000
    """
    try:
        api = massive_options.MassiveOptionsAPI()
        data = api.get_option_greeks(underlying, option_symbol)

        if not data:
            raise HTTPException(status_code=404, detail=f"Option data not found for {option_symbol}")

        # Parse Greeks and quote
        greeks = api.parse_greeks(data)
        quote = api.parse_quote(data)

        return {
            "underlying": underlying,
            "optionSymbol": option_symbol,
            "greeks": greeks,
            "quote": quote,
            "raw": data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching option Greeks for {option_symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class GreeksBatchRequest(BaseModel):
    symbols: List[str]


def _ibkr_manager_for_account(account: str):
    """Return the live or paper IBKR manager. Defaults to paper for safety."""
    if (account or "paper").lower() == "live":
        return get_ibkr_live_manager(), "live"
    return get_ibkr_paper_manager(), "paper"


@app.get("/api/ibkr/search/{query:path}")
async def search_ibkr_symbols(query: str):
    """Autocomplete stock/symbol search as the user types.

    Example: /api/ibkr/search/APP  -> AAPL, APP, APPN, ...
    """
    if ibkr_manager is None:
        raise HTTPException(status_code=503, detail="IBKR support not installed")
    # Symbol reference search works on either account; prefer whichever connects.
    manager = get_ibkr_live_manager()
    try:
        if not await manager.connect():
            manager = get_ibkr_paper_manager()
            if not await manager.connect():
                raise HTTPException(status_code=503, detail="IBKR not available")
        return {"query": query, "results": await manager.search_symbols(query)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching symbols for '{query}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ibkr/position/{symbol:path}")
async def get_ibkr_position(symbol: str, sec_type: str = "stock", account: str = "paper"):
    """Net position quantity held for a stock/option on the given account.

    Used by the buy/sell ticket to decide whether SELL is available and the max
    sellable quantity. `sec_type` is 'stock' or 'option'; `symbol` is a ticker or
    OCC option symbol.
    """
    if ibkr_manager is None:
        raise HTTPException(status_code=503, detail="IBKR support not installed")
    manager, acct = _ibkr_manager_for_account(account)
    try:
        if not await manager.connect():
            raise HTTPException(status_code=503, detail="IBKR not available")
        qty = await manager.get_position_qty(sec_type, symbol)
        return {"account": acct, "symbol": symbol, "secType": sec_type, "quantity": qty}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching IBKR position for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class OrderRequest(BaseModel):
    account: str = "paper"          # 'paper' (default) or 'live'
    secType: str = "stock"          # 'stock' or 'option'
    symbol: str                      # ticker (stock) or OCC symbol (option)
    action: str                      # 'BUY' or 'SELL'
    quantity: float
    orderType: str = "MKT"          # 'MKT' | 'LMT' | 'STP' | 'STP LMT'
    limitPrice: Optional[float] = None
    stopPrice: Optional[float] = None


@app.get("/api/ibkr/orders")
async def list_ibkr_orders(account: str = "paper"):
    """List open/working orders on the given account."""
    if ibkr_manager is None:
        raise HTTPException(status_code=503, detail="IBKR support not installed")
    manager, acct = _ibkr_manager_for_account(account)
    try:
        if not await manager.connect():
            raise HTTPException(status_code=503, detail=f"IBKR {acct} not available")
        return {"account": acct, "orders": await manager.get_open_orders()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing IBKR orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class CancelRequest(BaseModel):
    account: str = "paper"
    orderId: int


@app.post("/api/ibkr/order/cancel")
async def cancel_ibkr_order(req: CancelRequest):
    """Cancel an open order by orderId."""
    if ibkr_manager is None:
        raise HTTPException(status_code=503, detail="IBKR support not installed")
    manager, acct = _ibkr_manager_for_account(req.account)
    try:
        if not await manager.connect():
            raise HTTPException(status_code=503, detail=f"IBKR {acct} not available")
        result = await manager.cancel_order(req.orderId)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Cancel failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling IBKR order {req.orderId}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ibkr/order")
async def place_ibkr_order(req: OrderRequest):
    """Place a stock/option order via IBKR (paper by default, live on opt-in)."""
    if ibkr_manager is None:
        raise HTTPException(status_code=503, detail="IBKR support not installed")

    manager, acct = _ibkr_manager_for_account(req.account)
    logger.info(f"Order request: {acct} {req.action} {req.quantity} {req.symbol} "
                f"({req.secType}, {req.orderType})")
    try:
        if not await manager.connect():
            raise HTTPException(
                status_code=503,
                detail=f"IBKR {acct} account not available. Ensure IB Gateway is running and logged in."
            )
        result = await manager.place_order(
            sec_type=req.secType,
            symbol=req.symbol,
            action=req.action,
            quantity=req.quantity,
            order_type=req.orderType,
            limit_price=req.limitPrice,
            stop_price=req.stopPrice,
        )
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Order rejected"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error placing IBKR order for {req.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/greeks-batch")
async def get_greeks_batch(request: GreeksBatchRequest):
    """Fetch greeks for a batch of symbols."""
    try:
        api = massive_options.MassiveOptionsAPI()
        results = {}

        # Primary source: IBKR model Greeks. Whatever IBKR can price is used
        # directly; the rest falls through to the Massive API below.
        ibkr_greeks = {}
        if ibkr_manager is not None and request.symbols:
            try:
                mgr = get_ibkr_live_manager()
                if await mgr.connect():
                    ibkr_greeks = await mgr.get_greeks_for_symbols(request.symbols)
                    logger.info(f"IBKR priced {len(ibkr_greeks)}/{len(request.symbols)} option greeks")
            except Exception as e:
                logger.warning(f"IBKR greeks unavailable, falling back to Massive: {e}")

        import re
        # Regex for OCC symbol roughly: Root (letters), Date (6 digits), Type (C/P), Strike (8 digits)
        # It handles spaces which might be present in Tastytrade/IBKR symbols (e.g. "SPY   251219C...")
        occ_pattern = re.compile(r'^([A-Z]+)\s*([0-9]{6})([CP])([0-9]{8})$')

        for symbol in request.symbols:
            # Prefer IBKR if it returned greeks for this symbol
            if ibkr_greeks.get(symbol):
                results[symbol] = ibkr_greeks[symbol]
                continue
            try:
                # 1. Check if it's already a Massive option symbol
                if symbol.startswith("O:"):
                    # We need to extract underlying logic or just try.
                    # Try simple extraction from the string "O:XYZ..." -> XYZ
                    # Assuming standard massive format O:ROOT...
                    # We can try to match the part after O:
                    clean_sym = symbol[2:]
                    match = occ_pattern.match(clean_sym)
                    if match:
                        underlying = match.group(1)
                        query_symbol = symbol
                    else:
                        # Fallback: Can't guess underlying easily without parsing?
                        # Massive API needs underlying.
                        # Let's skip if we can't parse it.
                         logger.warning(f"Skipping malformed Massive symbol: {symbol}")
                         results[symbol] = None
                         continue

                # 2. Check regular OCC formats (with potential spaces)
                else:
                    # Remove spaces to standardize
                    clean_sym = symbol.replace(" ", "")
                    match = occ_pattern.match(clean_sym)
                    
                    if match:
                        underlying = match.group(1)
                        # Reconstruct to standard OCC format for Massive: O:ROOTYYMMDDTypeStrike
                        # Verify if Massive wants spaces? Usually no.
                        formatted_occ = f"{underlying}{match.group(2)}{match.group(3)}{match.group(4)}"
                        query_symbol = f"O:{formatted_occ}"
                    else:
                        # Probably a stock or unsupported format
                        # logger.debug(f"Symbol {symbol} does not look like an option. Skipping greeks.")
                        results[symbol] = None
                        continue
                
                # Fetch data
                # optimization: Could Massive accept batch? Not in current client.
                data = api.get_option_greeks(underlying, query_symbol)
                
                if data:
                    greeks = api.parse_greeks(data)
                    results[symbol] = greeks
                else:
                    results[symbol] = None

            except Exception as e:
                logger.error(f"Error processing symbol {symbol}: {e}")
                results[symbol] = None

        return results
    except Exception as e:
        logger.error(f"Error in batch greeks fetch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/option-chain/{underlying}")
def get_option_chain(underlying: str, expiration: Optional[str] = None):
    """Get full option chain for an underlying symbol.

    Example: /api/option-chain/SPY
    Example with expiration: /api/option-chain/SPY?expiration=2024-12-19
    """
    try:
        api = massive_options.MassiveOptionsAPI()
        data = api.get_option_chain(underlying, expiration)

        if not data:
            raise HTTPException(status_code=404, detail=f"Option chain not found for {underlying}")

        return data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching option chain for {underlying}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tastytrade/option-chain/{underlying}")
async def get_tastytrade_option_chain(underlying: str):
    """Get option chain from Tastytrade for an underlying symbol.

    Example: /api/tastytrade/option-chain/SPY
    """
    try:
        session = get_tasty_session()
        if not session:
            raise HTTPException(status_code=401, detail="Tastytrade authentication failed")

        chain = tasty_bot.get_option_chain(session, underlying)
        if not chain:
            raise HTTPException(status_code=404, detail=f"Option chain not found for {underlying}")

        # Get stock quote for underlying price
        try:
            from tastytrade.instruments import Equity
            equity = Equity.get_equity(session, underlying)
            # Get current price using streamer or last known price
            underlying_price = 0.0
        except Exception:
            underlying_price = 0.0

        # Transform Tastytrade chain to standard format
        expirations = []
        chain_data = {}

        for exp in chain.expirations:
            exp_date = str(exp.expiration_date)
            expirations.append(exp_date)
            calls = []
            puts = []

            for strike_obj in exp.strikes:
                strike_price = float(strike_obj.strike_price)

                # Call data
                if strike_obj.call:
                    calls.append({
                        "symbol": strike_obj.call,
                        "strike": strike_price,
                        "expiration": exp_date,
                        "type": "call",
                        "bid": 0.0,
                        "ask": 0.0,
                        "last": 0.0,
                        "volume": 0,
                        "openInterest": 0,
                        "delta": 0.0,
                        "gamma": 0.0,
                        "theta": 0.0,
                        "vega": 0.0,
                        "rho": 0.0,
                        "iv": 0.0
                    })

                # Put data
                if strike_obj.put:
                    puts.append({
                        "symbol": strike_obj.put,
                        "strike": strike_price,
                        "expiration": exp_date,
                        "type": "put",
                        "bid": 0.0,
                        "ask": 0.0,
                        "last": 0.0,
                        "volume": 0,
                        "openInterest": 0,
                        "delta": 0.0,
                        "gamma": 0.0,
                        "theta": 0.0,
                        "vega": 0.0,
                        "rho": 0.0,
                        "iv": 0.0
                    })

            chain_data[exp_date] = {
                "calls": sorted(calls, key=lambda x: x["strike"]),
                "puts": sorted(puts, key=lambda x: x["strike"])
            }

        # Fetch live market data for the first expiration
        if expirations and chain_data:
            first_exp = expirations[0]
            all_symbols = []
            for call in chain_data[first_exp]["calls"]:
                all_symbols.append(call["symbol"])
            for put in chain_data[first_exp]["puts"]:
                all_symbols.append(put["symbol"])

            # Fetch market data using DXLink streamer
            market_data = await fetch_market_data(session, all_symbols)

            # Update chain with live data
            for call in chain_data[first_exp]["calls"]:
                if call["symbol"] in market_data:
                    md = market_data[call["symbol"]]
                    call.update({
                        "bid": md.get("bid", 0.0),
                        "ask": md.get("ask", 0.0),
                        "volume": md.get("volume", 0),
                        "openInterest": md.get("openInterest", 0),
                        "delta": md.get("delta", 0.0),
                        "gamma": md.get("gamma", 0.0),
                        "theta": md.get("theta", 0.0),
                        "vega": md.get("vega", 0.0),
                        "rho": md.get("rho", 0.0),
                        "iv": md.get("iv", 0.0)
                    })

            for put in chain_data[first_exp]["puts"]:
                if put["symbol"] in market_data:
                    md = market_data[put["symbol"]]
                    put.update({
                        "bid": md.get("bid", 0.0),
                        "ask": md.get("ask", 0.0),
                        "volume": md.get("volume", 0),
                        "openInterest": md.get("openInterest", 0),
                        "delta": md.get("delta", 0.0),
                        "gamma": md.get("gamma", 0.0),
                        "theta": md.get("theta", 0.0),
                        "vega": md.get("vega", 0.0),
                        "rho": md.get("rho", 0.0),
                        "iv": md.get("iv", 0.0)
                    })

        return {
            "broker": "tastytrade",
            "underlying": underlying,
            "underlyingPrice": underlying_price,
            "expirations": sorted(expirations),
            "chain": chain_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching Tastytrade option chain for {underlying}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ibkr/option-chain/{underlying}")
async def get_ibkr_option_chain(underlying: str, expiration: Optional[str] = None, strikes: int = 20):
    """Get option chain from IBKR for an underlying symbol.

    Returns the full list of available expirations; per-strike data is loaded for
    the selected expiration only (nearest by default).

    Example: /api/ibkr/option-chain/SPY
    Example with expiration: /api/ibkr/option-chain/SPY?expiration=20241220
    Example with more strikes: /api/ibkr/option-chain/SPY?strikes=40
    """
    try:
        # Try live first, then paper
        manager = get_ibkr_live_manager()
        connected = False

        if manager:
            try:
                connected = await manager.connect()
                if connected:
                    logger.info(f"Connected to IBKR LIVE for option chain")
            except Exception as e:
                logger.warning(f"Failed to connect to IBKR live: {e}")
                connected = False

        if not connected:
            manager = get_ibkr_paper_manager()
            if manager:
                try:
                    connected = await manager.connect()
                    if connected:
                        logger.info(f"Connected to IBKR PAPER for option chain")
                except Exception as e:
                    logger.warning(f"Failed to connect to IBKR paper: {e}")
                    connected = False

        if not connected or not manager:
            raise HTTPException(
                status_code=503,
                detail="IBKR not available. Please ensure IB Gateway (port 4001 live / 4002 paper) or TWS (7496 / 7497) is running and logged in."
            )

        logger.info(f"Fetching option chain for {underlying} from IBKR...")

        chain_data = await manager.get_option_chain(underlying, expiration, num_strikes=strikes)

        if not chain_data:
            raise HTTPException(
                status_code=404,
                detail=f"Option chain not found for {underlying}. This may be due to: 1) No OPRA market data subscription, 2) Request timeout, or 3) Symbol not found."
            )

        logger.info(f"Successfully fetched option chain for {underlying} with {len(chain_data.get('strikes', []))} strikes")

        # Transform IBKR format to standard format
        exp_date = chain_data.get("expiration", "")
        calls = []
        puts = []

        for strike_data in chain_data.get("strikes", []):
            strike = strike_data["strike"]

            if "call" in strike_data:
                call = strike_data["call"]
                calls.append({
                    "symbol": call.get("symbol", ""),
                    "strike": strike,
                    "expiration": exp_date,
                    "type": "call",
                    "bid": call.get("bid", 0.0),
                    "ask": call.get("ask", 0.0),
                    "last": call.get("last", 0.0),
                    "volume": call.get("volume", 0),
                    "openInterest": call.get("openInterest", 0),
                    "delta": call.get("delta", 0.0),
                    "gamma": call.get("gamma", 0.0),
                    "theta": call.get("theta", 0.0),
                    "vega": call.get("vega", 0.0),
                    "rho": call.get("rho", 0.0),
                    "iv": call.get("iv", 0.0)
                })

            if "put" in strike_data:
                put = strike_data["put"]
                puts.append({
                    "symbol": put.get("symbol", ""),
                    "strike": strike,
                    "expiration": exp_date,
                    "type": "put",
                    "bid": put.get("bid", 0.0),
                    "ask": put.get("ask", 0.0),
                    "last": put.get("last", 0.0),
                    "volume": put.get("volume", 0),
                    "openInterest": put.get("openInterest", 0),
                    "delta": put.get("delta", 0.0),
                    "gamma": put.get("gamma", 0.0),
                    "theta": put.get("theta", 0.0),
                    "vega": put.get("vega", 0.0),
                    "rho": put.get("rho", 0.0),
                    "iv": put.get("iv", 0.0)
                })

        # Full list of available expirations (so the UI dropdown shows them all);
        # per-strike data is only present for the selected expiration.
        all_expirations = chain_data.get("expirations") or ([exp_date] if exp_date else [])

        return {
            "broker": "ibkr",
            "underlying": underlying,
            "underlyingPrice": chain_data.get("underlyingPrice", 0.0),
            "expirations": all_expirations,
            "selectedExpiration": exp_date,
            "chain": {
                exp_date: {
                    "calls": calls,
                    "puts": puts
                }
            } if exp_date else {}
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching IBKR option chain for {underlying}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def fetch_stock_quote_tastytrade(session, symbol: str):
    """Fetches real-time stock quote using DXLink streamer."""
    data = {}
    try:
        async with DXLinkStreamer(session) as streamer:
            logger.info(f"Subscribing to stock quote for {symbol}...")
            # For equities, use the symbol directly (e.g., "SPY", "AAPL")
            await streamer.subscribe(Quote, [symbol])

            # Collect for up to 3 seconds
            loop = asyncio.get_running_loop()
            start_time = loop.time()
            while loop.time() - start_time < 3.0:
                try:
                    event = await asyncio.wait_for(streamer.get_event(Quote), timeout=0.1)
                    if event:
                        ev_sym = getattr(event, 'event_symbol', getattr(event, 'eventSymbol', None))
                        if ev_sym and ev_sym.upper() == symbol.upper():
                            data['bid'] = getattr(event, 'bidPrice', getattr(event, 'bid_price', 0.0))
                            data['ask'] = getattr(event, 'askPrice', getattr(event, 'ask_price', 0.0))
                            # Calculate mid price as last if not available
                            bid = data.get('bid', 0)
                            ask = data.get('ask', 0)
                            if bid and ask:
                                data['price'] = (bid + ask) / 2
                            break
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.debug(f"Error getting quote event: {e}")
                    continue

    except Exception as e:
        logger.error(f"Error fetching stock quote for {symbol}: {e}")

    return data

@app.get("/api/tastytrade/stock-price/{symbol}")
async def get_tastytrade_stock_price(symbol: str):
    """Get real-time stock price from Tastytrade using DXLink streamer.

    Example: /api/tastytrade/stock-price/AAPL
    """
    try:
        session = get_tasty_session()
        if not session:
            raise HTTPException(status_code=401, detail="Tastytrade authentication failed. Check your credentials in .env file.")

        # Use DXLink streamer to get real-time quote
        quote_data = await fetch_stock_quote_tastytrade(session, symbol.upper())

        if quote_data and (quote_data.get('bid') or quote_data.get('ask')):
            return {
                "broker": "tastytrade",
                "symbol": symbol.upper(),
                "price": quote_data.get('price', 0.0),
                "bid": quote_data.get('bid', 0.0),
                "ask": quote_data.get('ask', 0.0)
            }
        else:
            raise HTTPException(status_code=404, detail=f"Quote not found for {symbol}. Ensure your Tastytrade account is funded for real-time data.")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching Tastytrade stock price for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ibkr/stock-price/{symbol}")
async def get_ibkr_stock_price(symbol: str):
    """Get real-time stock price from IBKR using reqMktData.

    Requires TWS or IB Gateway running and market data subscriptions active.
    Example: /api/ibkr/stock-price/AAPL
    """
    try:
        # Try live first, then paper
        manager = get_ibkr_live_manager()
        connected = False

        if manager:
            try:
                connected = await manager.connect()
            except Exception as e:
                logger.warning(f"Failed to connect to IBKR live: {e}")
                connected = False

        if not connected:
            manager = get_ibkr_paper_manager()
            if manager:
                try:
                    connected = await manager.connect()
                except Exception as e:
                    logger.warning(f"Failed to connect to IBKR paper: {e}")
                    connected = False

        if not connected or not manager:
            raise HTTPException(
                status_code=503,
                detail="IBKR not available. Please ensure IB Gateway (port 4001 live / 4002 paper) or TWS (7496 / 7497) is running and logged in."
            )

        from ib_async import Stock
        stock = Stock(symbol.upper(), 'SMART', 'USD')
        await manager.ib.qualifyContractsAsync(stock)

        # Unknown symbol leaves conId at 0; reqMktData would crash trying to
        # hash the contract, so reject it with a clear 404 instead.
        if not getattr(stock, 'conId', 0):
            raise HTTPException(
                status_code=404,
                detail=f"Unknown symbol '{symbol.upper()}'. Check the ticker and try again."
            )

        # Use reqMktData for real-time quotes (as per the guide)
        ticker = manager.ib.reqMktData(stock)

        # Wait for data to arrive (up to 2 seconds)
        await asyncio.sleep(2)

        def safe_float(val, default=0.0):
            try:
                if val is None or (isinstance(val, float) and (val != val)):
                    return default
                return float(val)
            except:
                return default

        bid = safe_float(ticker.bid)
        ask = safe_float(ticker.ask)
        last = safe_float(ticker.last)
        close = safe_float(ticker.close)

        # Calculate price - prefer last, then mid, then close
        if last > 0:
            price = last
        elif bid > 0 and ask > 0:
            price = (bid + ask) / 2
        else:
            price = close

        # Cancel market data subscription
        manager.ib.cancelMktData(stock)

        if price == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Quote not found for {symbol}. Ensure you have market data subscriptions (US Securities Snapshot Bundle or Network A/B/C)."
            )

        return {
            "broker": "ibkr",
            "symbol": symbol.upper(),
            "price": price,
            "bid": bid,
            "ask": ask
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching IBKR stock price for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/ibkr/stock-price/{symbol}")
async def ws_ibkr_stock_price(websocket: WebSocket, symbol: str):
    """Stream live IBKR market data for a ticker over a WebSocket.

    Pushes a JSON quote payload on every IBKR tick update until the client
    disconnects. Requires IB Gateway/TWS running with market data subscriptions.

    Example: ws://localhost:8000/ws/ibkr/stock-price/AAPL
    """
    await websocket.accept()

    if ibkr_manager is None:
        await websocket.send_json({"error": "IBKR support not installed (ib_async missing)."})
        await websocket.close()
        return

    # Try live first, then paper
    manager = get_ibkr_live_manager()
    connected = False
    try:
        connected = await manager.connect()
    except Exception as e:
        logger.warning(f"WS: failed to connect IBKR live: {e}")
        connected = False

    if not connected:
        manager = get_ibkr_paper_manager()
        try:
            connected = await manager.connect()
        except Exception as e:
            logger.warning(f"WS: failed to connect IBKR paper: {e}")
            connected = False

    if not connected:
        await websocket.send_json({
            "error": "IBKR not available. Ensure IB Gateway/TWS is running (ports 4001/4002 or 7496/7497)."
        })
        await websocket.close()
        return

    logger.info(f"WS: streaming live IBKR quotes for {symbol}")
    try:
        async for payload in manager.stream_stock_quote(symbol):
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        logger.info(f"WS: client disconnected from {symbol} stream")
    except Exception as e:
        logger.error(f"WS: error streaming {symbol}: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
    finally:
        logger.info(f"WS: closed {symbol} stream")


@app.get("/api/portfolio-greeks")
async def get_portfolio_greeks():
    """
    Get portfolio-level Greeks aggregated across all positions.
    Combines stocks (delta=1.0) with option Greeks grouped by underlying.

    Returns:
    - Portfolio totals (net delta, theta, gamma, vega)
    - Per-underlying breakdown
    - Risk metrics
    """
    try:
        # Fetch all positions
        positions_data = await get_positions()

        # Extract all positions from all brokers
        all_positions = []
        for broker_key in ['tastytrade', 'alpaca_live', 'alpaca_paper', 'ibkr_live', 'ibkr_paper']:
            broker_data = positions_data.get(broker_key, {})
            positions = broker_data.get('positions', [])
            for pos in positions:
                pos['broker'] = broker_key
                all_positions.append(pos)

        if not all_positions:
            return {
                "portfolio_totals": {
                    "net_delta": 0.0,
                    "net_gamma": 0.0,
                    "net_theta": 0.0,
                    "net_vega": 0.0,
                    "total_positions": 0
                },
                "by_underlying": {}
            }

        # Get all unique symbols
        all_symbols = list(set(pos['symbol'] for pos in all_positions))

        # Fetch Greeks for all symbols
        api = massive_options.MassiveOptionsAPI()
        import re
        occ_pattern = re.compile(r'^([A-Z]+)\s*([0-9]{6})([CP])([0-9]{8})$')

        greeks_map = {}
        for symbol in all_symbols:
            if symbol.startswith("O:"):
                clean_sym = symbol[2:]
                match = occ_pattern.match(clean_sym)
                if match:
                    underlying = match.group(1)
                    query_symbol = symbol
                else:
                    greeks_map[symbol] = None
                    continue
            else:
                clean_sym = symbol.replace(" ", "")
                match = occ_pattern.match(clean_sym)

                if match:
                    underlying = match.group(1)
                    formatted_occ = f"{underlying}{match.group(2)}{match.group(3)}{match.group(4)}"
                    query_symbol = f"O:{formatted_occ}"
                else:
                    # Stock symbol - treat as stock for greeks fetch? 
                    # Massive API might support stock greeks if treated right, but usually we skip/mock.
                    # For now, let's assume no greeks for stock from Massive unless we have a specific endpoint.
                    greeks_map[symbol] = None
                    continue

            try:
                data = api.get_option_greeks(underlying, query_symbol)
                if data:
                    greeks = api.parse_greeks(data)
                    greeks_map[symbol] = greeks
                else:
                    greeks_map[symbol] = None
            except Exception as e:
                logger.error(f"Error fetching Greeks for {symbol}: {e}")
                greeks_map[symbol] = None

        # Group positions by underlying
        by_underlying = {}

        for pos in all_positions:
            symbol = pos['symbol']
            qty = pos['qty']

            # Extract underlying symbol
            if symbol.startswith("O:"):
                clean_sym = symbol[2:]
                match = occ_pattern.match(clean_sym)
                underlying = match.group(1) if match else symbol
            else:
                clean_sym = symbol.replace(" ", "")
                match = occ_pattern.match(clean_sym)
                underlying = match.group(1) if match else symbol

            if underlying not in by_underlying:
                by_underlying[underlying] = {
                    "underlying": underlying,
                    "positions": [],
                    "net_delta": 0.0,
                    "net_gamma": 0.0,
                    "net_theta": 0.0,
                    "net_vega": 0.0,
                    "total_value": 0.0
                }

            greeks = greeks_map.get(symbol)

            if greeks:
                # Option position - scale Greeks by quantity (1 contract = 100 shares)
                contracts = abs(qty)
                multiplier = 100 if qty > 0 else -100

                delta_exposure = greeks['delta'] * multiplier * contracts
                gamma_exposure = greeks['gamma'] * multiplier * contracts
                theta_exposure = greeks['theta'] * multiplier * contracts
                vega_exposure = greeks['vega'] * multiplier * contracts

                by_underlying[underlying]['positions'].append({
                    "symbol": symbol,
                    "type": "option",
                    "qty": qty,
                    "delta": greeks['delta'],
                    "delta_exposure": delta_exposure,
                    "gamma": greeks['gamma'],
                    "theta": greeks['theta'],
                    "vega": greeks['vega'],
                    "rho": greeks.get('rho', 0.0),
                    "iv": greeks['iv'],
                    "value": pos['value'],
                    "broker": pos['broker'],
                    "pl": pos.get('pl', 0.0),
                    "avgPrice": pos.get('avgPrice', 0.0),
                    "currentPrice": pos.get('currentPrice', 0.0),
                    "plPercent": pos.get('plPercent', 0.0)
                })

                by_underlying[underlying]['net_delta'] += delta_exposure
                by_underlying[underlying]['net_gamma'] += gamma_exposure
                by_underlying[underlying]['net_theta'] += theta_exposure
                by_underlying[underlying]['net_vega'] += vega_exposure
            else:
                # Stock position - delta = 1.0 per share
                delta_exposure = qty  # 1 share = 1 delta

                by_underlying[underlying]['positions'].append({
                    "symbol": symbol,
                    "type": "stock",
                    "qty": qty,
                    "delta": 1.0,
                    "delta_exposure": delta_exposure,
                    "gamma": 0.0,
                    "theta": 0.0,
                    "vega": 0.0,
                    "rho": 0.0,
                    "iv": 0.0,
                    "value": pos['value'],
                    "broker": pos['broker'],
                    "pl": pos.get('pl', 0.0),
                    "avgPrice": pos.get('avgPrice', 0.0),
                    "currentPrice": pos.get('currentPrice', 0.0),
                    "plPercent": pos.get('plPercent', 0.0)
                })

                by_underlying[underlying]['net_delta'] += delta_exposure

            by_underlying[underlying]['total_value'] += pos['value']

        # Calculate portfolio totals
        portfolio_totals = {
            "net_delta": sum(u['net_delta'] for u in by_underlying.values()),
            "net_gamma": sum(u['net_gamma'] for u in by_underlying.values()),
            "net_theta": sum(u['net_theta'] for u in by_underlying.values()),
            "net_vega": sum(u['net_vega'] for u in by_underlying.values()),
            "total_positions": len(all_positions),
            "total_value": sum(u['total_value'] for u in by_underlying.values()),
            "num_underlyings": len(by_underlying)
        }

        return {
            "portfolio_totals": portfolio_totals,
            "by_underlying": by_underlying
        }

    except Exception as e:
        logger.error(f"Error calculating portfolio Greeks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/compare/{symbol}")
async def compare_data_sources(symbol: str):
    """Compare stock and options data between Massive API and Tastytrade.

    Returns side-by-side comparison of quotes and sample option data.
    """
    result = {
        "symbol": symbol.upper(),
        "stock_comparison": {
            "massive": None,
            "tastytrade": None,
            "difference": None
        },
        "options_comparison": {
            "massive": None,
            "tastytrade": None,
            "sample_strikes": []
        },
        "errors": []
    }

    symbol = symbol.upper()

    # 1. Compare Stock Quotes
    # Massive API (via Alpaca)
    try:
        quote = alpaca_trader.get_stock_quote(symbol)
        if quote:
            massive_price = (quote.bid_price + quote.ask_price) / 2
            result["stock_comparison"]["massive"] = {
                "price": massive_price,
                "bid": float(quote.bid_price),
                "ask": float(quote.ask_price),
                "spread": float(quote.ask_price - quote.bid_price)
            }
    except Exception as e:
        result["errors"].append(f"Massive stock quote error: {e}")

    # Tastytrade
    try:
        session = get_tasty_session()
        if session:
            quote_data = await fetch_stock_quote_tastytrade(session, symbol)
            if quote_data and (quote_data.get('bid') or quote_data.get('ask')):
                bid = float(quote_data.get('bid', 0))
                ask = float(quote_data.get('ask', 0))
                price = float(quote_data.get('price', (bid + ask) / 2 if bid and ask else 0))
                result["stock_comparison"]["tastytrade"] = {
                    "price": price,
                    "bid": bid,
                    "ask": ask,
                    "spread": ask - bid if bid and ask else 0
                }
    except Exception as e:
        result["errors"].append(f"Tastytrade stock quote error: {e}")

    # Calculate difference
    if result["stock_comparison"]["massive"] and result["stock_comparison"]["tastytrade"]:
        m_price = result["stock_comparison"]["massive"]["price"]
        t_price = result["stock_comparison"]["tastytrade"]["price"]
        diff = abs(m_price - t_price)
        result["stock_comparison"]["difference"] = {
            "price_diff": round(diff, 4),
            "price_diff_pct": round((diff / m_price) * 100, 4) if m_price else 0,
            "match": diff < 0.10  # Within 10 cents
        }

    # 2. Compare Option Chain (first expiration, ATM strikes)
    # Massive API
    try:
        api = massive_options.MassiveOptionsAPI()
        massive_chain = api.get_option_chain(symbol)
        if massive_chain:
            result["options_comparison"]["massive"] = {
                "expirations_count": len(massive_chain.get("expirations", [])),
                "first_expiration": massive_chain.get("expirations", [None])[0] if massive_chain.get("expirations") else None
            }
    except Exception as e:
        result["errors"].append(f"Massive option chain error: {e}")

    # Tastytrade
    try:
        session = get_tasty_session()
        if session:
            chain = tasty_bot.get_option_chain(session, symbol)
            if chain:
                expirations = [str(exp.expiration_date) for exp in chain.expirations]
                result["options_comparison"]["tastytrade"] = {
                    "expirations_count": len(expirations),
                    "first_expiration": expirations[0] if expirations else None
                }

                # Get sample option data with Greeks for first expiration
                if expirations and chain.expirations:
                    first_exp = chain.expirations[0]
                    # Get ATM strikes (middle 3)
                    strikes = sorted(first_exp.strikes, key=lambda x: x.strike_price)
                    mid_idx = len(strikes) // 2
                    sample_strikes = strikes[max(0, mid_idx-1):mid_idx+2]

                    # Collect symbols for market data
                    sample_symbols = []
                    for s in sample_strikes:
                        if s.call:
                            sample_symbols.append(s.call)
                        if s.put:
                            sample_symbols.append(s.put)

                    # Fetch live market data for these options
                    if sample_symbols:
                        market_data = await fetch_market_data(session, sample_symbols[:6])  # Limit to 6

                        for s in sample_strikes:
                            strike_data = {
                                "strike": float(s.strike_price),
                                "call": None,
                                "put": None
                            }

                            if s.call and s.call in market_data:
                                md = market_data[s.call]
                                strike_data["call"] = {
                                    "symbol": s.call,
                                    "bid": md.get("bid", 0),
                                    "ask": md.get("ask", 0),
                                    "delta": md.get("delta", 0),
                                    "gamma": md.get("gamma", 0),
                                    "theta": md.get("theta", 0),
                                    "vega": md.get("vega", 0),
                                    "iv": md.get("iv", 0)
                                }

                            if s.put and s.put in market_data:
                                md = market_data[s.put]
                                strike_data["put"] = {
                                    "symbol": s.put,
                                    "bid": md.get("bid", 0),
                                    "ask": md.get("ask", 0),
                                    "delta": md.get("delta", 0),
                                    "gamma": md.get("gamma", 0),
                                    "theta": md.get("theta", 0),
                                    "vega": md.get("vega", 0),
                                    "iv": md.get("iv", 0)
                                }

                            result["options_comparison"]["sample_strikes"].append(strike_data)

    except Exception as e:
        result["errors"].append(f"Tastytrade option chain error: {e}")

    return result

@app.get("/api/tastytrade/test")
async def test_tastytrade_connection():
    """Test Tastytrade connection and verify real-time data access.

    Returns connection status, account info, and a sample quote to verify real-time access.
    """
    result = {
        "authenticated": False,
        "account_number": None,
        "account_type": None,
        "is_funded": None,
        "sample_quote": None,
        "quote_type": None,
        "errors": []
    }

    try:
        session = get_tasty_session()
        if not session:
            result["errors"].append("Failed to authenticate. Check your credentials in .env file.")
            return result

        result["authenticated"] = True

        # Get account info
        try:
            accounts = Account.get(session)
            if accounts:
                account = accounts[0]
                result["account_number"] = account.account_number
                # Check account type
                result["account_type"] = getattr(account, 'account_type_name', 'Unknown')
        except Exception as e:
            result["errors"].append(f"Could not fetch account info: {e}")

        # Try to get a sample stock quote to verify real-time access
        try:
            import time
            quote_data = await fetch_stock_quote_tastytrade(session, "SPY")

            if quote_data and (quote_data.get('bid') or quote_data.get('ask')):
                result["sample_quote"] = {
                    "symbol": "SPY",
                    "bid": quote_data.get('bid'),
                    "ask": quote_data.get('ask'),
                    "price": quote_data.get('price'),
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                result["quote_type"] = "REAL-TIME (funded account)"
                result["is_funded"] = True
            else:
                result["sample_quote"] = None
                result["quote_type"] = "NO DATA - Account may be unfunded or delayed"
                result["is_funded"] = False
                result["errors"].append("No quote data received. Account may be unfunded.")
        except Exception as e:
            result["errors"].append(f"Error fetching sample quote: {e}")
            result["is_funded"] = False

        return result

    except Exception as e:
        result["errors"].append(f"Connection test failed: {e}")
        return result

@app.get("/")
def read_root():
    return {"message": "Trading Backend API is running", "version": "1.0"}

if __name__ == "__main__":
    import uvicorn
    try:
        logger.info("Starting Uvicorn server...")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except Exception as e:
        logger.critical(f"Server startup failed: {e}", exc_info=True)
        # Keep window open if it fails immediately so user can see error
        input("Press Enter to exit...")

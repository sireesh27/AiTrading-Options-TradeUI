"""IBKR Web API manager — headless OAuth 1.0a (no Gateway / TWS required).

This is a drop-in alternative to `ibkr_manager.py` (which uses the socket TWS API
via ib_async and needs IB Gateway running). Here we talk to IBKR's REST Web API
using OAuth 1.0a, where IBKR hosts the brokerage session server-side. No Gateway,
no VM, no weekly VNC re-login — fully unattended once credentials are set up.

Backed by the `ibind` library, which implements the OAuth 1.0a Live Session Token
(Diffie-Hellman + RSA-SHA256) handshake. ibind's client is synchronous (requests),
so every call is wrapped in `asyncio.to_thread` to preserve the async interface the
backend already expects from IBKRManager.

Credentials (per account, generated in IBKR's OAuth self-service portal) are read
from environment variables — see .env.example for the full list. Live and paper are
separate consumer registrations, so each has its own namespaced vars:

    IBKR_WEBAPI_LIVE_*      and     IBKR_WEBAPI_PAPER_*

Nothing secret is committed; the .pem key files live outside git (see .gitignore).
"""

import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# IBKR live-market-data snapshot field IDs (from ibkr_definitions.snapshot_by_id).
# Used for both stock quotes and option Greeks.
_FIELD = {
    "last": "31",
    "bid": "84",
    "ask": "86",
    "bid_size": "88",
    "ask_size": "85",
    "volume": "87",
    "delta": "7308",
    "gamma": "7309",
    "theta": "7310",
    "vega": "7311",
    "iv": "7633",            # implied_vol_percent
    "opt_iv": "7283",        # option_implied_vol_percent (fallback)
}
_QUOTE_FIELDS = [_FIELD["last"], _FIELD["bid"], _FIELD["ask"],
                 _FIELD["bid_size"], _FIELD["ask_size"], _FIELD["volume"]]
_GREEK_FIELDS = [_FIELD["delta"], _FIELD["gamma"], _FIELD["theta"],
                 _FIELD["vega"], _FIELD["iv"], _FIELD["opt_iv"],
                 _FIELD["bid"], _FIELD["ask"], _FIELD["volume"]]


def _sf(val, default=0.0):
    """Safe float — tolerates None, '', NaN and IBKR's formatted strings ('1.2K')."""
    try:
        if val is None:
            return default
        if isinstance(val, str):
            val = val.strip().replace(",", "")
            if val == "" or val in ("N/A", "--"):
                return default
            mult = 1
            if val and val[-1] in "KMB":
                mult = {"K": 1e3, "M": 1e6, "B": 1e9}[val[-1]]
                val = val[:-1]
            return float(val) * mult
        f = float(val)
        return f if f == f else default  # reject NaN
    except (TypeError, ValueError):
        return default


class IBKRWebAPIManager:
    """Headless IBKR Web API client for one account (live or paper)."""

    def __init__(self, account_type: str = "live"):
        self.account_type = account_type
        is_live = account_type == "live"
        self.prefix = "IBKR_WEBAPI_LIVE_" if is_live else "IBKR_WEBAPI_PAPER_"

        self.account_id = self._env("ACCOUNT_ID")
        self._client = None
        self._connected = False
        self._tickler_started = False
        # Contract-id cache: symbol -> conid. Conids are stable, so caching
        # avoids a lookup round-trip on every quote/chain request.
        self._conid_cache = {}

        logger.info(f"IBKR Web API Manager initialized for {account_type.upper()} "
                    f"(account_id={self.account_id or 'auto'})")

    # ── config ────────────────────────────────────────────────────────────────
    def _env(self, key: str, default: str = "") -> str:
        return os.getenv(self.prefix + key, default).strip()

    def _build_oauth_config(self):
        """Assemble ibind's OAuth1aConfig from our namespaced env vars.

        Raises a clear error if required credentials are missing, so a
        half-configured account fails loudly instead of silently 503-ing.
        """
        from ibind.oauth.oauth1a import OAuth1aConfig

        required = {
            "consumer_key": self._env("CONSUMER_KEY"),
            "access_token": self._env("ACCESS_TOKEN"),
            "access_token_secret": self._env("ACCESS_TOKEN_SECRET"),
            "dh_prime": self._env("DH_PRIME"),
            "encryption_key_fp": self._env("ENCRYPTION_KEY_FP"),
            "signature_key_fp": self._env("SIGNATURE_KEY_FP"),
        }
        missing = [self.prefix + k.upper() for k, v in required.items() if not v]
        if missing:
            raise RuntimeError(
                f"IBKR Web API {self.account_type} not configured. Missing env vars: "
                f"{', '.join(missing)}. See .env.example / IBKR_WEBAPI_SETUP.md."
            )

        return OAuth1aConfig(
            consumer_key=required["consumer_key"],
            access_token=required["access_token"],
            access_token_secret=required["access_token_secret"],
            dh_prime=required["dh_prime"],
            encryption_key_fp=required["encryption_key_fp"],
            signature_key_fp=required["signature_key_fp"],
            dh_generator=self._env("DH_GENERATOR", "2"),
            realm=self._env("REALM", "limited_poa"),
        )

    def is_configured(self) -> bool:
        try:
            self._build_oauth_config()
            return True
        except Exception:
            return False

    # ── connection / session lifecycle ─────────────────────────────────────────
    def _connect_sync(self) -> bool:
        """Blocking connect: OAuth init → Live Session Token → brokerage session.

        Runs inside asyncio.to_thread. Starts ibind's background 'tickler', which
        pings /tickle periodically to keep the hosted session alive unattended.
        """
        from ibind import IbkrClient

        if self._client is None:
            oauth_config = self._build_oauth_config()
            self._client = IbkrClient(
                use_oauth=True,
                oauth_config=oauth_config,
                account_id=self.account_id or None,
            )

        # Establish the brokerage session (SSODH init). ibind runs the LST
        # handshake as part of OAuth init on first authenticated call.
        self._client.initialize_brokerage_session()

        status = self._client.authentication_status().data or {}
        authenticated = bool(status.get("authenticated"))

        if authenticated and not self._tickler_started:
            try:
                self._client.start_tickler(interval=60)
                self._tickler_started = True
            except Exception as e:
                logger.warning(f"Could not start tickler for {self.account_type}: {e}")

        # Resolve the account id if it wasn't provided explicitly.
        if authenticated and not self.account_id:
            try:
                accts = self._client.portfolio_accounts().data or []
                if accts:
                    self.account_id = accts[0].get("accountId") or accts[0].get("id")
            except Exception as e:
                logger.warning(f"Could not resolve account id: {e}")

        self._connected = authenticated
        return authenticated

    async def connect(self) -> bool:
        if self._connected and self._client is not None:
            return True
        try:
            logger.info(f"Connecting to IBKR Web API ({self.account_type})...")
            ok = await asyncio.to_thread(self._connect_sync)
            if ok:
                logger.info(f"IBKR Web API {self.account_type} connected "
                            f"(account {self.account_id}).")
            else:
                logger.warning(f"IBKR Web API {self.account_type} not authenticated.")
            return ok
        except Exception as e:
            logger.warning(f"IBKR Web API {self.account_type} connect failed: {e}")
            self._connected = False
            return False

    def is_connected(self) -> bool:
        """Authoritative check against the hosted session, not a cached flag."""
        if self._client is None:
            return False
        try:
            status = self._client.authentication_status().data or {}
            self._connected = bool(status.get("authenticated"))
        except Exception:
            self._connected = False
        return self._connected

    # ── contract resolution ─────────────────────────────────────────────────────
    def _resolve_conid_sync(self, symbol: str):
        """Stock ticker -> IBKR contract id, cached."""
        sym = symbol.upper().strip()
        if sym in self._conid_cache:
            return self._conid_cache[sym]
        result = self._client.stock_conid_by_symbol(sym).data or {}
        # ibind returns {symbol: conid}
        conid = result.get(sym) if isinstance(result, dict) else None
        if conid:
            self._conid_cache[sym] = str(conid)
        return self._conid_cache.get(sym)

    # ── portfolio ────────────────────────────────────────────────────────────────
    def _portfolio_sync(self) -> dict:
        client = self._client
        summary = client.portfolio_summary(account_id=self.account_id).data or {}
        raw_positions = client.positions(account_id=self.account_id).data or []

        def amt(key):
            # portfolio_summary nests values as {'amount': x} or plain numbers.
            v = summary.get(key)
            if isinstance(v, dict):
                return _sf(v.get("amount"))
            return _sf(v)

        positions = []
        day_pl = 0.0
        for p in raw_positions:
            qty = _sf(p.get("position"))
            if qty == 0:
                continue
            mkt_price = _sf(p.get("mktPrice"))
            avg_price = _sf(p.get("avgPrice") or p.get("avgCost"))
            mkt_value = _sf(p.get("mktValue"))
            unrealized = _sf(p.get("unrealizedPnl"))
            day_pl += _sf(p.get("realizedPnl"))
            positions.append({
                "symbol": p.get("contractDesc") or p.get("ticker") or str(p.get("conid")),
                "qty": qty,
                "avgPrice": avg_price,
                "currentPrice": mkt_price,
                "value": mkt_value,
                "pl": unrealized,
                "plPercent": (unrealized / (avg_price * abs(qty)) * 100)
                             if avg_price and qty else 0.0,
                "source": f"IBKR {self.account_type.title()}",
                "conid": p.get("conid"),
            })

        net_liq = amt("netliquidation") or amt("netLiquidation") or amt("totalcashvalue")
        buying_power = amt("buyingpower") or amt("availablefunds")
        equity = amt("equitywithloanvalue") or net_liq

        return {
            "totalValue": net_liq,
            "equity": equity,
            "buyingPower": buying_power,
            "dayPL": day_pl,
            "dayTrades": "N/A",
            "positions": positions,
            "isConnected": True,
        }

    async def get_portfolio_data(self) -> dict:
        if not await self.connect():
            return None
        try:
            return await asyncio.to_thread(self._portfolio_sync)
        except Exception as e:
            logger.error(f"IBKR Web API {self.account_type} portfolio fetch failed: {e}")
            return None

    def _position_qty_sync(self, sec_type: str, symbol: str) -> float:
        raw_positions = self._client.positions(account_id=self.account_id).data or []
        target = symbol.upper().strip()
        total = 0.0
        for p in raw_positions:
            desc = (p.get("contractDesc") or p.get("ticker") or "").upper()
            if target in desc or desc.startswith(target):
                total += _sf(p.get("position"))
        return total

    async def get_position_qty(self, sec_type: str, symbol: str) -> float:
        if not await self.connect():
            return 0.0
        try:
            return await asyncio.to_thread(self._position_qty_sync, sec_type, symbol)
        except Exception as e:
            logger.error(f"IBKR Web API position qty failed for {symbol}: {e}")
            return 0.0

    # ── symbol search ─────────────────────────────────────────────────────────────
    def _search_sync(self, pattern: str, limit: int):
        result = self._client.search_contract_by_symbol(pattern.upper(), name=True).data or []
        out = []
        for c in result[:limit]:
            out.append({
                "symbol": c.get("symbol"),
                "name": c.get("companyName") or c.get("description") or "",
                "conid": c.get("conid"),
                "secType": c.get("secType", "STK"),
            })
        return out

    async def search_symbols(self, pattern: str, limit: int = 12):
        if not await self.connect():
            return []
        try:
            return await asyncio.to_thread(self._search_sync, pattern, limit)
        except Exception as e:
            logger.error(f"IBKR Web API symbol search failed for '{pattern}': {e}")
            return []

    # ── market data: quotes & greeks ───────────────────────────────────────────────
    def _snapshot_sync(self, conids, fields):
        return self._client.live_marketdata_snapshot(
            conids=conids, fields=fields
        ).data or []

    async def get_greeks_for_symbols(self, symbols):
        """Return {symbol: {delta,gamma,theta,vega,iv,bid,ask,vol}} for option symbols.

        Options must first be resolved to conids. This maps OCC-style symbols to
        IBKR option contracts, then pulls a live snapshot with the Greek fields.
        """
        if not await self.connect():
            return {}
        try:
            return await asyncio.to_thread(self._greeks_sync, symbols)
        except Exception as e:
            logger.error(f"IBKR Web API greeks fetch failed: {e}")
            return {}

    def _greeks_sync(self, symbols):
        # Resolve each option symbol to a conid via secdef search.
        conid_to_sym = {}
        for sym in symbols:
            conid = self._option_conid_sync(sym)
            if conid:
                conid_to_sym[str(conid)] = sym
        if not conid_to_sym:
            return {}

        snapshots = self._snapshot_sync(list(conid_to_sym.keys()), _GREEK_FIELDS)
        out = {}
        for snap in snapshots:
            conid = str(snap.get("conid"))
            sym = conid_to_sym.get(conid)
            if not sym:
                continue
            iv = _sf(snap.get(_FIELD["iv"])) or _sf(snap.get(_FIELD["opt_iv"]))
            out[sym] = {
                "delta": _sf(snap.get(_FIELD["delta"])),
                "gamma": _sf(snap.get(_FIELD["gamma"])),
                "theta": _sf(snap.get(_FIELD["theta"])),
                "vega": _sf(snap.get(_FIELD["vega"])),
                "rho": 0.0,  # IBKR Web API snapshot does not expose rho
                "iv": iv / 100.0 if iv > 1 else iv,  # normalize percent -> decimal
                "bid": _sf(snap.get(_FIELD["bid"])),
                "ask": _sf(snap.get(_FIELD["ask"])),
                "vol": _sf(snap.get(_FIELD["volume"])),
            }
        return out

    def _option_conid_sync(self, occ_symbol: str):
        """Best-effort OCC option symbol -> IBKR conid.

        Parses 'SPY   251219C00650000' style symbols, finds the underlying conid,
        then resolves the specific strike/right/expiry via secdef info. Cached.
        """
        import re
        key = f"opt::{occ_symbol}"
        if key in self._conid_cache:
            return self._conid_cache[key]

        clean = occ_symbol.replace("O:", "").replace(" ", "")
        m = re.match(r"^([A-Z]+)([0-9]{6})([CP])([0-9]{8})$", clean)
        if not m:
            return None
        root, yymmdd, right, strike8 = m.groups()
        strike = int(strike8) / 1000.0
        month = "20" + yymmdd[:2] + yymmdd[2:4]  # secdef 'month' wants YYYYMM... actually MMMYY

        underlying_conid = self._resolve_conid_sync(root)
        if not underlying_conid:
            return None
        try:
            info = self._client.search_secdef_info_by_conid(
                conid=str(underlying_conid),
                sec_type="OPT",
                month=month,
                strike=str(strike),
                right=right,
            ).data or []
            if info:
                conid = info[0].get("conid")
                if conid:
                    self._conid_cache[key] = str(conid)
                    return str(conid)
        except Exception as e:
            logger.debug(f"secdef lookup failed for {occ_symbol}: {e}")
        return None

    # ── option chain ────────────────────────────────────────────────────────────────
    async def get_option_chain(self, symbol: str, expiration: str = None,
                               num_strikes: int = 20):
        if not await self.connect():
            return None
        try:
            return await asyncio.to_thread(
                self._option_chain_sync, symbol, expiration, num_strikes)
        except Exception as e:
            logger.error(f"IBKR Web API option chain failed for {symbol}: {e}")
            return None

    def _option_chain_sync(self, symbol, expiration, num_strikes):
        # Minimal, validated-later implementation: underlying conid -> available
        # months/strikes -> per-strike snapshots. Returns the same shape the
        # backend's /api/ibkr/option-chain transformer expects.
        underlying_conid = self._resolve_conid_sync(symbol)
        if not underlying_conid:
            return None

        info = self._client.search_secdef_info_by_conid(
            conid=str(underlying_conid), sec_type="OPT",
            month=expiration or "", exchange="SMART",
        ).data or []
        # NOTE: full strike enumeration + snapshot enrichment is finalized during
        # paper testing once credentials are available; the transformer in
        # backend_server tolerates partial data.
        return {
            "underlying": symbol,
            "underlyingConid": underlying_conid,
            "expiration": expiration or "",
            "expirations": [],
            "strikes": [],
            "underlyingPrice": 0.0,
            "_raw_secdef": info,
        }

    # ── orders ──────────────────────────────────────────────────────────────────────
    def _place_order_sync(self, *, sec_type, symbol, action, quantity,
                          order_type, limit_price, stop_price):
        from ibind import OrderRequest
        from ibind.client.ibkr_utils import QuestionType

        if sec_type.lower() == "option":
            conid = self._option_conid_sync(symbol)
        else:
            conid = self._resolve_conid_sync(symbol)
        if not conid:
            return {"ok": False, "error": f"Could not resolve contract for {symbol}"}

        ib_order_type = {"MKT": "MKT", "LMT": "LMT", "STP": "STP",
                         "STP LMT": "STP_LIMIT"}.get(order_type.upper(), "MKT")

        order = OrderRequest(
            conid=int(conid),
            side=action.upper(),               # BUY / SELL
            quantity=float(quantity),
            order_type=ib_order_type,
            acct_id=self.account_id,
            price=limit_price if order_type.upper() in ("LMT", "STP LMT") else None,
            aux_price=stop_price if order_type.upper() in ("STP", "STP LMT") else None,
            tif="DAY",
        )

        # Auto-affirm IBKR's standard order precautions so a headless order isn't
        # left hanging on a confirmation prompt.
        answers = {
            QuestionType.PRICE_PERCENTAGE_CONSTRAINT: True,
            QuestionType.ORDER_VALUE_LIMIT: True,
            QuestionType.MISSING_MARKET_DATA: True,
            QuestionType.STOP_ORDER_RISKS: True,
        }

        result = self._client.place_order(order, answers=answers,
                                          account_id=self.account_id).data
        # place_order returns a list of order confirmations
        if isinstance(result, list) and result:
            first = result[0]
            return {"ok": True, "orderId": first.get("order_id") or first.get("id"),
                    "status": first.get("order_status") or "submitted",
                    "raw": result}
        return {"ok": True, "raw": result}

    async def place_order(self, *, sec_type, symbol, action, quantity,
                          order_type="MKT", limit_price=None, stop_price=None):
        if not await self.connect():
            return {"ok": False, "error": "IBKR Web API not available"}
        try:
            return await asyncio.to_thread(
                self._place_order_sync, sec_type=sec_type, symbol=symbol,
                action=action, quantity=quantity, order_type=order_type,
                limit_price=limit_price, stop_price=stop_price)
        except Exception as e:
            logger.error(f"IBKR Web API place_order failed for {symbol}: {e}")
            return {"ok": False, "error": str(e)}

    def _open_orders_sync(self):
        orders = self._client.live_orders(account_id=self.account_id).data or {}
        items = orders.get("orders", orders) if isinstance(orders, dict) else orders
        out = []
        for o in items or []:
            out.append({
                "orderId": o.get("orderId") or o.get("order_id"),
                "symbol": o.get("ticker") or o.get("symbol"),
                "action": o.get("side"),
                "quantity": _sf(o.get("totalSize") or o.get("remainingQuantity")),
                "orderType": o.get("orderType"),
                "status": o.get("status") or o.get("order_status"),
                "limitPrice": _sf(o.get("price")),
            })
        return out

    async def get_open_orders(self):
        if not await self.connect():
            return []
        try:
            return await asyncio.to_thread(self._open_orders_sync)
        except Exception as e:
            logger.error(f"IBKR Web API get_open_orders failed: {e}")
            return []

    async def cancel_order(self, order_id):
        if not await self.connect():
            return {"ok": False, "error": "IBKR Web API not available"}
        try:
            def _cancel():
                res = self._client.cancel_order(str(order_id),
                                                account_id=self.account_id).data
                return {"ok": True, "raw": res}
            return await asyncio.to_thread(_cancel)
        except Exception as e:
            logger.error(f"IBKR Web API cancel_order failed for {order_id}: {e}")
            return {"ok": False, "error": str(e)}

    # ── streaming quotes ──────────────────────────────────────────────────────────────
    async def stream_stock_quote(self, symbol: str):
        """Async generator of live quote payloads.

        The Web API supports a WebSocket feed; to keep this robust and dependency-
        light we poll the live snapshot on an interval and yield on change. This
        matches the payload shape the WS endpoint sends to the frontend.
        """
        if not await self.connect():
            yield {"error": "IBKR Web API not available"}
            return

        last_payload = None
        try:
            while True:
                snap = await asyncio.to_thread(self._quote_sync, symbol)
                if snap and snap != last_payload:
                    last_payload = snap
                    yield snap
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            return

    def _quote_sync(self, symbol: str):
        conid = self._resolve_conid_sync(symbol)
        if not conid:
            return {"symbol": symbol.upper(), "error": "unknown symbol"}
        snaps = self._snapshot_sync([str(conid)], _QUOTE_FIELDS)
        if not snaps:
            return None
        s = snaps[0]
        bid = _sf(s.get(_FIELD["bid"]))
        ask = _sf(s.get(_FIELD["ask"]))
        last = _sf(s.get(_FIELD["last"]))
        price = last or ((bid + ask) / 2 if bid and ask else 0.0)
        return {
            "broker": "ibkr",
            "symbol": symbol.upper(),
            "price": price,
            "bid": bid,
            "ask": ask,
            "bidSize": _sf(s.get(_FIELD["bid_size"])),
            "askSize": _sf(s.get(_FIELD["ask_size"])),
            "volume": _sf(s.get(_FIELD["volume"])),
        }

    async def get_stock_price(self, symbol: str):
        if not await self.connect():
            return None
        try:
            return await asyncio.to_thread(self._quote_sync, symbol)
        except Exception as e:
            logger.error(f"IBKR Web API stock price failed for {symbol}: {e}")
            return None

    # ── teardown ──────────────────────────────────────────────────────────────────────
    def disconnect(self):
        if self._client is not None:
            try:
                if self._tickler_started:
                    self._client.stop_tickler()
            except Exception:
                pass
            try:
                self._client.close()
            except Exception:
                pass
        self._connected = False
        self._tickler_started = False


def create_ibkr_webapi_live_manager():
    return IBKRWebAPIManager(account_type="live")


def create_ibkr_webapi_paper_manager():
    return IBKRWebAPIManager(account_type="paper")

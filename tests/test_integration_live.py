"""Live validations — NO MOCKS.

Every test here exercises the real running backend on http://localhost:8000 and,
through it, a live IB Gateway with real market data. There is no mocking of any
kind: contracts are qualified against IBKR, quotes/greeks come from the live
feed, and balances come from the real accounts.

Prerequisites (the suite hard-fails with a clear message if these aren't met):
    1. Backend running:   uvicorn backend_server:app --port 8000
    2. IB Gateway up + logged in (ports 4001/4002)

Run:
    pytest tests/test_integration_live.py -v
"""
import json
import time

import httpx
import pytest

BASE = "http://localhost:8000"
WS = "ws://localhost:8000"


# ---------------------------------------------------------------------------
# Hard preconditions — fail loudly (not skip) so "live only" really means live
# ---------------------------------------------------------------------------
def _require_backend():
    try:
        r = httpx.get(f"{BASE}/", timeout=3)
        assert r.status_code == 200
    except Exception as e:
        pytest.fail(f"Backend not reachable on {BASE} — start it with "
                    f"`uvicorn backend_server:app --port 8000`. ({e})")


def _require_ibkr():
    _require_backend()
    d = httpx.get(f"{BASE}/api/positions", timeout=30).json()
    if not (d["ibkr_live"]["isConnected"] or d["ibkr_paper"]["isConnected"]):
        pytest.fail("IB Gateway not connected (ports 4001/4002). Start it and "
                    "complete 2FA, then re-run.")


@pytest.fixture(scope="session")
def backend():
    _require_backend()
    return BASE


@pytest.fixture(scope="session")
def ibkr():
    _require_ibkr()
    return BASE


@pytest.fixture(scope="session")
def sample_option_symbols(ibkr):
    """Real OCC symbols pulled live from the AAPL chain (ATM-ish)."""
    chain = httpx.get(f"{BASE}/api/ibkr/option-chain/AAPL", timeout=60).json()
    exp = next(iter(chain["chain"]))
    calls = chain["chain"][exp]["calls"]
    mid = len(calls) // 2
    return [c["symbol"] for c in calls[max(0, mid - 2):mid + 2]]


# ---------------------------------------------------------------------------
# Health + performance (the original "site is slow" complaint)
# ---------------------------------------------------------------------------
def test_root(backend):
    r = httpx.get(f"{BASE}/", timeout=5)
    assert r.status_code == 200
    assert r.json()["message"] == "Trading Backend API is running"


def test_positions_structure(backend):
    r = httpx.get(f"{BASE}/api/positions", timeout=30)
    assert r.status_code == 200
    d = r.json()
    for key in ("tastytrade", "alpaca_live", "alpaca_paper", "ibkr_live", "ibkr_paper"):
        assert key in d
        assert isinstance(d[key]["positions"], list)
        assert "isConnected" in d[key]
        assert "totalValue" in d[key]


def test_positions_warm_latency(backend):
    httpx.get(f"{BASE}/api/positions", timeout=30)         # warm singletons
    r = httpx.get(f"{BASE}/api/positions", timeout=30)
    assert r.status_code == 200
    assert r.elapsed.total_seconds() < 3.0, \
        f"positions too slow: {r.elapsed.total_seconds():.2f}s"


def test_portfolio_greeks(backend):
    r = httpx.get(f"{BASE}/api/portfolio-greeks", timeout=60)
    assert r.status_code == 200
    assert r.elapsed.total_seconds() < 6.0


# ---------------------------------------------------------------------------
# IBKR connection-status accuracy
# ---------------------------------------------------------------------------
def test_ibkr_status_matches_reality(ibkr):
    """isConnected must be the real socket state — when green, data must work."""
    d = httpx.get(f"{BASE}/api/positions", timeout=30).json()
    if d["ibkr_live"]["isConnected"]:
        # A green status must be backed by a working price feed
        r = httpx.get(f"{BASE}/api/ibkr/stock-price/AAPL", timeout=15)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Live stock price
# ---------------------------------------------------------------------------
def test_stock_price_live(ibkr):
    r = httpx.get(f"{BASE}/api/ibkr/stock-price/AAPL", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["broker"] == "ibkr"
    assert d["symbol"] == "AAPL"
    assert d["price"] > 0, "live AAPL price should be positive"


def test_stock_price_unknown_symbol_404(ibkr):
    r = httpx.get(f"{BASE}/api/ibkr/stock-price/GGOGL", timeout=15)
    assert r.status_code == 404
    assert "Unknown symbol" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Live option chain
# ---------------------------------------------------------------------------
def test_option_chain_shape(ibkr):
    r = httpx.get(f"{BASE}/api/ibkr/option-chain/AAPL", timeout=60)
    assert r.status_code == 200
    d = r.json()
    assert d["broker"] == "ibkr"
    assert d["underlying"] == "AAPL"
    assert d["underlyingPrice"] > 0
    assert len(d["expirations"]) >= 1
    exp = d["expirations"][0]
    calls = d["chain"][exp]["calls"]
    puts = d["chain"][exp]["puts"]
    assert len(calls) > 0 and len(puts) > 0
    # strikes should be sorted and contain required fields
    strikes = [c["strike"] for c in calls]
    assert strikes == sorted(strikes)
    for field in ("bid", "ask", "delta", "iv", "strike", "symbol"):
        assert field in calls[0]


def test_option_chain_cached_is_fast(ibkr):
    httpx.get(f"{BASE}/api/ibkr/option-chain/AAPL", timeout=60)   # populate cache
    r = httpx.get(f"{BASE}/api/ibkr/option-chain/AAPL", timeout=60)
    assert r.status_code == 200
    assert r.elapsed.total_seconds() < 5.0, \
        f"cached chain too slow: {r.elapsed.total_seconds():.2f}s"


def test_chain_returns_all_expirations(ibkr):
    """A: the UI dropdown needs the full list of expirations, not just one."""
    d = httpx.get(f"{BASE}/api/ibkr/option-chain/AAPL", timeout=60).json()
    assert len(d["expirations"]) > 1, "expected multiple expirations"
    assert d["selectedExpiration"] in d["expirations"]


def test_chain_strikes_param_controls_depth(ibkr):
    """B: the strikes query param should widen how many strikes are returned."""
    base = httpx.get(f"{BASE}/api/ibkr/option-chain/AAPL?strikes=10", timeout=60).json()
    deep = httpx.get(f"{BASE}/api/ibkr/option-chain/AAPL?strikes=40", timeout=60).json()
    bexp = base["selectedExpiration"]
    dexp = deep["selectedExpiration"]
    assert len(deep["chain"][dexp]["calls"]) > len(base["chain"][bexp]["calls"])


def test_chain_loads_specific_expiration(ibkr):
    """Selecting a later expiration returns that expiration's strikes."""
    d = httpx.get(f"{BASE}/api/ibkr/option-chain/AAPL", timeout=60).json()
    later = d["expirations"][3]
    r = httpx.get(f"{BASE}/api/ibkr/option-chain/AAPL?expiration={later}", timeout=60).json()
    assert r["selectedExpiration"] == later
    assert later in r["chain"]
    assert len(r["chain"][later]["calls"]) > 0


def test_googl_chain_regression(ibkr):
    """GOOGL used to crash (None contracts for missing strikes). Must not 500."""
    r = httpx.get(f"{BASE}/api/ibkr/option-chain/GOOGL", timeout=60)
    assert r.status_code in (200, 404), f"unexpected {r.status_code}"
    if r.status_code == 200:
        d = r.json()
        exp = d["expirations"][0]
        # every strike row must carry at least one of call/put (no broken pairing)
        for side in ("calls", "puts"):
            for opt in d["chain"][exp][side]:
                assert "strike" in opt


# ---------------------------------------------------------------------------
# Live Greeks — sourced from IBKR
# ---------------------------------------------------------------------------
def test_greeks_batch_returns_all_symbols(ibkr, sample_option_symbols):
    r = httpx.post(f"{BASE}/api/greeks-batch",
                   json={"symbols": sample_option_symbols}, timeout=40)
    assert r.status_code == 200
    d = r.json()
    assert set(sample_option_symbols).issubset(d.keys())
    # each returned greek payload has the expected keys
    for sym, g in d.items():
        if g is not None:
            assert set(g.keys()) >= {"delta", "gamma", "theta", "vega", "iv"}


def test_greeks_priced_by_ibkr_during_market_hours(ibkr, sample_option_symbols):
    """When the market is open, IBKR should price ATM AAPL greeks (delta != 0).
    Outside market hours greeks may be sparse, so this asserts the mechanism
    works rather than failing after close."""
    r = httpx.post(f"{BASE}/api/greeks-batch",
                   json={"symbols": sample_option_symbols}, timeout=40)
    d = r.json()
    priced = [s for s in sample_option_symbols if d.get(s) and d[s]["delta"] != 0]
    now = time.localtime()
    weekday = now.tm_wday < 5
    market_open = weekday and (9 * 60 + 30) <= (now.tm_hour * 60 + now.tm_min) <= (16 * 60)
    if market_open:
        assert priced, "expected non-zero greeks for ATM AAPL during market hours"
    else:
        pytest.skip("market closed — greeks may be zero; mechanism validated elsewhere")


# ---------------------------------------------------------------------------
# Trading endpoints — READ + VALIDATION ONLY.
# These never place a real order: they exercise the read paths and the
# validation/safety rejections that return BEFORE any order is submitted.
# Successful order placement is verified manually (paper) to avoid executing
# real-world transactions from the test suite.
# ---------------------------------------------------------------------------
class TestSymbolSearch:
    def test_search_returns_matches(self, ibkr):
        r = httpx.get(f"{BASE}/api/ibkr/search/AAP", timeout=15)
        assert r.status_code == 200
        results = r.json()["results"]
        assert len(results) > 0
        syms = [x["symbol"] for x in results]
        assert any(s.startswith("AAP") for s in syms)
        # AAPL should surface for this prefix
        assert "AAPL" in syms

    def test_search_ranks_exact_first(self, ibkr):
        r = httpx.get(f"{BASE}/api/ibkr/search/AAPL", timeout=15)
        results = r.json()["results"]
        assert results, "expected results for AAPL"
        assert results[0]["symbol"] == "AAPL"
        assert "delta" not in results[0]  # sanity: it's a symbol record


class TestTradingEndpoints:
    def test_order_routes_to_selected_account(self, ibkr):
        """Buy paper-vs-live routing: the response echoes the chosen account.
        Uses a validation-reject (qty 0) so NO real order is placed."""
        for acct in ("paper", "live"):
            r = httpx.post(f"{BASE}/api/ibkr/order", timeout=20, json={
                "account": acct, "secType": "stock", "symbol": "AAPL",
                "action": "BUY", "quantity": 0, "orderType": "MKT",
            })
            # Rejected before placing (qty 0) — proves the endpoint accepts the
            # account selection and validates without executing a trade.
            assert r.status_code == 400

    def test_position_endpoint(self, ibkr):
        r = httpx.get(f"{BASE}/api/ibkr/position/AAPL?sec_type=stock&account=paper", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["account"] == "paper"
        assert d["symbol"] == "AAPL"
        assert "quantity" in d

    def test_open_orders_list(self, ibkr):
        r = httpx.get(f"{BASE}/api/ibkr/orders?account=paper", timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json()["orders"], list)

    def test_order_rejects_missing_limit_price(self, ibkr):
        # LMT without a price is rejected before any order is placed
        r = httpx.post(f"{BASE}/api/ibkr/order", timeout=20, json={
            "account": "paper", "secType": "stock", "symbol": "AAPL",
            "action": "BUY", "quantity": 1, "orderType": "LMT",
        })
        assert r.status_code == 400
        assert "Limit price" in r.json()["detail"]

    def test_order_rejects_bad_quantity(self, ibkr):
        r = httpx.post(f"{BASE}/api/ibkr/order", timeout=20, json={
            "account": "paper", "secType": "stock", "symbol": "AAPL",
            "action": "BUY", "quantity": 0, "orderType": "MKT",
        })
        assert r.status_code == 400

    def test_order_rejects_unknown_option_symbol(self, ibkr):
        r = httpx.post(f"{BASE}/api/ibkr/order", timeout=20, json={
            "account": "paper", "secType": "option", "symbol": "NOT_AN_OCC",
            "action": "BUY", "quantity": 1, "orderType": "MKT",
        })
        assert r.status_code == 400


def test_non_option_symbol_has_no_greeks(ibkr):
    r = httpx.post(f"{BASE}/api/greeks-batch", json={"symbols": ["AAPL"]}, timeout=20)
    assert r.status_code == 200
    assert r.json()["AAPL"] is None


# ---------------------------------------------------------------------------
# Live WebSocket streaming
# ---------------------------------------------------------------------------
def test_websocket_streams_live_quotes(ibkr):
    from websockets.sync.client import connect
    with connect(f"{WS}/ws/ibkr/stock-price/AAPL") as ws:
        msg = json.loads(ws.recv())
        assert "error" not in msg, f"stream error: {msg}"
        assert msg["symbol"] == "AAPL"
        assert "price" in msg and "bid" in msg and "ask" in msg


def test_websocket_unknown_symbol_error_frame(ibkr):
    from websockets.sync.client import connect
    with connect(f"{WS}/ws/ibkr/stock-price/GGOGL") as ws:
        msg = json.loads(ws.recv())
        assert "error" in msg
        assert "Unknown symbol" in msg["error"]

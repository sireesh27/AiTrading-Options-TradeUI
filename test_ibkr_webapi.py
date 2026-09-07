"""Smoke test for the headless IBKR Web API (OAuth 1.0a) integration.

Runs the full connection loop against a paper (default) or live account and
exercises the read-only calls the backend depends on. No orders are placed.

    python test_ibkr_webapi.py --account paper
    python test_ibkr_webapi.py --account paper --symbol AAPL

Exit code 0 = connected & data returned; non-zero = a step failed.
"""

import argparse
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

import ibkr_webapi_manager as webapi


async def run(account: str, symbol: str) -> int:
    mgr = (webapi.create_ibkr_webapi_live_manager() if account == "live"
           else webapi.create_ibkr_webapi_paper_manager())

    print(f"\n=== IBKR Web API smoke test ({account}) ===")

    if not mgr.is_configured():
        print("[FAIL] Not configured. Set the IBKR_WEBAPI_"
              f"{account.upper()}_* vars in .env — see IBKR_WEBAPI_SETUP.md.")
        return 2

    print("-> Connecting (OAuth -> Live Session Token -> brokerage session)...")
    if not await mgr.connect():
        print("[FAIL] Could not authenticate. Check credentials and .pem paths.")
        return 3
    print(f"[OK] Connected. Account id: {mgr.account_id}")

    print("-> Fetching portfolio...")
    portfolio = await mgr.get_portfolio_data()
    if portfolio:
        print(f"[OK] Net liq: {portfolio['totalValue']:.2f} | "
              f"Buying power: {portfolio['buyingPower']:.2f} | "
              f"Positions: {len(portfolio['positions'])}")
    else:
        print("[WARN] Portfolio returned no data (new/empty account is OK).")

    print(f"-> Fetching quote for {symbol}...")
    quote = await mgr.get_stock_price(symbol)
    if quote and quote.get("price"):
        print(f"[OK] {symbol}: price={quote['price']} bid={quote['bid']} ask={quote['ask']}")
    else:
        print(f"[WARN] No quote for {symbol} "
              f"(market may be closed or data subscription missing).")

    print(f"-> Symbol search for '{symbol[:3]}'...")
    results = await mgr.search_symbols(symbol[:3])
    print(f"[OK] {len(results)} search results" +
          (f" (e.g. {results[0]['symbol']})" if results else ""))

    mgr.disconnect()
    print("\n[OK] Smoke test complete — Web API is working.\n")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", choices=["paper", "live"], default="paper")
    ap.add_argument("--symbol", default="SPY")
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args.account, args.symbol.upper())))


if __name__ == "__main__":
    main()

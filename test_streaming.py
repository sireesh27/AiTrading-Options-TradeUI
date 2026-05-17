"""
Test Tastytrade DXLink Streaming - Real-time Market Data
=========================================================

This script demonstrates:
1. Authentication with Tastytrade
2. Getting quote token
3. Connecting to DXLink WebSocket
4. Subscribing to symbols (stocks and options)
5. Receiving real-time Quote, Trade, Greeks events
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_streaming():
    """Test real-time streaming from Tastytrade DXLink"""

    print("=" * 70)
    print("TASTYTRADE DXLINK STREAMING TEST")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Step 1: Login and get access token (using same auth as backend)
    print("\n[Step 1] Authenticating with Tastytrade...")

    import main_tastytrade as tasty_bot

    session = tasty_bot.authenticate()
    if not session:
        print("ERROR: Failed to authenticate with Tastytrade")
        print("Make sure TASTY_CLIENT_SECRET and TASTY_REFRESH_TOKEN are set in .env")
        return

    print(f"  Done - Session established")

    # Step 2-5: Connect to DXLink and stream data
    print("\n[Step 2] Connecting to DXLink WebSocket...")

    from tastytrade import DXLinkStreamer
    from tastytrade.dxfeed import Quote, Greeks, Summary

    # Get option symbols for Greeks testing
    print("\n[Step 3] Getting option symbols for Greeks testing...")
    from tastytrade.instruments import NestedOptionChain

    chain = NestedOptionChain.get(session, "SPY")
    if isinstance(chain, list):
        chain = chain[0] if chain else None
    if not chain:
        print("  ERROR: Could not get option chain")
        return
    first_exp = chain.expirations[0]
    exp_date = first_exp.expiration_date

    # Get ATM strikes (around current price ~694)
    atm_strikes = [s for s in first_exp.strikes if 690 <= float(s.strike_price) <= 700]

    # Build option streamer symbols (.SPY260112C694 format)
    option_symbols = []
    for strike in atm_strikes[:3]:  # Get 3 ATM options
        strike_price = float(strike.strike_price)
        date_str = exp_date.strftime("%y%m%d")

        if strike.call:
            # Convert to streamer format: .SPY260112C694
            strike_fmt = str(int(strike_price)) if strike_price == int(strike_price) else f"{strike_price:.2f}".replace(".", "")
            option_symbols.append(f".SPY{date_str}C{strike_fmt}")
        if strike.put:
            strike_fmt = str(int(strike_price)) if strike_price == int(strike_price) else f"{strike_price:.2f}".replace(".", "")
            option_symbols.append(f".SPY{date_str}P{strike_fmt}")

    print(f"  Expiration: {exp_date}")
    print(f"  Option symbols: {len(option_symbols)}")
    for sym in option_symbols[:4]:
        print(f"    - {sym}")
    if len(option_symbols) > 4:
        print(f"    ... and {len(option_symbols) - 4} more")

    # Use DXLinkStreamer as context manager (handles connection/disconnect)
    async with DXLinkStreamer(session) as streamer:
        print("\n  WebSocket connected!")

        # Step 4: Subscribe to stock quotes
        stock_symbols = ["SPY", "AAPL", "TSLA", "NVDA", "QQQ"]
        print(f"\n[Step 4] Subscribing to symbols...")
        print(f"  Stocks: {', '.join(stock_symbols)}")

        await streamer.subscribe(Quote, stock_symbols)
        print(f"  Subscribed to Stock Quote events")

        # Subscribe to option events
        await streamer.subscribe(Quote, option_symbols)
        await streamer.subscribe(Greeks, option_symbols)
        print(f"  Subscribed to Option Quote + Greeks events")

        # Step 5: Listen for real-time data events
        print(f"\n[Step 5] Listening for real-time events (10 seconds)...")
        print("-" * 70)

        quote_count = 0
        greeks_count = 0
        loop = asyncio.get_event_loop()
        start_time = loop.time()
        timeout = 10  # Listen for 10 seconds

        while loop.time() - start_time < timeout:
            try:
                # Check for Quote events
                event = await asyncio.wait_for(streamer.get_event(Quote), timeout=0.1)
                if event:
                    quote_count += 1
                    symbol = getattr(event, 'event_symbol', getattr(event, 'eventSymbol', ''))
                    bid = float(event.bid_price) if event.bid_price else 0
                    ask = float(event.ask_price) if event.ask_price else 0

                    # Only print first few and then every 10th
                    if quote_count <= 5 or quote_count % 20 == 0:
                        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        print(f"[{timestamp}] QUOTE {symbol:20} | Bid: ${bid:>10.2f} | Ask: ${ask:>10.2f}")

            except asyncio.TimeoutError:
                pass

            try:
                # Check for Greeks events
                event = await asyncio.wait_for(streamer.get_event(Greeks), timeout=0.1)
                if event:
                    greeks_count += 1
                    symbol = getattr(event, 'event_symbol', getattr(event, 'eventSymbol', ''))
                    delta = float(event.delta) if event.delta else 0
                    gamma = float(event.gamma) if event.gamma else 0
                    theta = float(event.theta) if event.theta else 0
                    vega = float(event.vega) if event.vega else 0
                    iv = float(event.volatility) if event.volatility else 0  # 'volatility' is the IV field

                    if greeks_count <= 10 or greeks_count % 20 == 0:
                        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        print(f"[{timestamp}] GREEKS {symbol:20} | D={delta:>7.4f} | G={gamma:>7.4f} | T={theta:>8.4f} | V={vega:>7.4f} | IV={iv*100:>6.2f}%")

            except asyncio.TimeoutError:
                pass

    # Summary
    print("-" * 70)
    print("\n[Summary]")
    print(f"  Quote events received: {quote_count}")
    print(f"  Greeks events received: {greeks_count}")
    print(f"  Total events: {quote_count + greeks_count}")
    print(f"  Duration: {timeout} seconds")

    print("\n" + "=" * 70)
    print("STREAMING TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_streaming())

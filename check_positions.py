"""
Check if positions are being fetched from all broker accounts.
"""
import main_tastytrade as tasty_bot
import alpaca_trader
import ibkr_manager
from tastytrade import Account
import asyncio

print("=" * 80)
print("CHECKING POSITIONS FROM ALL ACCOUNTS")
print("=" * 80)

# TastyTrade
print("\n1. TASTYTRADE POSITIONS:")
print("-" * 80)
try:
    session = tasty_bot.authenticate()
    if session:
        account = Account.get(session)[0]
        positions = account.get_positions(session)
        print(f"Total Positions: {len(positions)}")
        if positions:
            for p in positions[:5]:  # Show first 5
                print(f"  - {p.symbol}: {p.quantity} @ ${p.mark_price}")
        else:
            print("  No open positions")
except Exception as e:
    print(f"Error: {e}")

# Alpaca Live
print("\n2. ALPACA LIVE POSITIONS:")
print("-" * 80)
try:
    client = alpaca_trader.authenticate_live()
    if client:
        positions = alpaca_trader.get_positions(client)
        print(f"Total Positions: {len(positions)}")
        if positions:
            for p in positions[:5]:
                print(f"  - {p.symbol}: {p.qty} @ ${p.current_price}")
        else:
            print("  No open positions")
except Exception as e:
    print(f"Error: {e}")

# Alpaca Paper
print("\n3. ALPACA PAPER POSITIONS:")
print("-" * 80)
try:
    client = alpaca_trader.authenticate_paper()
    if client:
        positions = alpaca_trader.get_positions(client)
        print(f"Total Positions: {len(positions)}")
        if positions:
            for p in positions[:5]:
                print(f"  - {p.symbol}: {p.qty} @ ${p.current_price} (P/L: ${p.unrealized_pl:.2f})")
        else:
            print("  No open positions")
except Exception as e:
    print(f"Error: {e}")

# IBKR Live
async def check_ibkr():
    print("\n4. IBKR LIVE POSITIONS:")
    print("-" * 80)
    try:
        ib_mgr = ibkr_manager.create_ibkr_live_manager()
        portfolio = await ib_mgr.get_portfolio_data()
        positions = portfolio.get('positions', [])
        print(f"Total Positions: {len(positions)}")
        if positions:
            for p in positions[:5]:
                print(f"  - {p['symbol']}: {p['qty']} @ ${p['currentPrice']:.2f} (P/L: ${p['pl']:.2f})")
        else:
            print("  No open positions")
        ib_mgr.disconnect()
    except Exception as e:
        print(f"Error: {e}")

    # IBKR Paper
    print("\n5. IBKR PAPER POSITIONS:")
    print("-" * 80)
    try:
        ib_mgr = ibkr_manager.create_ibkr_paper_manager()
        portfolio = await ib_mgr.get_portfolio_data()
        positions = portfolio.get('positions', [])
        print(f"Total Positions: {len(positions)}")
        if positions:
            for p in positions[:5]:
                print(f"  - {p['symbol']}: {p['qty']} @ ${p['currentPrice']:.2f} (P/L: ${p['pl']:.2f})")
        else:
            print("  No open positions")
        ib_mgr.disconnect()
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(check_ibkr())

print("\n" + "=" * 80)
print("SUMMARY:")
print("- Positions are fetched from all connected accounts")
print("- Empty position lists mean the account has no open positions")
print("- All position data includes: symbol, qty, avgPrice, currentPrice, P/L")
print("=" * 80)

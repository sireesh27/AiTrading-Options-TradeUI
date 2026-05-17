"""
Test script to verify all broker connections and functionality.
Run this to check if TastyTrade, Alpaca, and IBKR are working correctly.
"""
import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# Set UTF-8 encoding for Windows console to prevent garbled output
if sys.platform == 'win32':
    import codecs
    try:
        if sys.stdout.encoding.lower() != 'utf-8':
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        if sys.stderr.encoding.lower() != 'utf-8':
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except Exception as e:
        # Fallback if standard streams are already modified or inaccessible
        pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import broker modules
import main_tastytrade as tasty_bot
import alpaca_trader
import ibkr_manager

def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")

def print_status(broker, status, message):
    """Print status with color coding."""
    status_symbol = "[OK]" if status == "SUCCESS" else "[FAIL]"
    print(f"{status_symbol} {broker}: {message}")

def test_tastytrade():
    """Test TastyTrade connection."""
    print_header("Testing TastyTrade Connection")

    try:
        session = tasty_bot.authenticate()
        if session:
            # Try to get account info
            from tastytrade import Account
            accounts = Account.get(session)
            if accounts:
                account = accounts[0]
                print_status("TastyTrade", "SUCCESS", f"Connected - Account: {account.account_number}")

                # Get balances
                try:
                    balances = account.get_balances(session)
                    print(f"   └─ Net Liquidating Value: ${balances.net_liquidating_value:,.2f}")
                    try:
                        print(f"   └─ Buying Power: ${balances.derivative_buying_power:,.2f}")
                    except AttributeError:
                        print(f"   └─ Buying Power: N/A")
                except Exception as e:
                    print(f"   └─ Could not fetch balances: {e}")

                return True
            else:
                print_status("TastyTrade", "FAILED", "No accounts found")
                return False
        else:
            print_status("TastyTrade", "FAILED", "Authentication failed")
            return False
    except Exception as e:
        print_status("TastyTrade", "FAILED", str(e))
        return False

def test_alpaca_live():
    """Test Alpaca Live connection."""
    print_header("Testing Alpaca Live Connection")

    try:
        client = alpaca_trader.authenticate_live()
        if client:
            # Get account info
            account = client.get_account()
            print_status("Alpaca Live", "SUCCESS", f"Connected - Account: {account.account_number}")
            print(f"   └─ Buying Power: ${float(account.buying_power):,.2f}")
            print(f"   └─ Cash: ${float(account.cash):,.2f}")
            print(f"   └─ Portfolio Value: ${float(account.portfolio_value):,.2f}")

            # Get positions
            positions = alpaca_trader.get_positions(client)
            print(f"   └─ Open Positions: {len(positions)}")

            return True
        else:
            print_status("Alpaca Live", "FAILED", "Authentication failed")
            return False
    except Exception as e:
        print_status("Alpaca Live", "FAILED", str(e))
        return False

def test_alpaca_paper():
    """Test Alpaca Paper connection."""
    print_header("Testing Alpaca Paper Connection")

    try:
        client = alpaca_trader.authenticate_paper()
        if client:
            # Get account info
            account = client.get_account()
            print_status("Alpaca Paper", "SUCCESS", f"Connected - Account: {account.account_number}")
            print(f"   └─ Buying Power: ${float(account.buying_power):,.2f}")
            print(f"   └─ Cash: ${float(account.cash):,.2f}")
            print(f"   └─ Portfolio Value: ${float(account.portfolio_value):,.2f}")

            # Get positions
            positions = alpaca_trader.get_positions(client)
            print(f"   └─ Open Positions: {len(positions)}")

            return True
        else:
            print_status("Alpaca Paper", "FAILED", "Authentication failed")
            return False
    except Exception as e:
        print_status("Alpaca Paper", "FAILED", str(e))
        return False

async def test_ibkr_live():
    """Test IBKR Live connection."""
    print_header("Testing IBKR Live Connection")

    try:
        ib_mgr = ibkr_manager.create_ibkr_live_manager()
        connected = await ib_mgr.connect()

        if connected:
            # Get portfolio data
            portfolio = await ib_mgr.get_portfolio_data()
            print_status("IBKR Live", "SUCCESS", "Connected")
            print(f"   └─ Total Value: ${portfolio['totalValue']:,.2f}")
            print(f"   └─ Buying Power: ${portfolio['buyingPower']:,.2f}")
            print(f"   └─ Open Positions: {len(portfolio['positions'])}")

            # Disconnect
            ib_mgr.disconnect()
            return True
        else:
            print_status("IBKR Live", "FAILED", "Connection failed!")
            print("   └─ CRITICIAL: Ensure TWS or IB Gateway is running and logged in.")
            print("   └─ Check TWS Settings: API -> Settings -> 'Enable ActiveX and Socket Clients' must be CHECKED.")
            print("   └─ Check TWS Settings: API -> Settings -> 'Socket Port' must be 7496 for LIVE.")
            print("   └─ Start TWS/IB Gateway or use cloud deployment (see IBKR_CLOUD_DEPLOYMENT.md)")
            return False
    except Exception as e:
        print_status("IBKR Live", "FAILED", str(e))
        return False

async def test_ibkr_paper():
    """Test IBKR Paper connection."""
    print_header("Testing IBKR Paper Connection")

    try:
        ib_mgr = ibkr_manager.create_ibkr_paper_manager()
        connected = await ib_mgr.connect()

        if connected:
            # Get portfolio data
            portfolio = await ib_mgr.get_portfolio_data()
            print_status("IBKR Paper", "SUCCESS", "Connected")
            print(f"   └─ Total Value: ${portfolio['totalValue']:,.2f}")
            print(f"   └─ Buying Power: ${portfolio['buyingPower']:,.2f}")
            print(f"   └─ Open Positions: {len(portfolio['positions'])}")

            # Disconnect
            ib_mgr.disconnect()
            return True
        else:
            print_status("IBKR Paper", "FAILED", "Connection failed!")
            print("   └─ CRITICIAL: Ensure TWS or IB Gateway is running and logged in.")
            print("   └─ Check TWS Settings: API -> Settings -> 'Enable ActiveX and Socket Clients' must be CHECKED.")
            print("   └─ Check TWS Settings: API -> Settings -> 'Socket Port' must be 7497 for PAPER.")
            print("   └─ Start TWS/IB Gateway or use cloud deployment (see IBKR_CLOUD_DEPLOYMENT.md)")
            return False
    except Exception as e:
        print_status("IBKR Paper", "FAILED", str(e))
        return False

def test_stock_quote():
    """Test stock quote retrieval."""
    print_header("Testing Stock Quote (via Alpaca)")

    try:
        quote = alpaca_trader.get_stock_quote("SPY")
        if quote:
            mid_price = (quote.bid_price + quote.ask_price) / 2
            print_status("Stock Quote", "SUCCESS", "Retrieved SPY quote")
            print(f"   └─ SPY Price: ${mid_price:.2f}")
            print(f"   └─ Bid: ${quote.bid_price:.2f}")
            print(f"   └─ Ask: ${quote.ask_price:.2f}")
            return True
        else:
            print_status("Stock Quote", "FAILED", "Could not retrieve quote")
            return False
    except Exception as e:
        print_status("Stock Quote", "FAILED", str(e))
        return False

async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("  BROKER CONNECTION TEST SUITE")
    print("=" * 80)

    results = {}

    # Test each broker
    results['tastytrade'] = test_tastytrade()
    results['alpaca_live'] = test_alpaca_live()
    results['alpaca_paper'] = test_alpaca_paper()
    results['ibkr_live'] = await test_ibkr_live()
    results['ibkr_paper'] = await test_ibkr_paper()
    results['stock_quote'] = test_stock_quote()

    # Print summary
    print_header("Test Summary")

    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)

    for name, status in results.items():
        status_text = "[PASSED]" if status else "[FAILED]"
        print(f"{status_text} - {name.upper()}")

    print(f"\n{'=' * 80}")
    print(f"Total: {passed_tests}/{total_tests} tests passed")
    print(f"{'=' * 80}\n")

    # Print recommendations
    if not all(results.values()):
        print("\n[!] RECOMMENDATIONS:")

        if not results['tastytrade']:
            print("\n>> TastyTrade:")
            print("   - Set up OAuth2 credentials (see GET_TASTYTRADE_REFRESH_TOKEN.md)")
            print("   - Run: python main_tastytrade.py --test-auth")

        if not results['alpaca_live']:
            print("\n>> Alpaca Live:")
            print("   - Check ALPACA_API_KEY and ALPACA_API_SECRET in .env file")
            print("   - Verify credentials are for live account")

        if not results['alpaca_paper']:
            print("\n>> Alpaca Paper:")
            print("   - Check ALPACA_PAPER_API_KEY and ALPACA_PAPER_API_SECRET in .env file")
            print("   - Verify credentials are for paper account")

        if not results['ibkr_live']:
            print("\n>> IBKR Live:")
            print("   - Start TWS or IB Gateway in LIVE mode (port 7496), OR")
            print("   - Deploy to cloud (see IBKR_CLOUD_DEPLOYMENT.md)")
            print("   - Ensure API is enabled in TWS settings")

        if not results['ibkr_paper']:
            print("\n>> IBKR Paper:")
            print("   - Start TWS or IB Gateway in PAPER mode (port 7497), OR")
            print("   - Deploy to cloud (see IBKR_CLOUD_DEPLOYMENT.md)")
            print("   - Ensure API is enabled in TWS settings")

        print("\n>> For detailed setup instructions, see:")
        print("   - TASTYTRADE_OAUTH_SETUP.md")
        print("   - IBKR_CLOUD_DEPLOYMENT.md")
        print("   - README.md")
    else:
        print("\n[SUCCESS] All brokers are connected and working!")
        print("\n>> Next Steps:")
        print("   - Start the backend server: python backend_server.py")
        print("   - Test API endpoint: curl http://localhost:8000/api/positions")
        print("   - Build your frontend or use the API directly")

    return all(results.values())

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[!] Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

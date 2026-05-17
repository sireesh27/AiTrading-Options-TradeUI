"""
Robinhood trading integration using robin-stocks library.
WARNING: This uses an unofficial API which may break at any time.
Robinhood does not officially support API access for stock trading.
"""
import os
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import robin_stocks.robinhood as rh
    import pyotp
    ROBIN_STOCKS_AVAILABLE = True
except ImportError:
    ROBIN_STOCKS_AVAILABLE = False
    logger.warning("robin-stocks library not installed. Run: pip install robin-stocks pyotp")

def authenticate():
    """Authenticates with Robinhood using credentials from environment variables.

    WARNING: This uses an unofficial API. Robinhood may block or change authentication at any time.

    Returns:
        bool: True if authentication successful, None otherwise
    """
    if not ROBIN_STOCKS_AVAILABLE:
        logger.error("robin-stocks library is not installed.")
        logger.error("Install with: pip install robin-stocks pyotp")
        return None

    from pathlib import Path
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)

    username = os.getenv("ROBINHOOD_USERNAME")
    password = os.getenv("ROBINHOOD_PASSWORD")
    totp_secret = os.getenv("ROBINHOOD_TOTP_SECRET")  # 2FA secret key

    if not username or not password:
        logger.error("Please set ROBINHOOD_USERNAME and ROBINHOOD_PASSWORD in your .env file.")
        return None

    try:
        logger.info(f"Authenticating with Robinhood as {username}...")

        # Generate TOTP code if 2FA is enabled
        mfa_code = None
        if totp_secret:
            try:
                totp = pyotp.TOTP(totp_secret)
                mfa_code = totp.now()
                logger.info("Generated 2FA code from TOTP secret")
            except Exception as e:
                logger.error(f"Failed to generate TOTP code: {e}")
                logger.error("Check your ROBINHOOD_TOTP_SECRET in .env file")
                return None

        # Login to Robinhood
        login = rh.login(username, password, mfa_code=mfa_code, store_session=True)

        if login:
            logger.info("Authentication successful!")
            return True
        else:
            logger.error("Authentication failed - invalid response from Robinhood")
            return None

    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        logger.error("\nTroubleshooting:")
        logger.error("1. Verify username/password are correct")
        logger.error("2. Ensure 2FA is set up and TOTP secret is correct")
        logger.error("3. Check if Robinhood has changed their API (this is an unofficial API)")
        logger.error("4. See ROBINHOOD_SETUP.md for detailed instructions")
        return None

def get_account_info():
    """Get Robinhood account information.

    Returns:
        dict: Account information including portfolio value, buying power, etc.
    """
    if not ROBIN_STOCKS_AVAILABLE:
        return None

    try:
        # Get account profile
        profile = rh.profiles.load_account_profile()

        # Get portfolio data
        portfolio = rh.profiles.load_portfolio_profile()

        return {
            "account_number": profile.get('account_number', 'N/A'),
            "buying_power": float(portfolio.get('buying_power', 0)),
            "cash": float(portfolio.get('cash', 0)),
            "portfolio_value": float(portfolio.get('equity', 0)),
            "previous_close": float(portfolio.get('equity_previous_close', 0)),
        }
    except Exception as e:
        logger.error(f"Failed to get account info: {e}")
        return None

def get_positions():
    """Get all current positions from Robinhood.

    Returns:
        list: List of position dictionaries
    """
    if not ROBIN_STOCKS_AVAILABLE:
        return []

    try:
        positions = rh.account.build_holdings()

        result = []
        for symbol, data in positions.items():
            try:
                result.append({
                    "symbol": symbol,
                    "qty": float(data.get('quantity', 0)),
                    "avg_entry_price": float(data.get('average_buy_price', 0)),
                    "current_price": float(data.get('price', 0)),
                    "unrealized_pl": float(data.get('equity', 0)) - (float(data.get('quantity', 0)) * float(data.get('average_buy_price', 0))),
                    "unrealized_plpc": 0.0,  # Calculate if needed
                    "equity": float(data.get('equity', 0)),
                    "percent_change": float(data.get('percent_change', 0)),
                })
            except Exception as e:
                logger.warning(f"Error processing position for {symbol}: {e}")
                continue

        logger.info(f"Current Positions ({len(result)}):")
        for pos in result:
            logger.info(f"  {pos['symbol']}: {pos['qty']} shares @ ${pos['avg_entry_price']:.2f} (P&L: ${pos['unrealized_pl']:.2f})")

        if not result:
            logger.info("No open positions.")

        return result
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        return []

def place_market_order(symbol, qty, side, dry_run=True):
    """Place a market order for stocks.

    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        qty: Quantity of shares
        side: 'buy' or 'sell'
        dry_run: If True, only simulates the order (default: True)

    Returns:
        dict: Order information if successful, None otherwise
    """
    if not ROBIN_STOCKS_AVAILABLE:
        logger.error("robin-stocks library not available")
        return None

    try:
        if dry_run:
            logger.info(f"DRY RUN: Would place {side.upper()} market order for {qty} shares of {symbol}")
            return {"dry_run": True, "symbol": symbol, "qty": qty, "side": side}
        else:
            logger.info(f"Placing {side.upper()} market order for {qty} shares of {symbol}...")

            if side.lower() == 'buy':
                order = rh.orders.order_buy_market(symbol, qty)
            elif side.lower() == 'sell':
                order = rh.orders.order_sell_market(symbol, qty)
            else:
                logger.error(f"Invalid side: {side}. Must be 'buy' or 'sell'")
                return None

            if order:
                logger.info(f"Order placed! Order ID: {order.get('id', 'N/A')}, Status: {order.get('state', 'N/A')}")
                return order
            else:
                logger.error("Order failed - no response from Robinhood")
                return None

    except Exception as e:
        logger.error(f"Failed to place order: {e}")
        return None

def get_stock_quote(symbol):
    """Get the latest quote for a stock symbol.

    Args:
        symbol: Stock symbol (e.g., 'AAPL')

    Returns:
        dict: Quote data with bid, ask, and last price
    """
    if not ROBIN_STOCKS_AVAILABLE:
        return None

    try:
        quote = rh.stocks.get_latest_price(symbol, includeExtendedHours=True)

        if quote and len(quote) > 0:
            price = float(quote[0])

            # Get more detailed quote data
            quote_data = rh.stocks.get_quotes(symbol)
            if quote_data and len(quote_data) > 0:
                data = quote_data[0]
                return {
                    "symbol": symbol,
                    "price": price,
                    "bid_price": float(data.get('bid_price', price)),
                    "ask_price": float(data.get('ask_price', price)),
                    "last_trade_price": float(data.get('last_trade_price', price)),
                }
            else:
                return {
                    "symbol": symbol,
                    "price": price,
                    "bid_price": price,
                    "ask_price": price,
                    "last_trade_price": price,
                }
        else:
            logger.error(f"No quote data for {symbol}")
            return None

    except Exception as e:
        logger.error(f"Failed to get stock quote for {symbol}: {e}")
        return None

def logout():
    """Logout from Robinhood session."""
    if not ROBIN_STOCKS_AVAILABLE:
        return

    try:
        rh.logout()
        logger.info("Logged out from Robinhood")
    except Exception as e:
        logger.error(f"Error during logout: {e}")

def main():
    """Main function for testing Robinhood integration."""
    import argparse

    parser = argparse.ArgumentParser(description="Robinhood Stock Trading Bot")
    parser.add_argument("--test-auth", action="store_true", help="Test authentication")
    parser.add_argument("--positions", action="store_true", help="Show current positions")
    parser.add_argument("--account", action="store_true", help="Show account information")
    parser.add_argument("--quote", type=str, help="Get stock quote (e.g., AAPL)")
    parser.add_argument("--trade", action="store_true", help="Place a trade")
    parser.add_argument("--symbol", type=str, help="Stock symbol (e.g., AAPL)")
    parser.add_argument("--qty", type=int, help="Quantity of shares")
    parser.add_argument("--side", type=str, choices=['buy', 'sell'], help="Buy or Sell")
    parser.add_argument("--live", action="store_true", help="Execute live trade (disable dry run)")

    args = parser.parse_args()

    if args.test_auth:
        auth_result = authenticate()
        if auth_result:
            logger.info("Authentication test completed successfully!")
            logout()
        return

    # Authenticate for other operations
    if not authenticate():
        return

    try:
        if args.account:
            account = get_account_info()
            if account:
                logger.info(f"Account Number: {account['account_number']}")
                logger.info(f"Portfolio Value: ${account['portfolio_value']:,.2f}")
                logger.info(f"Buying Power: ${account['buying_power']:,.2f}")
                logger.info(f"Cash: ${account['cash']:,.2f}")

        if args.positions:
            get_positions()

        if args.quote:
            quote = get_stock_quote(args.quote)
            if quote:
                logger.info(f"{quote['symbol']}: ${quote['price']:.2f}")
                logger.info(f"  Bid: ${quote['bid_price']:.2f}, Ask: ${quote['ask_price']:.2f}")

        if args.trade:
            if not (args.symbol and args.qty and args.side):
                logger.error("Missing arguments for trade. Requires --symbol, --qty, --side")
                return

            place_market_order(args.symbol, args.qty, args.side, dry_run=not args.live)

    finally:
        logout()

if __name__ == "__main__":
    main()

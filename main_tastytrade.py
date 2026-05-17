import os
import argparse
import logging
from dotenv import load_dotenv
from tastytrade import Session, Account, OAuthSession

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def authenticate():
    """Authenticates with the Tastytrade API using credentials from environment variables.

    Supports both OAuth2 (recommended) and legacy username/password authentication.
    OAuth2 credentials take precedence if both are present.
    """
    load_dotenv()

    # Try OAuth2 authentication first (recommended method)
    client_secret = os.getenv("TASTY_CLIENT_SECRET")
    refresh_token = os.getenv("TASTY_REFRESH_TOKEN")
    is_live = os.getenv("TASTY_LIVE", "False").lower() == "true"

    if client_secret and refresh_token:
        try:
            logger.info(f"Authenticating with OAuth2 ({'LIVE' if is_live else 'CERTIFICATION'})...")
            session = OAuthSession(client_secret, refresh_token, is_test=not is_live)
            logger.info("OAuth2 authentication successful!")
            return session
        except Exception as e:
            logger.error(f"OAuth2 authentication failed: {e}")
            logger.info("Falling back to username/password authentication...")

    # Fallback to username/password (deprecated method)
    username = os.getenv("TASTY_USERNAME")
    password = os.getenv("TASTY_PASSWORD")

    if not username or not password:
        logger.error("Please set either:")
        logger.error("  1. TASTY_CLIENT_SECRET and TASTY_REFRESH_TOKEN (OAuth2 - recommended)")
        logger.error("  2. TASTY_USERNAME and TASTY_PASSWORD (deprecated, will be removed Dec 1, 2025)")
        return None

    try:
        logger.warning("Using deprecated username/password authentication.")
        logger.warning("Please migrate to OAuth2 before December 1, 2025!")
        logger.info(f"Authenticating as {username} ({'LIVE' if is_live else 'CERTIFICATION'})...")
        try:
            session = Session(username, password, is_test=not is_live)
        except Exception as e:
            if "invalid_credentials" in str(e) and not is_live:
                logger.warning("Certification auth failed. Trying LIVE environment...")
                session = Session(username, password, is_test=False)
            else:
                raise e

        logger.info("Authentication successful!")
        return session
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        return None

from tastytrade.instruments import NestedOptionChain
from datetime import date

def get_option_chain(session, symbol):
    """Fetches the option chain for a given symbol."""
    try:
        logger.info(f"Fetching option chain for {symbol}...")
        chain = NestedOptionChain.get(session, symbol)
        if isinstance(chain, list):
            if chain:
                chain = chain[0]
            else:
                return None
        return chain
    except Exception as e:
        logger.error(f"Failed to fetch option chain: {e}")
        return None

from tastytrade.order import NewOrder, OrderAction, OrderTimeInForce, OrderType, PriceEffect, Leg
from tastytrade.instruments import Option
from decimal import Decimal

def get_option_symbol(session, symbol, expiration_date, strike, option_type):
    """Finds the OCC symbol for a specific option."""
    try:
        chain = NestedOptionChain.get(session, symbol)
        if isinstance(chain, list):
            if chain:
                chain = chain[0]
            else:
                return None
        for exp in chain.expirations:
            if exp.expiration_date == expiration_date:
                for s in exp.strikes:
                    if s.strike_price == strike:
                        if option_type == 'C' or option_type == 'call':
                            return s.call
                        elif option_type == 'P' or option_type == 'put':
                            return s.put
        return None
    except Exception as e:
        logger.error(f"Failed to find option symbol: {e}")
        return None

def place_order(session, account, symbol, expiration_date, strike, option_type, action, quantity=1, dry_run=True):
    """Places an order for an option."""
    try:
        option_symbol = get_option_symbol(session, symbol, expiration_date, strike, option_type)
        if not option_symbol:
            logger.error("Option not found.")
            return

        leg_action = OrderAction.BUY_TO_OPEN if action == 'buy' else OrderAction.SELL_TO_OPEN
        # Simple logic: Buy -> Buy to Open, Sell -> Sell to Open (for now)
        # A more robust bot would handle closing vs opening.

        leg = Leg(
            instrument_type='Equity Option',
            symbol=option_symbol,
            action=leg_action,
            quantity=quantity
        )

        order = NewOrder(
            time_in_force=OrderTimeInForce.DAY,
            order_type=OrderType.MARKET, # Market order for simplicity in this demo, LIMIT is safer
            legs=[leg],
            price_effect=PriceEffect.DEBIT if action == 'buy' else PriceEffect.CREDIT
        )

        if dry_run:
            logger.info(f"DRY RUN: Would place {action} order for {quantity} {symbol} {expiration_date} {strike} {option_type}")
            logger.info(f"Order details: {order}")
            # In a real dry run with the SDK, we might call a dry_run endpoint if available,
            # but here we just print.
        else:
            logger.info(f"Placing {action} order for {quantity} {symbol} {expiration_date} {strike} {option_type}...")
            response = account.place_order(session, order)
            logger.info(f"Order placed! Response: {response}")

    except Exception as e:
        logger.error(f"Failed to place order: {e}")

def main():
    parser = argparse.ArgumentParser(description="Tastytrade Options Trading Bot")
    parser.add_argument("--test-auth", action="store_true", help="Test authentication")
    parser.add_argument("--chain", type=str, help="Fetch option chain for a symbol (e.g., SPY)")
    parser.add_argument("--trade", action="store_true", help="Trigger a trade (requires other args)")
    parser.add_argument("--symbol", type=str, help="Underlying symbol")
    parser.add_argument("--strike", type=float, help="Strike price")
    parser.add_argument("--expiration", type=str, help="Expiration date (YYYY-MM-DD)")
    parser.add_argument("--type", type=str, choices=['call', 'put'], help="Option type")
    parser.add_argument("--action", type=str, choices=['buy', 'sell'], help="Action")
    parser.add_argument("--quantity", type=int, default=1, help="Quantity")
    parser.add_argument("--live", action="store_true", help="Actually execute the trade (disable dry run)")

    args = parser.parse_args()

    session = authenticate()
    if not session:
        return

    account = Account.get(session)[0] # Use the first account

    if args.test_auth:
        logger.info(f"Using account: {account.account_number}")

    if args.chain:
        chain = get_option_chain(session, args.chain)
        if chain:
            # Print first 5 expirations as a sample
            expirations = sorted(chain.expirations, key=lambda x: x.expiration_date)
            logger.info(f"Found {len(expirations)} expirations for {args.chain}.")
            for exp in expirations[:5]:
                logger.info(f"Expiration: {exp.expiration_date}")

    if args.trade:
        if not (args.symbol and args.strike and args.expiration and args.type and args.action):
            logger.error("Missing arguments for trade. Requires --symbol, --strike, --expiration, --type, --action")
            return

        try:
            exp_date = date.fromisoformat(args.expiration)
            place_order(session, account, args.symbol, exp_date, args.strike, args.type, args.action, args.quantity, dry_run=not args.live)
        except ValueError:
            logger.error("Invalid date format. Use YYYY-MM-DD.")

if __name__ == "__main__":
    main()

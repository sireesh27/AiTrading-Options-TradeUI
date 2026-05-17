import os
import argparse
import logging
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def authenticate(account_type='live'):
    """Authenticates with the Alpaca API using credentials from environment variables.

    Args:
        account_type: 'live' or 'paper' - which account to connect to

    Returns:
        TradingClient or None
    """
    from pathlib import Path
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)

    # Determine which credentials to use
    if account_type == 'paper':
        api_key = os.getenv("ALPACA_PAPER_API_KEY")
        api_secret = os.getenv("ALPACA_PAPER_API_SECRET")
        is_paper = True
    else:  # live
        api_key = os.getenv("ALPACA_API_KEY")
        api_secret = os.getenv("ALPACA_API_SECRET")
        is_paper = os.getenv("ALPACA_PAPER", "false").lower() == "true"

    if not api_key or not api_secret:
        logger.error(f"Please set ALPACA{'_PAPER' if account_type == 'paper' else ''}_API_KEY and ALPACA{'_PAPER' if account_type == 'paper' else ''}_API_SECRET in your .env file.")
        return None

    try:
        logger.info(f"Authenticating with Alpaca {account_type.upper()} ({'PAPER' if is_paper else 'LIVE'})...")
        client = TradingClient(api_key, api_secret, paper=is_paper)
        account = client.get_account()
        logger.info(f"Authentication successful! Account: {account.account_number}")
        logger.info(f"Buying Power: ${account.buying_power}")
        return client
    except Exception as e:
        logger.error(f"Authentication failed for {account_type}: {e}")
        return None

def authenticate_live():
    """Authenticates with Alpaca LIVE account."""
    return authenticate('live')

def authenticate_paper():
    """Authenticates with Alpaca PAPER account."""
    return authenticate('paper')

def place_market_order(client, symbol, qty, side, dry_run=True):
    """Places a market order for stocks."""
    try:
        order_side = OrderSide.BUY if side == 'buy' else OrderSide.SELL

        market_order_data = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.DAY
        )

        if dry_run:
            logger.info(f"DRY RUN: Would place {side.upper()} market order for {qty} shares of {symbol}")
            logger.info(f"Order details: {market_order_data}")
        else:
            logger.info(f"Placing {side.upper()} market order for {qty} shares of {symbol}...")
            order = client.submit_order(order_data=market_order_data)
            logger.info(f"Order placed! Order ID: {order.id}, Status: {order.status}")
            return order

    except Exception as e:
        logger.error(f"Failed to place order: {e}")

def place_limit_order(client, symbol, qty, side, limit_price, dry_run=True):
    """Places a limit order for stocks."""
    try:
        order_side = OrderSide.BUY if side == 'buy' else OrderSide.SELL

        limit_order_data = LimitOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.DAY,
            limit_price=limit_price
        )

        if dry_run:
            logger.info(f"DRY RUN: Would place {side.upper()} limit order for {qty} shares of {symbol} at ${limit_price}")
            logger.info(f"Order details: {limit_order_data}")
        else:
            logger.info(f"Placing {side.upper()} limit order for {qty} shares of {symbol} at ${limit_price}...")
            order = client.submit_order(order_data=limit_order_data)
            logger.info(f"Order placed! Order ID: {order.id}, Status: {order.status}")
            return order

    except Exception as e:
        logger.error(f"Failed to place order: {e}")

def get_positions(client):
    """Gets all current positions."""
    try:
        positions = client.get_all_positions()
        if positions:
            logger.info(f"Current Positions ({len(positions)}):")
            for position in positions:
                logger.info(f"  {position.symbol}: {position.qty} shares @ ${position.avg_entry_price} (P&L: ${position.unrealized_pl})")
        else:
            logger.info("No open positions.")
        return positions
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(description="Alpaca Stock Trading Bot")
    parser.add_argument("--test-auth", action="store_true", help="Test authentication")
    parser.add_argument("--positions", action="store_true", help="Show current positions")
    parser.add_argument("--trade", action="store_true", help="Place a trade")
    parser.add_argument("--symbol", type=str, help="Stock symbol (e.g., AAPL)")
    parser.add_argument("--qty", type=int, help="Quantity of shares")
    parser.add_argument("--side", type=str, choices=['buy', 'sell'], help="Buy or Sell")
    parser.add_argument("--order-type", type=str, choices=['market', 'limit'], default='market', help="Order type")
    parser.add_argument("--limit-price", type=float, help="Limit price (required for limit orders)")
    parser.add_argument("--live", action="store_true", help="Execute live trade (disable dry run)")

    args = parser.parse_args()

    client = authenticate()
    if not client:
        return

    if args.test_auth:
        logger.info("Authentication test completed successfully!")

    if args.positions:
        get_positions(client)

    if args.trade:
        if not (args.symbol and args.qty and args.side):
            logger.error("Missing arguments for trade. Requires --symbol, --qty, --side")
            return

        if args.order_type == 'limit' and not args.limit_price:
            logger.error("Limit orders require --limit-price")
            return

        if args.order_type == 'market':
            place_market_order(client, args.symbol, args.qty, args.side, dry_run=not args.live)
        else:
            place_limit_order(client, args.symbol, args.qty, args.side, args.limit_price, dry_run=not args.live)

def get_option_quote(symbol):
    """Fetches the latest quote for an option symbol from Alpaca."""
    try:
        load_dotenv()
        api_key = os.getenv("ALPACA_API_KEY")
        api_secret = os.getenv("ALPACA_API_SECRET")

        if not api_key or not api_secret:
            logger.error("Alpaca credentials missing for quote fetch")
            return None

        # Import here to avoid circular dependency or unnecessary imports if not used
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionLatestQuoteRequest

        client = OptionHistoricalDataClient(api_key, api_secret)
        request_params = OptionLatestQuoteRequest(symbol_or_symbols=symbol)

        quote = client.get_option_latest_quote(request_params)
        if symbol in quote:
            return quote[symbol]
        return None
    except Exception as e:
        logger.error(f"Failed to fetch Alpaca option quote for {symbol}: {e}")
        return None

def get_option_snapshot(symbol_or_symbols):
    """Fetches the snapshot (including Greeks) for option symbol(s) from Alpaca."""
    try:
        load_dotenv()
        api_key = os.getenv("ALPACA_API_KEY")
        api_secret = os.getenv("ALPACA_API_SECRET")

        if not api_key or not api_secret:
            logger.error("Alpaca credentials missing for snapshot fetch")
            return None

        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionSnapshotRequest

        client = OptionHistoricalDataClient(api_key, api_secret)
        request_params = OptionSnapshotRequest(symbol_or_symbols=symbol_or_symbols)

        snapshot = client.get_option_snapshot(request_params)
        return snapshot
    except Exception as e:
        logger.error(f"Failed to fetch Alpaca option snapshot: {e}")
        return None

def get_stock_quote(symbol):
    """Fetches the latest quote for a stock symbol from Alpaca."""
    try:
        from pathlib import Path
        env_path = (Path(__file__).parent / '.env').resolve()

        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)

        api_key = os.getenv("ALPACA_API_KEY")
        api_secret = os.getenv("ALPACA_API_SECRET")

        if not api_key or not api_secret:
            logger.error("Alpaca credentials missing for stock quote fetch")
            return None

        from alpaca.data.historical.stock import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest
        from alpaca.data.enums import DataFeed

        client = StockHistoricalDataClient(api_key, api_secret)
        request_params = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)

        quote = client.get_stock_latest_quote(request_params)
        if symbol in quote:
            return quote[symbol]
        return None
    except Exception as e:
        logger.error(f"Failed to fetch Alpaca stock quote for {symbol}: {e}")
        return None

if __name__ == "__main__":
    main()

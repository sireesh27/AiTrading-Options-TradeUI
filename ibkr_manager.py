import asyncio
import logging
from ib_async import *

logger = logging.getLogger(__name__)

class IBKRManager:
    def __init__(self, account_type='live'):
        """Initialize IBKR Manager.

        Args:
            account_type: 'live' or 'paper' - which account to connect to
        """
        self.ib = IB()
        self.connected = False
        self.account_type = account_type

        # Set port based on account type
        # Port 7496 = Live Trading
        # Port 7497 = Paper Trading
        self.port = 7496 if account_type == 'live' else 7497

        # Use different clientId for each account type to avoid conflicts
        self.client_id = 1 if account_type == 'live' else 2

        logger.info(f"IBKR Manager initialized for {account_type.upper()} account (port {self.port})")

    async def connect(self):
        if self.ib.isConnected():
            return True

        try:
            logger.info(f"Attempting to connect to IBKR {self.account_type.upper()} on port {self.port}...")
            await self.ib.connectAsync('127.0.0.1', self.port, clientId=self.client_id, timeout=2)
            logger.info(f"Connected to IBKR {self.account_type.upper()} on port {self.port}!")
            self.connected = True

            # Wait a moment for connection to stabilize and data to sync
            await asyncio.sleep(1)
            return True
        except Exception as e:
            logger.warning(f"Could not connect to IBKR {self.account_type.upper()} on port {self.port}: {e}")
            return False

    async def get_portfolio_data(self):
        if not await self.connect():
            logger.error("Failed to connect to IBKR")
            return {
                "totalValue": 0.0,
                "equity": 0.0,
                "buyingPower": 0.0,
                "dayPL": 0.0,
                "dayTrades": "N/A",
                "positions": []
            }

        try:
            # Request portfolio updates
            # ib.portfolio() returns the current state of the portfolio
            portfolio_items = self.ib.portfolio()

            positions = []
            for item in portfolio_items:
                contract = item.contract

                # Calculate PL Percent if possible
                avg_cost = item.averageCost
                market_price = item.marketPrice
                qty = item.position
                pl_percent = 0.0
                if avg_cost > 0:
                    pl_percent = ((market_price - avg_cost) / avg_cost) * 100

                # Use localSymbol for options to get the specific contract (OCC format)
                # If localSymbol is empty, fall back to symbol
                display_symbol = contract.localSymbol if contract.localSymbol else contract.symbol

                positions.append({
                    "symbol": display_symbol,
                    "qty": qty,
                    "avgPrice": avg_cost,
                    "currentPrice": market_price,
                    "value": qty * market_price,
                    "pl": item.unrealizedPNL,
                    "plPercent": pl_percent,
                    "source": "IBKR"
                })

            # Request account summary
            # Use async version to avoid blocking
            account_summary = await self.ib.accountSummaryAsync()

            summary_data = {
                "totalValue": 0.0,
                "equity": 0.0,
                "buyingPower": 0.0,
                "dayPL": 0.0,
                "dayTrades": "N/A", # IBKR doesn't provide day trades count easily in summary
                "positions": positions
            }

            desired_tags = {
                'NetLiquidation': 'totalValue',
                'BuyingPower': 'buyingPower',
                'AvailableFunds': 'buyingPower', # Fallback or alternative
                'UnrealizedPnL': 'unrealizedPL',
                'RealizedPnL': 'realizedPL',
                'DailyPnL': 'dayPL'
            }

            for item in account_summary:
                if item.tag in desired_tags:
                    # Prefer BuyingPower over AvailableFunds if both exist, or handle logic
                    # For now just map
                    if item.tag == 'NetLiquidation':
                        summary_data['totalValue'] = float(item.value)
                        summary_data['equity'] = float(item.value)  # Equity is same as Net Liquidation Value
                    elif item.tag == 'BuyingPower':
                        summary_data['buyingPower'] = float(item.value)
                    elif item.tag == 'DailyPnL':
                        summary_data['dayPL'] = float(item.value)
                    elif item.tag == 'UnrealizedPnL' and summary_data['dayPL'] == 0.0:
                        # Use UnrealizedPnL as fallback if DailyPnL not available
                        summary_data['dayPL'] = float(item.value)

            return summary_data

        except Exception as e:
            logger.error(f"Error fetching IBKR data: {e}")
            self.disconnect()
            return {
                "totalValue": 0.0,
                "equity": 0.0,
                "buyingPower": 0.0,
                "dayPL": 0.0,
                "dayTrades": "N/A",
                "positions": []
            }

    async def get_option_chain(self, symbol: str, expiration: str = None):
        """Fetch option chain data for a given symbol."""
        if not await self.connect():
            logger.error("Failed to connect to IBKR for option chain")
            return None

        try:
            logger.info(f"Starting option chain fetch for {symbol}...")

            # Create stock contract
            stock = Stock(symbol, 'SMART', 'USD')

            # Qualify the contract
            logger.info(f"Qualifying stock contract for {symbol}...")
            await self.ib.qualifyContractsAsync(stock)
            logger.info(f"Qualified stock contract for {symbol}, conId={stock.conId}")

            # Get option parameters (expirations and strikes)
            chains = await self.ib.reqSecDefOptParamsAsync(
                stock.symbol, '', stock.secType, stock.conId
            )

            if not chains:
                logger.error(f"No option chains found for {symbol}")
                return None

            # Get the first chain (usually the main exchange)
            chain = chains[0]
            logger.info(f"Found {len(chain.expirations)} expirations for {symbol}")

            # Select expiration
            target_expiration = None
            if expiration:
                if expiration in chain.expirations:
                    target_expiration = expiration
            else:
                # Get nearest expiration
                sorted_exps = sorted(chain.expirations)
                if sorted_exps:
                    target_expiration = sorted_exps[0]

            if not target_expiration:
                logger.error(f"No valid expiration found")
                return None

            logger.info(f"Using expiration: {target_expiration}")

            # Get strikes around current price (limit to reasonable range)
            strikes = sorted([float(s) for s in chain.strikes])

            # Get stock price to filter strikes
            stock_ticker = await self.ib.reqTickersAsync(stock)
            if stock_ticker and stock_ticker[0].marketPrice():
                current_price = stock_ticker[0].marketPrice()
            else:
                current_price = strikes[len(strikes)//2]  # Use middle strike as fallback

            logger.info(f"Current stock price: {current_price}")

            # Filter strikes within 20% of current price
            min_strike = current_price * 0.8
            max_strike = current_price * 1.2
            filtered_strikes = [s for s in strikes if min_strike <= s <= max_strike]

            # Limit to 20 strikes max
            if len(filtered_strikes) > 20:
                # Get strikes around ATM
                mid_idx = len(filtered_strikes) // 2
                start_idx = max(0, mid_idx - 10)
                end_idx = min(len(filtered_strikes), mid_idx + 10)
                filtered_strikes = filtered_strikes[start_idx:end_idx]

            logger.info(f"Fetching data for {len(filtered_strikes)} strikes")

            # Create option contracts
            option_contracts = []
            for strike in filtered_strikes:
                # Call option
                call = Option(symbol, target_expiration, strike, 'C', 'SMART')
                option_contracts.append(call)

                # Put option
                put = Option(symbol, target_expiration, strike, 'P', 'SMART')
                option_contracts.append(put)

            # Qualify all contracts
            qualified = await self.ib.qualifyContractsAsync(*option_contracts)
            logger.info(f"Qualified {len(qualified)} option contracts")

            # Request market data for all contracts
            tickers = await self.ib.reqTickersAsync(*qualified)
            logger.info(f"Received {len(tickers)} tickers")

            # Build strikes data
            strikes_data = []
            for i in range(0, len(tickers), 2):
                if i + 1 >= len(tickers):
                    break

                call_ticker = tickers[i]
                put_ticker = tickers[i + 1]

                strike = filtered_strikes[i // 2]

                def extract_option_data(ticker):
                    # Helper to safely convert to float
                    def safe_float(val, default=0.0):
                        try:
                            if val is None or (isinstance(val, float) and (val != val or val == float('inf') or val == float('-inf'))):
                                return default
                            return float(val)
                        except (ValueError, TypeError):
                            return default

                    def safe_int(val, default=0):
                        try:
                            if val is None:
                                return default
                            return int(val)
                        except (ValueError, TypeError):
                            return default

                    return {
                        "bid": safe_float(ticker.bid if ticker.bid and ticker.bid > 0 else 0.0),
                        "ask": safe_float(ticker.ask if ticker.ask and ticker.ask > 0 else 0.0),
                        "last": safe_float(ticker.last if ticker.last and ticker.last > 0 else 0.0),
                        "volume": safe_int(ticker.volume),
                        "openInterest": 0,  # IBKR doesn't provide OI in ticker
                        "delta": safe_float(ticker.modelGreeks.delta if ticker.modelGreeks else 0.0),
                        "gamma": safe_float(ticker.modelGreeks.gamma if ticker.modelGreeks else 0.0),
                        "theta": safe_float(ticker.modelGreeks.theta if ticker.modelGreeks else 0.0),
                        "vega": safe_float(ticker.modelGreeks.vega if ticker.modelGreeks else 0.0),
                        "rho": 0.0,  # Not always available
                        "iv": safe_float(ticker.modelGreeks.impliedVol if ticker.modelGreeks else 0.0)
                    }

                strikes_data.append({
                    "strike": float(strike),
                    "call": {
                        "symbol": str(call_ticker.contract.localSymbol),
                        **extract_option_data(call_ticker)
                    },
                    "put": {
                        "symbol": str(put_ticker.contract.localSymbol),
                        **extract_option_data(put_ticker)
                    }
                })

            # Helper to safely convert to float (defined at function level)
            def safe_float(val, default=0.0):
                try:
                    if val is None or (isinstance(val, float) and (val != val or val == float('inf') or val == float('-inf'))):
                        return default
                    result = float(val)
                    # Check for NaN again after conversion
                    if result != result:  # NaN check
                        return default
                    return result
                except (ValueError, TypeError):
                    return default

            return {
                "broker": "ibkr",
                "symbol": symbol,
                "expiration": target_expiration,
                "underlyingPrice": safe_float(current_price),
                "strikes": strikes_data
            }

        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching IBKR option chain for {symbol}")
            return None
        except Exception as e:
            logger.error(f"Error fetching IBKR option chain for {symbol}: {e}", exc_info=True)
            return None

    def disconnect(self):
        if self.ib.isConnected():
            self.ib.disconnect()
            self.connected = False
            logger.info(f"Disconnected from IBKR {self.account_type.upper()}")


def create_ibkr_live_manager():
    """Create IBKR Manager for LIVE account (port 7496)."""
    return IBKRManager(account_type='live')


def create_ibkr_paper_manager():
    """Create IBKR Manager for PAPER account (port 7497)."""
    return IBKRManager(account_type='paper')

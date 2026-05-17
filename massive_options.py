"""
Massive API Integration for Option Greeks
Fetches option chain data and Greeks from Massive API.
"""
import os
import logging
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class MassiveOptionsAPI:
    """Client for Massive Options API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Massive API client.

        Args:
            api_key: Massive API key. If not provided, reads from MASSIVE_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("MASSIVE_API_KEY")
        if not self.api_key:
            logger.warning("MASSIVE_API_KEY not found in environment variables")

        self.base_url = "https://api.massive.com/v3"

    def get_option_greeks(self, underlying: str, option_symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get option Greeks and snapshot data for a specific option contract.

        Args:
            underlying: Underlying symbol (e.g., 'SPY')
            option_symbol: Option contract symbol (e.g., 'O:SPY251219C00650000')

        Returns:
            Dictionary containing option data including Greeks, or None if error

        Example:
            >>> api = MassiveOptionsAPI()
            >>> data = api.get_option_greeks('SPY', 'O:SPY251219C00650000')
            >>> if data:
            ...     print(f"Delta: {data['greeks']['delta']}")
            ...     print(f"Gamma: {data['greeks']['gamma']}")
        """
        if not self.api_key:
            logger.error("API key not configured")
            return None

        url = f"{self.base_url}/snapshot/options/{underlying}/{option_symbol}"
        params = {"apiKey": self.api_key}

        try:
            logger.info(f"Fetching option Greeks for {option_symbol}")
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Successfully fetched Greeks for {option_symbol}")
            return data

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error fetching option Greeks: {e}")
            logger.error(f"Response: {e.response.text if e.response else 'No response'}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching option Greeks: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching option Greeks: {e}")
            return None

    def parse_greeks(self, data: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """
        Parse Greeks from API response.

        Args:
            data: Raw API response

        Returns:
            Dictionary containing parsed Greeks
        """
        try:
            # Greeks are nested under 'results' key in Massive API response
            results = data.get('results', {})
            greeks = results.get('greeks', {})
            implied_vol = results.get('implied_volatility', 0.0)

            return {
                'delta': float(greeks.get('delta', 0.0)),
                'gamma': float(greeks.get('gamma', 0.0)),
                'theta': float(greeks.get('theta', 0.0)),
                'vega': float(greeks.get('vega', 0.0)),
                'rho': float(greeks.get('rho', 0.0)),
                'iv': float(implied_vol)
            }
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error parsing Greeks: {e}")
            return None

    def parse_quote(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse option quote from API response.

        Args:
            data: Raw API response

        Returns:
            Dictionary containing quote data
        """
        try:
            # Quote data is nested under 'results' key in Massive API response
            results = data.get('results', {})
            day = results.get('day', {})
            last_trade = results.get('last_trade', {})

            return {
                'bid': 0.0,  # Massive API doesn't provide real-time bid/ask
                'ask': 0.0,
                'last': float(last_trade.get('price', 0.0)),
                'bidSize': 0,
                'askSize': 0,
                'volume': int(day.get('volume', 0)),
                'openInterest': int(results.get('open_interest', 0))
            }
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error parsing quote: {e}")
            return None

    def get_option_chain(self, underlying: str, expiration: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get full option chain for an underlying symbol.

        Args:
            underlying: Underlying symbol (e.g., 'SPY')
            expiration: Optional expiration date filter (e.g., '2024-12-19')

        Returns:
            Dictionary containing option chain data
        """
        if not self.api_key:
            logger.error("API key not configured")
            return None

        url = f"{self.base_url}/snapshot/options/{underlying}"
        params = {"apiKey": self.api_key}

        if expiration:
            params['expiration'] = expiration

        try:
            logger.info(f"Fetching option chain for {underlying}")
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Successfully fetched option chain for {underlying}")
            return data

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error fetching option chain: {e}")
            logger.error(f"Response: {e.response.text if e.response else 'No response'}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching option chain: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching option chain: {e}")
            return None


def format_option_symbol(underlying: str, expiration: str, strike: float, option_type: str) -> str:
    """
    Format option symbol in Massive API format.

    Args:
        underlying: Underlying symbol (e.g., 'SPY')
        expiration: Expiration date in YYMMDD format (e.g., '251219' for Dec 19, 2025)
        strike: Strike price (e.g., 650.0)
        option_type: 'C' for call, 'P' for put

    Returns:
        Formatted option symbol (e.g., 'O:SPY251219C00650000')

    Example:
        >>> format_option_symbol('SPY', '251219', 650.0, 'C')
        'O:SPY251219C00650000'
    """
    # Format strike price with 5 digits before decimal and 3 after
    strike_str = f"{int(strike):05d}{int((strike % 1) * 1000):03d}"
    return f"O:{underlying}{expiration}{option_type}{strike_str}"


def main():
    """Main function for testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Massive Options API - Fetch Option Greeks")
    parser.add_argument("--underlying", type=str, default="SPY", help="Underlying symbol")
    parser.add_argument("--option", type=str, help="Option symbol (e.g., O:SPY251219C00650000)")
    parser.add_argument("--expiration", type=str, help="Expiration in YYMMDD format (e.g., 251219)")
    parser.add_argument("--strike", type=float, help="Strike price (e.g., 650.0)")
    parser.add_argument("--type", type=str, choices=['C', 'P'], help="Option type: C for call, P for put")
    parser.add_argument("--chain", action="store_true", help="Get full option chain")

    args = parser.parse_args()

    api = MassiveOptionsAPI()

    if args.chain:
        # Fetch full option chain
        print(f"\n{'=' * 80}")
        print(f"Fetching option chain for {args.underlying}")
        print('=' * 80)

        data = api.get_option_chain(args.underlying)
        if data:
            print(f"\nOption chain data retrieved successfully!")
            print(f"Data keys: {list(data.keys())}")
        else:
            print("\nFailed to fetch option chain")

    else:
        # Fetch specific option Greeks
        if args.option:
            option_symbol = args.option
        elif args.expiration and args.strike and args.type:
            option_symbol = format_option_symbol(args.underlying, args.expiration, args.strike, args.type)
        else:
            # Default example
            option_symbol = "O:SPY251219C00650000"

        print(f"\n{'=' * 80}")
        print(f"Fetching Greeks for {option_symbol}")
        print('=' * 80)

        data = api.get_option_greeks(args.underlying, option_symbol)

        if data:
            print(f"\n[SUCCESS] Option data retrieved!")
            print(f"\nOption: {option_symbol}")

            # Parse and display Greeks
            greeks = api.parse_greeks(data)
            if greeks:
                print(f"\nGreeks:")
                print(f"  Delta: {greeks['delta']:.4f}")
                print(f"  Gamma: {greeks['gamma']:.4f}")
                print(f"  Theta: {greeks['theta']:.4f}")
                print(f"  Vega: {greeks['vega']:.4f}")
                print(f"  Rho: {greeks['rho']:.4f}")
                print(f"  IV: {greeks['iv']:.2%}")

            # Parse and display quote
            quote = api.parse_quote(data)
            if quote:
                print(f"\nQuote:")
                print(f"  Bid: ${quote['bid']:.2f} x {quote['bidSize']}")
                print(f"  Ask: ${quote['ask']:.2f} x {quote['askSize']}")
                print(f"  Last: ${quote['last']:.2f}")
                print(f"  Volume: {quote['volume']:,}")
                print(f"  Open Interest: {quote['openInterest']:,}")
        else:
            print("\n[FAILED] Could not fetch option data")
            print("\nTroubleshooting:")
            print("1. Check if MASSIVE_API_KEY is set in .env file")
            print("2. Verify the API key is valid")
            print("3. Ensure the option symbol is correct")

    print(f"\n{'=' * 80}\n")


if __name__ == "__main__":
    main()

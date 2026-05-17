"""
Test script to compare data from Massive API and Tastytrade.
Run this after starting the backend server.
"""

import requests
import json
from datetime import datetime

API_BASE = "http://localhost:8000"

def test_tastytrade_connection():
    """Test Tastytrade authentication and real-time data access."""
    print("\n" + "="*60)
    print("TASTYTRADE CONNECTION TEST")
    print("="*60)

    try:
        response = requests.get(f"{API_BASE}/api/tastytrade/test", timeout=30)
        data = response.json()

        print(f"\nAuthenticated: {data.get('authenticated', False)}")
        print(f"Account Number: {data.get('account_number', 'N/A')}")
        print(f"Account Type: {data.get('account_type', 'N/A')}")
        print(f"Is Funded: {data.get('is_funded', 'Unknown')}")
        print(f"Quote Type: {data.get('quote_type', 'N/A')}")

        if data.get('sample_quote'):
            q = data['sample_quote']
            print(f"\nSample Quote (SPY):")
            print(f"  Price: ${q.get('price', 0):.2f}")
            print(f"  Bid: ${q.get('bid', 0):.2f}")
            print(f"  Ask: ${q.get('ask', 0):.2f}")
            print(f"  Timestamp: {q.get('timestamp', 'N/A')}")

        if data.get('errors'):
            print(f"\nErrors:")
            for err in data['errors']:
                print(f"  - {err}")

        return data.get('authenticated', False)

    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to backend. Is the server running?")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def compare_data_sources(symbol: str):
    """Compare stock and options data between Massive and Tastytrade."""
    print("\n" + "="*60)
    print(f"DATA COMPARISON: {symbol}")
    print("="*60)

    try:
        response = requests.get(f"{API_BASE}/api/compare/{symbol}", timeout=60)
        data = response.json()

        # Stock Comparison
        print("\n--- STOCK QUOTE COMPARISON ---")
        stock = data.get('stock_comparison', {})

        massive = stock.get('massive')
        tasty = stock.get('tastytrade')
        diff = stock.get('difference')

        print(f"\n{'Source':<15} {'Price':>12} {'Bid':>12} {'Ask':>12} {'Spread':>10}")
        print("-" * 65)

        if massive:
            print(f"{'Massive API':<15} ${massive['price']:>10.2f} ${massive['bid']:>10.2f} ${massive['ask']:>10.2f} ${massive['spread']:>8.4f}")
        else:
            print(f"{'Massive API':<15} {'N/A':>12} {'N/A':>12} {'N/A':>12} {'N/A':>10}")

        if tasty:
            print(f"{'Tastytrade':<15} ${tasty['price']:>10.2f} ${tasty['bid']:>10.2f} ${tasty['ask']:>10.2f} ${tasty['spread']:>8.4f}")
        else:
            print(f"{'Tastytrade':<15} {'N/A':>12} {'N/A':>12} {'N/A':>12} {'N/A':>10}")

        if diff:
            print(f"\nPrice Difference: ${diff['price_diff']:.4f} ({diff['price_diff_pct']:.4f}%)")
            print(f"Match (within $0.10): {'YES' if diff['match'] else 'NO'}")

        # Options Comparison
        print("\n--- OPTIONS CHAIN COMPARISON ---")
        opts = data.get('options_comparison', {})

        massive_opts = opts.get('massive')
        tasty_opts = opts.get('tastytrade')

        print(f"\n{'Source':<15} {'Expirations':>15} {'First Exp':>15}")
        print("-" * 50)

        if massive_opts:
            print(f"{'Massive API':<15} {massive_opts['expirations_count']:>15} {massive_opts['first_expiration'] or 'N/A':>15}")
        else:
            print(f"{'Massive API':<15} {'N/A':>15} {'N/A':>15}")

        if tasty_opts:
            print(f"{'Tastytrade':<15} {tasty_opts['expirations_count']:>15} {tasty_opts['first_expiration'] or 'N/A':>15}")
        else:
            print(f"{'Tastytrade':<15} {'N/A':>15} {'N/A':>15}")

        # Sample Strikes with Greeks (from Tastytrade)
        sample_strikes = opts.get('sample_strikes', [])
        if sample_strikes:
            print("\n--- SAMPLE OPTION GREEKS (Tastytrade) ---")
            print(f"Expiration: {tasty_opts['first_expiration'] if tasty_opts else 'N/A'}")

            for strike_data in sample_strikes:
                strike = strike_data['strike']
                print(f"\nStrike: ${strike:.2f}")

                call = strike_data.get('call')
                put = strike_data.get('put')

                print(f"  {'Type':<6} {'Bid':>8} {'Ask':>8} {'Delta':>8} {'Gamma':>8} {'Theta':>8} {'Vega':>8} {'IV':>8}")
                print("  " + "-" * 70)

                if call:
                    print(f"  {'CALL':<6} ${call['bid']:>6.2f} ${call['ask']:>6.2f} {call['delta']:>8.4f} {call['gamma']:>8.4f} {call['theta']:>8.4f} {call['vega']:>8.4f} {call['iv']*100:>7.2f}%")
                else:
                    print(f"  {'CALL':<6} {'N/A':>8} {'N/A':>8} {'N/A':>8} {'N/A':>8} {'N/A':>8} {'N/A':>8} {'N/A':>8}")

                if put:
                    print(f"  {'PUT':<6} ${put['bid']:>6.2f} ${put['ask']:>6.2f} {put['delta']:>8.4f} {put['gamma']:>8.4f} {put['theta']:>8.4f} {put['vega']:>8.4f} {put['iv']*100:>7.2f}%")
                else:
                    print(f"  {'PUT':<6} {'N/A':>8} {'N/A':>8} {'N/A':>8} {'N/A':>8} {'N/A':>8} {'N/A':>8} {'N/A':>8}")

        # Errors
        if data.get('errors'):
            print("\n--- ERRORS ---")
            for err in data['errors']:
                print(f"  - {err}")

        return data

    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to backend. Is the server running?")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def main():
    print("\n" + "="*60)
    print("DATA SOURCE COMPARISON TEST")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # Test Tastytrade connection first
    connected = test_tastytrade_connection()

    if not connected:
        print("\nWARNING: Tastytrade not connected. Comparison may be incomplete.")

    # Compare multiple symbols
    symbols = ["SPY", "AAPL", "TSLA"]

    for symbol in symbols:
        compare_data_sources(symbol)

    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()

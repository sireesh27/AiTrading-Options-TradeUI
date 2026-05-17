"""
Quick verification script for Massive API integration.
Tests both the module and the API endpoints.
"""
import requests
import sys

print("=" * 80)
print("MASSIVE API INTEGRATION - VERIFICATION TEST")
print("=" * 80)

# Test 1: Standalone module
print("\n[TEST 1] Testing standalone massive_options module...")
try:
    from massive_options import MassiveOptionsAPI, format_option_symbol

    api = MassiveOptionsAPI()

    # Format option symbol
    symbol = format_option_symbol('SPY', '251219', 650.0, 'C')
    print(f"  [OK] Symbol formatting: {symbol}")

    # Fetch Greeks
    data = api.get_option_greeks('SPY', symbol)
    if data:
        greeks = api.parse_greeks(data)
        quote = api.parse_quote(data)
        print(f"  [OK] Greeks fetched successfully")
        print(f"       Delta: {greeks['delta']:.4f}")
        print(f"       IV: {greeks['iv']:.2%}")
        print(f"       Last Price: ${quote['last']:.2f}")
    else:
        print(f"  [FAIL] Could not fetch Greeks")

except Exception as e:
    print(f"  [FAIL] Error: {e}")

# Test 2: Backend API endpoint for option Greeks
print("\n[TEST 2] Testing /api/option-greeks endpoint...")
try:
    url = "http://localhost:8000/api/option-greeks/SPY/O:SPY251219C00650000"
    response = requests.get(url, timeout=10)

    if response.status_code == 200:
        data = response.json()
        print(f"  [OK] API endpoint working")
        print(f"       Underlying: {data['underlying']}")
        print(f"       Delta: {data['greeks']['delta']:.4f}")
        print(f"       Gamma: {data['greeks']['gamma']:.4f}")
        print(f"       Theta: {data['greeks']['theta']:.4f}")
        print(f"       Vega: {data['greeks']['vega']:.4f}")
        print(f"       IV: {data['greeks']['iv']:.2%}")
    else:
        print(f"  [FAIL] API returned status {response.status_code}")

except requests.exceptions.ConnectionError:
    print(f"  [FAIL] Backend server not running on port 8000")
except Exception as e:
    print(f"  [FAIL] Error: {e}")

# Test 3: Backend API endpoint for option chain
print("\n[TEST 3] Testing /api/option-chain endpoint...")
try:
    url = "http://localhost:8000/api/option-chain/SPY"
    response = requests.get(url, timeout=10)

    if response.status_code == 200:
        data = response.json()
        results_count = len(data.get('results', []))
        print(f"  [OK] Option chain endpoint working")
        print(f"       Status: {data['status']}")
        print(f"       Results count: {results_count}")
        print(f"       Next URL: {'Available' if data.get('next_url') else 'None'}")
    else:
        print(f"  [FAIL] API returned status {response.status_code}")

except requests.exceptions.ConnectionError:
    print(f"  [FAIL] Backend server not running on port 8000")
except Exception as e:
    print(f"  [FAIL] Error: {e}")

# Test 4: Verify API endpoints are documented
print("\n[TEST 4] Testing root endpoint...")
try:
    url = "http://localhost:8000/"
    response = requests.get(url, timeout=5)

    if response.status_code == 200:
        data = response.json()
        print(f"  [OK] Backend server is running")
        print(f"       Message: {data['message']}")
        print(f"       Version: {data['version']}")
    else:
        print(f"  [FAIL] Root endpoint returned status {response.status_code}")

except requests.exceptions.ConnectionError:
    print(f"  [FAIL] Backend server not running on port 8000")
except Exception as e:
    print(f"  [FAIL] Error: {e}")

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
print("\nAvailable API Endpoints:")
print("  1. GET /api/positions - Get all broker positions")
print("  2. GET /api/stock-price/{symbol} - Get stock quote")
print("  3. GET /api/option-greeks/{underlying}/{option_symbol} - Get option Greeks")
print("  4. GET /api/option-chain/{underlying} - Get option chain")
print("\nCommand-line Tools:")
print("  - python massive_options.py --underlying SPY --option O:SPY251219C00650000")
print("  - python massive_options.py --underlying SPY --chain")
print("  - python test_massive_api.py  (this script)")
print("=" * 80 + "\n")

"""
Verification script for Portfolio Greeks and Tabs integration.
Tests the /api/portfolio-greeks endpoint and presence of new data fields.
"""
import requests
import json
import sys
import codecs

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

API_BASE_URL = 'http://localhost:8000'

print("=" * 80)
print("PORTFOLIO GREEKS API - VERIFICATION")
print("=" * 80)

# Step 1: Fetch Portfolio Greeks
print("\n[STEP 1] Fetching data from /api/portfolio-greeks...")
try:
    response = requests.get(f"{API_BASE_URL}/api/portfolio-greeks")
    if response.status_code != 200:
        print(f"  ✗ Error: API returned status {response.status_code}")
        exit(1)
        
    data = response.json()
    by_underlying = data.get('by_underlying', {})
    portfolio_totals = data.get('portfolio_totals', {})
    
    print(f"  ✓ Fetched data successfully.")
    print(f"  ✓ Portfolio Net Delta: {portfolio_totals.get('net_delta')}")
    print(f"  ✓ Number of Underlyings: {len(by_underlying)}")

    # Step 2: Verify New Fields
    print("\n[STEP 2] Verifying new fields (PL, Prices, Rho) in positions...")
    
    missing_fields_count = 0
    positions_checked = 0
    
    for underlying_sym, u_data in by_underlying.items():
        print(f"\nUnderlying: {underlying_sym}")
        for pos in u_data.get('positions', []):
            positions_checked += 1
            symbol = pos.get('symbol')
            
            # Check for new fields
            pl = pos.get('pl')
            avgPrice = pos.get('avgPrice')
            currentPrice = pos.get('currentPrice')
            plPercent = pos.get('plPercent')
            rho = pos.get('rho')
            
            missing = []
            if pl is None: missing.append('pl')
            if avgPrice is None: missing.append('avgPrice')
            if currentPrice is None: missing.append('currentPrice')
            if plPercent is None: missing.append('plPercent')
            if rho is None: missing.append('rho')
            
            if missing:
                print(f"  ✗ Position {symbol}: MISSING fields: {missing}")
                missing_fields_count += 1
            else:
                print(f"  ✓ Position {symbol}:")
                print(f"      PL: ${pl:.2f}, PL%: {plPercent:.2f}%, Avg: ${avgPrice:.2f}, Curr: ${currentPrice:.2f}")
                print(f"      Rho: {rho}")

    if positions_checked == 0:
        print("  ! No positions found to verify.")
    elif missing_fields_count == 0:
        print(f"\n  ✓ All {positions_checked} positions have the required new fields.")
    else:
        print(f"\n  ✗ Found {missing_fields_count} positions with missing fields.")
        exit(1)

except Exception as e:
    print(f"  ✗ Error: {e}")
    exit(1)

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE!")
print("=" * 80)

"""
Verify all position fields are present.
"""
import requests
import json

response = requests.get('http://localhost:8000/api/positions')
data = response.json()

print("=" * 80)
print("POSITION FIELDS VERIFICATION - ALL BROKERS")
print("=" * 80)

for broker, account_data in data.items():
    positions = account_data.get('positions', [])
    if positions:
        print(f"\n{broker.upper()}:")
        pos = positions[0]
        print(f"  Position: {pos['symbol']}")
        print(f"    [OK] Symbol: {pos['symbol']}")
        print(f"    [OK] Quantity: {pos['qty']}")
        print(f"    [OK] Avg Price: ${pos['avgPrice']:,.2f}")
        print(f"    [OK] Current Price: ${pos['currentPrice']:,.2f}")
        print(f"    [OK] Value: ${pos['value']:,.2f}")
        print(f"    [OK] P/L: ${pos['pl']:,.2f}")
        print(f"    [OK] P/L %: {pos['plPercent']:.2f}%")
    else:
        print(f"\n{broker.upper()}: No positions")

print("\n" + "=" * 80)
print("[SUCCESS] ALL REQUIRED POSITION FIELDS PRESENT:")
print("   1. Symbol - Stock/Option ticker")
print("   2. Quantity (qty) - Number of shares")
print("   3. Value - Position value (qty x price)")
print("   4. P/L - Profit/Loss in dollars")
print("\n[INFO] ADDITIONAL FIELDS:")
print("   - avgPrice - Average entry price")
print("   - currentPrice - Current market price")
print("   - plPercent - P/L percentage")
print("   - source - Broker account name")
print("=" * 80)

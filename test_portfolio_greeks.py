"""
Portfolio Greeks Test Script
Demonstrates the complete Portfolio Greeks feature with stock + option Greeks aggregation.
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

print("=" * 100)
print("PORTFOLIO GREEKS - COMPLETE ANALYSIS")
print("=" * 100)

# Fetch Portfolio Greeks
print("\n[FETCHING DATA] Getting portfolio Greeks from all accounts...")
try:
    response = requests.get(f"{API_BASE_URL}/api/portfolio-greeks")
    if response.status_code != 200:
        print(f"❌ Error: API returned status {response.status_code}")
        exit(1)

    data = response.json()
    totals = data['portfolio_totals']
    by_underlying = data['by_underlying']

    print("✅ Data retrieved successfully!\n")

except Exception as e:
    print(f"❌ Error fetching data: {e}")
    exit(1)

# Display Portfolio Totals
print("=" * 100)
print("PORTFOLIO SUMMARY")
print("=" * 100)
print(f"\n{'Metric':<30} {'Value':>20} {'Interpretation':<50}")
print("-" * 100)

print(f"{'Total Positions':<30} {totals['total_positions']:>20} {'All positions across all brokers':<50}")
print(f"{'Number of Underlyings':<30} {totals['num_underlyings']:>20} {'Unique stocks/ETFs traded':<50}")
print(f"{'Total Portfolio Value':<30} ${totals['total_value']:>19,.2f} {'Combined value of all positions':<50}")

print("\n" + "=" * 100)
print("PORTFOLIO GREEKS")
print("=" * 100)
print(f"\n{'Greek':<30} {'Value':>20} {'Meaning':<50}")
print("-" * 100)

# Net Delta
delta_interp = "Portfolio is BULLISH" if totals['net_delta'] > 0 else "Portfolio is BEARISH" if totals['net_delta'] < 0 else "Portfolio is NEUTRAL"
delta_move = f"${abs(totals['net_delta']):.2f} per $1 move in market"
print(f"{'Net Delta':<30} {totals['net_delta']:>20.2f} {delta_interp + ' - ' + delta_move:<50}")

# Net Theta
theta_sign = '+' if totals['net_theta'] >= 0 else '-'
theta_interp = "GAINING from time decay ✓" if totals['net_theta'] > 0 else "LOSING to time decay ✗"
print(f"{'Net Theta (per day)':<30} {theta_sign}${abs(totals['net_theta']):>18.2f} {theta_interp:<50}")

# Net Gamma
gamma_interp = "Delta increases as market moves" if totals['net_gamma'] > 0 else "Delta decreases as market moves"
print(f"{'Net Gamma':<30} {totals['net_gamma']:>20.4f} {gamma_interp:<50}")

# Net Vega
vega_interp = "Profit from rising IV" if totals['net_vega'] > 0 else "Profit from falling IV"
print(f"{'Net Vega':<30} {totals['net_vega']:>20.2f} {vega_interp:<50}")

# Additional Metrics
print("\n" + "-" * 100)
print("RISK METRICS")
print("-" * 100)
delta_per_1k = (totals['net_delta'] / totals['total_value']) * 1000 if totals['total_value'] > 0 else 0
print(f"{'Delta per $1000 invested':<30} {delta_per_1k:>20.2f} {'Directional exposure normalized':<50}")

yearly_theta = totals['net_theta'] * 365
print(f"{'Annualized Theta (if held)':<30} ${yearly_theta:>19.2f} {'Time decay over a year (unrealistic)':<50}")

# By Underlying Breakdown
print("\n" + "=" * 100)
print("GREEKS BY UNDERLYING")
print("=" * 100)

# Sort by absolute delta
sorted_underlyings = sorted(by_underlying.items(), key=lambda x: abs(x[1]['net_delta']), reverse=True)

print(f"\n{'Symbol':<10} {'Pos':>4} {'Value':>12} {'Net Delta':>12} {'Net Theta':>12} {'Net Gamma':>12} {'Net Vega':>12}")
print("-" * 100)

for symbol, underlying_data in sorted_underlyings:
    num_pos = len(underlying_data['positions'])
    value = underlying_data['total_value']
    delta = underlying_data['net_delta']
    theta = underlying_data['net_theta']
    gamma = underlying_data['net_gamma']
    vega = underlying_data['net_vega']

    print(f"{symbol:<10} {num_pos:>4} ${value:>11,.2f} "
          f"{delta:>12.2f} "
          f"{theta:>12.2f} "
          f"{gamma:>12.4f} "
          f"{vega:>12.2f}")

# Detailed breakdown for each underlying
print("\n" + "=" * 100)
print("DETAILED POSITION BREAKDOWN")
print("=" * 100)

for symbol, underlying_data in sorted_underlyings:
    print(f"\n{'─' * 100}")
    print(f"📊 {symbol} - {len(underlying_data['positions'])} Position(s)")
    print(f"{'─' * 100}")

    # Summary for this underlying
    print(f"\nSummary:")
    print(f"  Total Value: ${underlying_data['total_value']:,.2f}")
    print(f"  Net Delta:   {underlying_data['net_delta']:>8.2f}  ({'Bullish' if underlying_data['net_delta'] > 0 else 'Bearish' if underlying_data['net_delta'] < 0 else 'Neutral'})")
    print(f"  Net Theta:   {underlying_data['net_theta']:>8.2f}  ({'Positive decay' if underlying_data['net_theta'] > 0 else 'Negative decay'})")

    print(f"\nPositions:")
    print(f"  {'Symbol':<25} {'Type':<8} {'Qty':>8} {'Delta':>10} {'Δ Exp':>10} {'Theta':>10} {'IV':>8}")
    print(f"  {'-' * 95}")

    for pos in underlying_data['positions']:
        pos_type = pos['type'].upper()
        qty = pos['qty']
        delta = pos['delta']
        delta_exp = pos['delta_exposure']
        theta = pos['theta']
        iv = pos['iv']

        print(f"  {pos['symbol']:<25} {pos_type:<8} {qty:>8.2f} "
              f"{delta:>10.4f} {delta_exp:>10.2f} "
              f"{theta:>10.4f} {iv*100:>7.2f}%")

# Risk Analysis
print("\n" + "=" * 100)
print("RISK ANALYSIS & RECOMMENDATIONS")
print("=" * 100)

print("\n📈 DIRECTIONAL RISK:")
if totals['net_delta'] > 100:
    print(f"   ⚠️  STRONG BULLISH BIAS (+{totals['net_delta']:.2f} delta)")
    print(f"       Your portfolio will gain ${totals['net_delta']:.2f} for every $1 the market goes UP")
    print(f"       Your portfolio will lose ${totals['net_delta']:.2f} for every $1 the market goes DOWN")
elif totals['net_delta'] > 20:
    print(f"   ✓  Moderate bullish bias (+{totals['net_delta']:.2f} delta)")
elif totals['net_delta'] < -100:
    print(f"   ⚠️  STRONG BEARISH BIAS ({totals['net_delta']:.2f} delta)")
    print(f"       Your portfolio will gain ${abs(totals['net_delta']):.2f} for every $1 the market goes DOWN")
elif totals['net_delta'] < -20:
    print(f"   ✓  Moderate bearish bias ({totals['net_delta']:.2f} delta)")
else:
    print(f"   ✓  Well-balanced portfolio ({totals['net_delta']:.2f} delta)")

print("\n⏰ TIME DECAY RISK:")
if totals['net_theta'] > 10:
    print(f"   ✓  EXCELLENT - You're net SHORT options (+${totals['net_theta']:.2f}/day)")
    print(f"       Time works FOR you. You collect ${totals['net_theta']:.2f} every day.")
    print(f"       Estimated monthly income from theta: ${totals['net_theta'] * 30:.2f}")
elif totals['net_theta'] > 0:
    print(f"   ✓  Positive theta (+${totals['net_theta']:.2f}/day)")
elif totals['net_theta'] > -10:
    print(f"   ⚠️  Small negative theta (-${abs(totals['net_theta']):.2f}/day)")
    print(f"       You lose ${abs(totals['net_theta']):.2f} per day to time decay.")
else:
    print(f"   ⚠️  SIGNIFICANT TIME DECAY (-${abs(totals['net_theta']):.2f}/day)")
    print(f"       You're losing ${abs(totals['net_theta']):.2f} PER DAY to time decay!")
    print(f"       Monthly loss if held: ${abs(totals['net_theta'] * 30):.2f}")
    print(f"       💡 Consider: Close losing long options or roll them out")

print("\n🎢 GAMMA RISK:")
if abs(totals['net_gamma']) > 1:
    print(f"   ⚠️  High gamma exposure ({totals['net_gamma']:.4f})")
    print(f"       Your delta changes significantly as market moves")
elif abs(totals['net_gamma']) > 0.1:
    print(f"   ✓  Moderate gamma ({totals['net_gamma']:.4f})")
else:
    print(f"   ✓  Low gamma ({totals['net_gamma']:.4f}) - mostly stocks")

print("\n📊 VOLATILITY RISK (VEGA):")
if abs(totals['net_vega']) > 50:
    print(f"   ⚠️  High vega exposure ({totals['net_vega']:.2f})")
    print(f"       Portfolio value changes ${abs(totals['net_vega']):.2f} per 1% IV move")
    if totals['net_vega'] > 0:
        print(f"       You WANT IV to increase (long volatility)")
    else:
        print(f"       You WANT IV to decrease (short volatility)")
else:
    print(f"   ✓  Moderate vega exposure ({totals['net_vega']:.2f})")

print("\n" + "=" * 100)
print("ACCESS THE UI")
print("=" * 100)
print("\n🌐 Open your browser to: http://localhost:5173")
print("📊 The Portfolio Greeks dashboard is now live at the top of the page!")
print("\nFeatures:")
print("  • Real-time Greeks aggregation across ALL brokers")
print("  • Stock positions counted as delta = 1.0")
print("  • Option Greeks scaled by contract size (×100)")
print("  • Grouped by underlying symbol")
print("  • Color-coded directional exposure")
print("  • Interactive refresh button")
print("\n" + "=" * 100 + "\n")

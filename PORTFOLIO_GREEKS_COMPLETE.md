# Portfolio Greeks - Complete Implementation

## Overview

Successfully implemented a comprehensive **Portfolio Greeks** feature that aggregates Greeks across ALL positions (stocks + options) from ALL brokers (TastyTrade, Alpaca Live, Alpaca Paper, IBKR Live, IBKR Paper).

**Key Innovation**: Stocks are treated as delta = 1.0, allowing you to see your total directional exposure combining stocks and options.

## Your Current Portfolio Analysis

### Portfolio Summary
- **Total Positions**: 13 (across all brokers)
- **Unique Underlyings**: 5 (AAPL, GOOG, SPY, BTCUSD, DOGEUSD)
- **Total Portfolio Value**: $4,873.10

### Portfolio Greeks (Critical Metrics)

| Greek | Value | Interpretation |
|-------|-------|----------------|
| **Net Delta** | +481.79 | ⚠️ STRONG BULLISH - Portfolio gains $481.79 per $1 market move UP |
| **Net Theta** | +$18.46/day | ✅ EXCELLENT - Collecting $18.46/day from time decay |
| **Net Gamma** | -3.23 | Delta decreases as market moves |
| **Net Vega** | -22.83 | Profit from decreasing IV |

### Risk Analysis

#### ✅ **What's Working**
1. **Positive Theta**: You're collecting **$18.46 per day** from time decay
   - This means you're net SHORT options (selling premium)
   - Monthly theta income: **$553.67**
   - Annualized (theoretical): **$6,736**

2. **Negative Vega**: Portfolio profits when volatility decreases
   - Good for premium sellers
   - Benefits from market calm

#### ⚠️ **What Needs Attention**
1. **High Bullish Delta**: +481.79 delta exposure
   - Your portfolio is HEAVILY bullish
   - You'll lose $481.79 for every $1 the market drops
   - **Recommendation**: Consider hedging with puts or reducing long exposure

2. **DOGEUSD Dominance**: 477 shares = +477 delta
   - Single crypto position represents 99% of your delta exposure
   - Extremely concentrated risk
   - **Recommendation**: Diversify or reduce position size

3. **Negative Gamma**: Your delta decreases as market moves
   - In a rally, you'll gain less as market goes up
   - In a drop, you'll lose more as market goes down

## Position Breakdown

### DOGEUSD (99% of Delta Risk!)
- **Position**: 477.16 shares (stock)
- **Delta Exposure**: +477.16
- **Value**: $67.10
- **Risk**: Extremely high concentration - this ONE position drives your entire portfolio delta

### AAPL (5 Positions - Stock + 4 Options)
- **Net Delta**: +13.93 (slightly bullish)
- **Net Theta**: +$8.49/day (collecting premium)
- **Total Value**: $3,067.27

**Breakdown**:
1. **11 shares** of AAPL stock = +11 delta
2. **Short** AAPL251212C00287500 (sold call) = -1.14 delta, collecting theta
3. **Long** AAPL251212C00292500 (bought call) = +0.80 delta, losing theta
4. **Long** AAPL251212P00267500 (bought put) = -1.68 delta, losing theta
5. **Short** AAPL251212P00272500 (sold put) = +4.96 delta, collecting theta

**Net Effect**: Mix of long stock with option spreads creating positive theta

### GOOG (5 Positions - Stock + 4 Options)
- **Net Delta**: -10.31 (slightly bearish)
- **Net Theta**: +$9.96/day (collecting premium)
- **Total Value**: $307.53

**Breakdown**:
1. **1 share** of GOOG stock = +1 delta
2. **Short** GOOG260109C00325000 (sold call) = -37.30 delta
3. **Long** GOOG260109C00345000 (bought call) = +14.06 delta
4. **Long** GOOG260109P00295000 (bought put) = -20.55 delta
5. **Short** GOOG260109P00305000 (sold put) = +32.48 delta

**Net Effect**: Complex option strategies creating net negative delta but positive theta

### SPY (1 Position)
- **Position**: 1 share (stock)
- **Delta Exposure**: +1.00
- **Value**: $688.55

### BTCUSD (1 Position)
- **Position**: 0.008 BTC (stock)
- **Delta Exposure**: +0.01
- **Value**: $742.66

## Understanding How Stocks Get Greeks

### The Core Concept

**Stocks don't have Greeks in the traditional sense**, but we can express them in Greek terms:

```
Stock Position = Delta of 1.0 per share
```

### Example Calculations

**10 shares of AAPL**:
- Delta = 10.0 (moves $10 for every $1 AAPL moves)
- Gamma = 0 (delta never changes)
- Theta = 0 (no time decay)
- Vega = 0 (no IV sensitivity)

**Combined with Option**:
- 10 shares AAPL = +10 delta
- 1x AAPL call (delta 0.37) = +37 delta (×100 multiplier)
- **Total exposure** = +47 delta

This means your position moves $47 for every $1 AAPL moves.

## API Endpoint

### GET /api/portfolio-greeks

**Response Format**:
```json
{
  "portfolio_totals": {
    "net_delta": 481.79,
    "net_gamma": -3.23,
    "net_theta": 18.46,
    "net_vega": -22.83,
    "total_positions": 13,
    "total_value": 4873.10,
    "num_underlyings": 5
  },
  "by_underlying": {
    "AAPL": {
      "underlying": "AAPL",
      "positions": [...],
      "net_delta": 13.93,
      "net_gamma": -2.23,
      "net_theta": 8.49,
      "net_vega": -0.73,
      "total_value": 3067.27
    },
    ...
  }
}
```

## Frontend Component

### Features

1. **Real-time Dashboard**
   - Located at top of main page
   - Auto-loads on page load
   - Refresh button for updates

2. **Summary Cards**
   - Net Delta (color-coded: green=bullish, red=bearish)
   - Net Theta (shows daily P&L from time decay)
   - Net Gamma
   - Net Vega

3. **Portfolio Stats**
   - Total positions
   - Number of underlyings
   - Total portfolio value
   - Delta per $1000 invested

4. **Greeks by Underlying Table**
   - All underlyings sorted by delta exposure
   - Shows number of positions per underlying
   - Net Greeks for each underlying

5. **Interpretation Guide**
   - Plain English explanations
   - Context-specific insights
   - Color-coded for quick understanding

## How the Calculation Works

### Step 1: Fetch All Positions
```python
# Get positions from all brokers
all_positions = []
for broker in ['tastytrade', 'alpaca_live', 'alpaca_paper', 'ibkr_live', 'ibkr_paper']:
    positions.extend(broker_data[broker]['positions'])
```

### Step 2: Fetch Greeks for Options
```python
# For each position symbol
if is_option(symbol):
    greeks = fetch_from_massive_api(symbol)
else:
    greeks = None  # Stock - no Greeks needed
```

### Step 3: Calculate Delta Exposure

**For Options**:
```python
delta_exposure = option_delta × quantity × 100
# Example: 0.37 delta × 1 contract × 100 = 37 delta
```

**For Stocks**:
```python
delta_exposure = 1.0 × quantity
# Example: 1.0 × 10 shares = 10 delta
```

### Step 4: Aggregate by Underlying
```python
# Group AAPL stock + AAPL options together
underlying['AAPL']['net_delta'] = stock_delta + option_deltas
```

### Step 5: Calculate Portfolio Totals
```python
portfolio_net_delta = sum(all_underlying_deltas)
portfolio_net_theta = sum(all_underlying_thetas)
...
```

## Use Cases

### 1. Risk Management
**Question**: "How exposed am I to a market crash?"

**Answer**: Check Net Delta
- Net Delta +481.79 = You'll lose $481.79 per $1 market drop
- High concentration in DOGEUSD (477 delta)

**Action**: Reduce DOGEUSD position or buy protective puts

### 2. Income Tracking
**Question**: "How much am I collecting from selling premium?"

**Answer**: Check Net Theta
- Net Theta +$18.46/day
- Monthly: $553.67
- Mainly from AAPL and GOOG options

**Action**: Monitor and consider adding more short premium strategies

### 3. Position Sizing
**Question**: "Is my portfolio balanced?"

**Answer**: Check by_underlying breakdown
- DOGEUSD: 477 delta (99% of exposure!)
- AAPL: 14 delta
- GOOG: -10 delta
- Others: minimal

**Action**: SEVERELY imbalanced - diversify immediately

### 4. Strategy Effectiveness
**Question**: "Are my option strategies working?"

**Answer**: Check individual underlying Greeks
- AAPL: Positive theta (+8.49) = ✅ Collecting premium
- GOOG: Positive theta (+9.96) = ✅ Collecting premium
- But net negative deltas on both = slight bearish bias

**Action**: Option strategies working well for premium collection

## Recommendations

### Immediate Actions (High Priority)

1. **⚠️ REDUCE DOGEUSD EXPOSURE**
   - Currently 99% of your portfolio delta
   - Single point of failure
   - Consider selling 400+ shares to reduce to <100 delta

2. **📊 Monitor Theta Decay**
   - You're collecting $18.46/day
   - Track actual P&L vs theoretical theta
   - Close positions before expiration if necessary

3. **🎯 AAPL Options Expiring Tomorrow!**
   - All AAPL options expire Dec 12, 2025
   - Decide: Close, roll, or let expire
   - Most are deep OTM and may expire worthless

### Medium-Term Actions

4. **Diversify Delta Exposure**
   - Add bearish hedges (SPY puts?)
   - Reduce crypto concentration
   - Balance across more stocks

5. **Leverage Positive Theta**
   - You're good at selling premium (+$18/day)
   - Consider expanding this strategy
   - Look for high IV opportunities

6. **Monitor Vega**
   - Net vega -22.83 means you profit from falling IV
   - If VIX spikes, your positions lose value
   - Consider this in volatile markets

## Testing

### Command Line Test
```bash
python test_portfolio_greeks.py
```

### API Test
```bash
curl http://localhost:8000/api/portfolio-greeks | python -m json.tool
```

### UI Access
Open browser to: http://localhost:5173

Look for the **Portfolio Greeks** section at the top of the dashboard.

## Files Created/Modified

### Backend
1. **backend_server.py** - Added `/api/portfolio-greeks` endpoint
   - Aggregates positions from all brokers
   - Fetches Greeks for options via Massive API
   - Treats stocks as delta = 1.0
   - Groups by underlying
   - Returns portfolio totals + breakdown

### Frontend
2. **frontend/src/components/PortfolioGreeks.tsx** - NEW component
   - Beautiful dashboard layout
   - Summary cards for each Greek
   - Table of Greeks by underlying
   - Interpretation guide
   - Refresh functionality

3. **frontend/src/App.tsx** - Added PortfolioGreeks component
   - Displays at top of page
   - Auto-loads on page load

### Testing
4. **test_portfolio_greeks.py** - Comprehensive test script
   - Fetches portfolio Greeks
   - Displays detailed analysis
   - Provides risk recommendations

## Summary

### What This Gives You

✅ **Complete Portfolio View**
- All positions from all brokers in one place
- Stocks AND options combined
- Real-time aggregation

✅ **True Directional Exposure**
- Know exactly how much you're long/short
- See which underlyings drive your risk
- Identify concentration issues

✅ **Time Decay Tracking**
- See if you're collecting or paying theta
- Estimate daily/monthly income
- Make better premium selling decisions

✅ **Risk Management**
- Spot imbalances immediately
- Understand gamma and vega exposure
- Make informed hedging decisions

✅ **Beautiful UI**
- Color-coded for quick insights
- Plain English explanations
- One-click refresh

### Next Steps

1. **Open the UI**: http://localhost:5173
2. **Review your Greeks**: Focus on delta and theta
3. **Take action**: Consider reducing DOGEUSD concentration
4. **Monitor daily**: Check theta collection and delta changes

---

**The Portfolio Greeks feature is 100% complete and operational!** 🎉

You now have a professional-grade risk management tool that combines stocks and options to show your true portfolio exposure.

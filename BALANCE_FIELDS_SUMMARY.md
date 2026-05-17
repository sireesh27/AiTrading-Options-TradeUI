# Balance Fields Summary

## API Endpoint: GET /api/positions

All broker accounts now return the following balance fields:

### Available Fields for Each Account:

1. **totalValue** - Total portfolio value (Net Liquidation Value)
2. **equity** - Account equity
3. **buyingPower** - Available buying power for trading
4. **dayPL** - Day's Profit/Loss (today's P/L)
5. **dayTrades** - Day trade count
6. **positions** - Array of current positions

---

## Field Details by Broker:

### TastyTrade:
```json
{
    "totalValue": 2887.03,      // net_liquidating_value
    "equity": 2887.03,           // margin_equity
    "buyingPower": 2887.03,      // derivative_buying_power
    "dayPL": 0.0,                // Calculated from positions (if available)
    "dayTrades": "0 / 3",
    "positions": []
}
```

**Data Sources:**
- `totalValue` → `balances.net_liquidating_value`
- `equity` → `balances.margin_equity`
- `buyingPower` → `balances.derivative_buying_power`
- `dayPL` → Calculated from position day_pl_close (if available)

---

### Alpaca (Live & Paper):
```json
{
    "totalValue": 99734.61,      // account.portfolio_value
    "equity": 99734.61,           // account.equity
    "buyingPower": 195072.24,     // account.buying_power
    "dayPL": 14.93,               // equity - last_equity
    "dayTrades": "0 / 3",
    "positions": [...]
}
```

**Data Sources:**
- `totalValue` → `account.portfolio_value`
- `equity` → `account.equity`
- `buyingPower` → `account.buying_power`
- `dayPL` → `account.equity - account.last_equity` (current - previous day's closing equity)

**Example Day's P/L Calculation:**
```
Current Equity: $99,734.61
Previous Day's Closing Equity: $99,719.68
Day's P/L = $99,734.61 - $99,719.68 = $14.93
```

---

### IBKR (Live & Paper):
```json
{
    "totalValue": 1004340.97,    // NetLiquidation
    "equity": 1004340.97,         // NetLiquidation (same)
    "buyingPower": 4015868.36,    // BuyingPower
    "dayPL": 0.0,                 // DailyPnL or UnrealizedPnL
    "dayTrades": "N/A",
    "positions": []
}
```

**Data Sources:**
- `totalValue` → Account Summary tag `NetLiquidation`
- `equity` → Account Summary tag `NetLiquidation`
- `buyingPower` → Account Summary tag `BuyingPower`
- `dayPL` → Account Summary tag `DailyPnL` (falls back to `UnrealizedPnL`)

**Available Account Summary Tags:**
- `NetLiquidation` - Total account value
- `BuyingPower` - Available buying power
- `DailyPnL` - Today's profit/loss
- `UnrealizedPnL` - Total unrealized P/L
- `RealizedPnL` - Total realized P/L

---

## Complete API Response Structure:

```json
{
    "tastytrade": {
        "totalValue": 2887.03,
        "equity": 2887.03,
        "buyingPower": 2887.03,
        "dayPL": 0.0,
        "dayTrades": "0 / 3",
        "positions": []
    },
    "alpaca_live": {
        "totalValue": 99.0,
        "equity": 99.0,
        "buyingPower": 99.0,
        "dayPL": 0.0,
        "dayTrades": "0 / 3",
        "positions": []
    },
    "alpaca_paper": {
        "totalValue": 99734.61,
        "equity": 99734.61,
        "buyingPower": 195072.24,
        "dayPL": 14.93,
        "dayTrades": "0 / 3",
        "positions": [
            {
                "symbol": "AAPL",
                "qty": 10.0,
                "avgPrice": 273.44,
                "currentPrice": 278.78,
                "pl": 53.4,
                "plPercent": 1.95,
                "source": "Alpaca Paper"
            }
        ]
    },
    "ibkr_live": {
        "totalValue": 103.0,
        "equity": 103.0,
        "buyingPower": 103.0,
        "dayPL": 0.0,
        "dayTrades": "N/A",
        "positions": []
    },
    "ibkr_paper": {
        "totalValue": 1004340.97,
        "equity": 1004340.97,
        "buyingPower": 4015868.36,
        "dayPL": 0.0,
        "dayTrades": "N/A",
        "positions": []
    }
}
```

---

## Testing the API:

### Start the backend server:
```bash
python backend_server.py
```

### Query all positions and balances:
```bash
curl http://localhost:8000/api/positions | python -m json.tool
```

### Test all broker connections:
```bash
python test_all_brokers.py
```

---

## Files Modified:

1. **backend_server.py** - Added equity and dayPL fields to response structure
2. **ibkr_manager.py** - Updated to fetch equity and dayPL from account summary
3. **alpaca_trader.py** - No changes needed (already had all required fields)
4. **main_tastytrade.py** - No changes needed (already had all required fields)

---

## Summary:

✅ **All 5 accounts now provide:**
- Total Balance (totalValue)
- Equity
- Buying Power
- Day's P/L (dayPL)

✅ **IBKR Live and Paper both fully functional**
✅ **Alpaca Live and Paper both fully functional**
✅ **TastyTrade OAuth2 authentication working**

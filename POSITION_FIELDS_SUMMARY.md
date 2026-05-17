# Position Fields Summary

## All Position Data Fields

Each position from every broker account now includes the following fields:

### ✅ Required Fields:

1. **symbol** - Stock/Option Symbol (e.g., "AAPL", "SPY", "BTCUSD")
2. **value** - Position Value (qty × currentPrice)
3. **pl** - Profit/Loss in dollars

### Additional Fields:

4. **qty** - Quantity/Number of shares
5. **avgPrice** - Average entry price
6. **currentPrice** - Current market price
7. **plPercent** - Profit/Loss percentage
8. **source** - Broker name (e.g., "Alpaca Paper", "IBKR Live", "TastyTrade")

---

## Position Structure Example:

### Alpaca Paper Position (AAPL):
```json
{
    "symbol": "AAPL",              // ✅ Stock Symbol
    "qty": 10.0,                   // Quantity
    "avgPrice": 273.44,            // Average entry price
    "currentPrice": 278.78,        // Current market price
    "value": 2787.80,              // ✅ Position Value (10 × $278.78)
    "pl": 53.4,                    // ✅ Profit/Loss ($534.00)
    "plPercent": 1.95,             // P/L Percentage (1.95%)
    "source": "Alpaca Paper"       // Broker account
}
```

### Calculation Details:
- **value** = qty × currentPrice = 10 × $278.78 = **$2,787.80**
- **pl** = (currentPrice - avgPrice) × qty = ($278.78 - $273.44) × 10 = **$53.40**
- **plPercent** = ((currentPrice - avgPrice) / avgPrice) × 100 = **1.95%**

---

## Complete API Response Example:

### GET /api/positions

```json
{
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
                "value": 2787.80,        // Position value
                "pl": 53.4,              // P/L in dollars
                "plPercent": 1.95,
                "source": "Alpaca Paper"
            },
            {
                "symbol": "BTCUSD",
                "qty": 0.00807702,
                "avgPrice": 123497.762,
                "currentPrice": 91423.0,
                "value": 738.43,         // Position value
                "pl": -259.07,           // P/L in dollars (loss)
                "plPercent": -25.97,
                "source": "Alpaca Paper"
            },
            {
                "symbol": "DOGEUSD",
                "qty": 477.158730775,
                "avgPrice": 0.257860481,
                "currentPrice": 0.141184,
                "value": 67.38,          // Position value
                "pl": -55.67,            // P/L in dollars (loss)
                "plPercent": -45.25,
                "source": "Alpaca Paper"
            }
        ]
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

## Field Descriptions:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| **symbol** | string | Stock or option ticker symbol | "AAPL" |
| **qty** | number | Number of shares/contracts | 10.0 |
| **avgPrice** | number | Average entry price per share | 273.44 |
| **currentPrice** | number | Current market price | 278.78 |
| **value** | number | Total position value (qty × price) | 2787.80 |
| **pl** | number | Unrealized P/L in dollars | 53.4 |
| **plPercent** | number | Unrealized P/L percentage | 1.95 |
| **source** | string | Which broker account | "Alpaca Paper" |

---

## Position Value Calculations by Broker:

### TastyTrade:
```python
value = qty × mark_price
```

### Alpaca (Live/Paper):
```python
value = qty × current_price
```

### IBKR (Live/Paper):
```python
value = position × market_price
```

---

## Testing:

### Test all positions:
```bash
curl http://localhost:8000/api/positions | python -m json.tool
```

### Check specific account:
```bash
curl -s http://localhost:8000/api/positions | python -m json.tool | grep -A 10 "alpaca_paper"
```

### Verify position fields:
```bash
curl -s http://localhost:8000/api/positions | python -c "
import sys, json
data = json.load(sys.stdin)
positions = data['alpaca_paper']['positions']
if positions:
    print('Position Fields for', positions[0]['symbol'], ':')
    for key, value in positions[0].items():
        print(f'  {key}: {value}')
"
```

---

## Summary:

✅ **All positions now include:**
1. **Symbol** - Stock/Option ticker
2. **Value** - Position value (qty × price)
3. **P/L** - Profit/Loss in dollars

✅ **Additional useful fields:**
- Quantity, Average Price, Current Price
- P/L Percentage
- Broker source

✅ **Available for all accounts:**
- TastyTrade
- Alpaca Live
- Alpaca Paper
- IBKR Live
- IBKR Paper

---

## Files Updated:

1. **backend_server.py** - Added `value` field to position structures for TastyTrade, Alpaca Live, and Alpaca Paper
2. **ibkr_manager.py** - Added `value` field to IBKR position structures

All positions are now properly structured with complete information for display and analysis.

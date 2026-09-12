# Trading Backend - Usage Guide

This directory contains backend scripts for trading with TastyTrade, Alpaca, and IBKR brokers.

> **Deploying to GCP?** See [GCP_DEPLOYMENT.md](GCP_DEPLOYMENT.md) for the step-by-step runbook (VM sizing, deploy script, SSH tunnels, weekly re-auth schedule).

## Setup

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API Keys:**
   - Edit `.env` file with your broker credentials
   - See `.env` file for required variables

---

## 1. Backend Server (FastAPI)

### Start the Server:
```bash
python backend_server.py
```

The server will run on: `http://localhost:8000`

### API Endpoints:

#### Get Account Balances & Positions (All Brokers):
```bash
curl http://localhost:8000/api/positions
```

**Response:**
```json
{
  "tastytrade": {
    "totalValue": 0.0,
    "buyingPower": 0.0,
    "dayTrades": "0 / 3",
    "positions": []
  },
  "alpaca": {
    "totalValue": 0.0,
    "buyingPower": 99.0,
    "dayTrades": "0 / 3",
    "positions": []
  },
  "ibkr": {
    "totalValue": 0.0,
    "buyingPower": 0.0,
    "dayTrades": "N/A",
    "positions": []
  }
}
```

#### Get Stock Price:
```bash
curl http://localhost:8000/api/stock-price/SPY
```

**Response:**
```json
{
  "symbol": "SPY",
  "price": 685.94,
  "bid": 685.9,
  "ask": 685.99
}
```

---

## 2. TastyTrade Script (Options Trading)

### Test Authentication:
```bash
python main_tastytrade.py --test-auth
```

### Get Option Chain:
```bash
python main_tastytrade.py --chain SPY
```

### Place Option Trade (Dry Run):
```bash
python main_tastytrade.py --trade \
  --symbol SPY \
  --strike 600 \
  --expiration 2025-12-31 \
  --type call \
  --action buy \
  --quantity 1
```

### Place Option Trade (LIVE):
```bash
python main_tastytrade.py --trade \
  --symbol SPY \
  --strike 600 \
  --expiration 2025-12-31 \
  --type call \
  --action buy \
  --quantity 1 \
  --live
```

**Arguments:**
- `--test-auth` - Test authentication only
- `--chain SYMBOL` - Fetch option chain for a symbol
- `--trade` - Place a trade
- `--symbol` - Underlying stock symbol (e.g., SPY, AAPL)
- `--strike` - Strike price (e.g., 600)
- `--expiration` - Expiration date in YYYY-MM-DD format
- `--type` - Option type: `call` or `put`
- `--action` - Trade action: `buy` or `sell`
- `--quantity` - Number of contracts (default: 1)
- `--live` - Execute live trade (without this, it's a dry run)

---

## 3. Alpaca Script (Stock Trading)

### Test Authentication:
```bash
python alpaca_trader.py --test-auth
```

### Get Current Positions:
```bash
python alpaca_trader.py --positions
```

### Place Stock Trade (Dry Run):
```bash
python alpaca_trader.py --trade \
  --symbol AAPL \
  --qty 10 \
  --side buy \
  --order-type market
```

### Place Stock Trade (LIVE):
```bash
python alpaca_trader.py --trade \
  --symbol AAPL \
  --qty 10 \
  --side buy \
  --order-type market \
  --live
```

### Place Limit Order:
```bash
python alpaca_trader.py --trade \
  --symbol AAPL \
  --qty 10 \
  --side buy \
  --order-type limit \
  --limit-price 150.00 \
  --live
```

**Arguments:**
- `--test-auth` - Test authentication only
- `--positions` - Show current positions
- `--trade` - Place a trade
- `--symbol` - Stock symbol (e.g., AAPL, TSLA)
- `--qty` - Quantity of shares
- `--side` - Trade side: `buy` or `sell`
- `--order-type` - Order type: `market` or `limit`
- `--limit-price` - Limit price (required for limit orders)
- `--live` - Execute live trade (without this, it's a dry run)

---

## 4. IBKR Setup

IBKR requires TWS (Trader Workstation) or IB Gateway to be running:

1. **Start TWS or IB Gateway**

2. **Enable API:**
   - File → Global Configuration → API → Settings
   - Check "Enable ActiveX and Socket Clients"
   - Check "Allow connections from localhost only"
   - Set Socket port: 7496 (Live) or 7497 (Paper)

3. **Test Connection:**
   ```bash
   # Run the backend server and check IBKR status
   python backend_server.py
   ```

---

## Environment Variables (.env file)

### TastyTrade:
```
TASTY_USERNAME=your_email@example.com
TASTY_PASSWORD=your_password
TASTY_LIVE=True  # True for live, False for certification/sandbox
```

### Alpaca:
```
ALPACA_API_KEY=your_api_key
ALPACA_API_SECRET=your_api_secret
ALPACA_PAPER=false  # true for paper trading, false for live
```

### IBKR:
- No API keys needed in .env
- Requires TWS/IB Gateway running locally

---

## Current Status

Based on latest test:
- ✅ **Alpaca**: Connected successfully (Account: 938056519, Buying Power: $99)
- ❌ **TastyTrade**: Authentication failed (check credentials)
- ❌ **IBKR**: Connection timeout (ensure TWS/IB Gateway is running)

---

## Troubleshooting

### TastyTrade "Invalid Credentials":
- Verify username/password in `.env`
- Check if 2FA is enabled (API may not support 2FA)
- Try LIVE mode: `TASTY_LIVE=True`

### IBKR Connection Timeout:
- Ensure TWS or IB Gateway is running
- Enable API in TWS settings
- Check firewall settings
- Verify port 7496 (live) or 7497 (paper) is open

### Alpaca Issues:
- Verify API keys are correct
- Check if using Paper or Live keys correctly
- Ensure `ALPACA_PAPER` setting matches your API keys

---

## Notes

- **Dry Run by Default**: All trades are dry runs unless you add `--live` flag
- **Market Hours**: Some APIs only work during market hours
- **Rate Limits**: Be aware of API rate limits for each broker
- **Safety**: Always test with dry runs first before going live

# Robinhood API Setup Guide

## ⚠️ IMPORTANT WARNING

**This integration uses an UNOFFICIAL Robinhood API** which Robinhood does not support and actively tries to prevent.

### Key Limitations:
- ❌ **Not officially supported** - May break at any time
- ❌ **Authentication issues** - Robinhood frequently changes their authentication
- ❌ **Stocks only** - Official API only supports cryptocurrency trading
- ❌ **Account risk** - Unofficial API usage may violate Robinhood TOS
- ⚠️ **Use at your own risk** - No guarantees of reliability

### Alternatives:
For production trading, consider using officially supported brokers:
- ✅ **Alpaca** - Free API, officially supported
- ✅ **TastyTrade** - Options trading, official API
- ✅ **IBKR** - Professional platform, official API

---

## 🔧 Prerequisites

1. **Robinhood Account** with username/password access
2. **Two-Factor Authentication** enabled
3. **Python Libraries:**
   ```bash
   pip install robin-stocks pyotp
   ```

---

## 📋 Step-by-Step Setup

### Step 1: Install Required Libraries

```bash
pip install robin-stocks pyotp
```

**Libraries:**
- `robin-stocks` - Unofficial Robinhood Python API wrapper
- `pyotp` - For generating 2FA TOTP codes

---

### Step 2: Enable Two-Factor Authentication (2FA)

1. **Log into Robinhood app** (mobile or web)

2. **Navigate to Settings:**
   - Mobile: Account → Security → Two-Factor Authentication
   - Web: Account → Settings → Security

3. **Enable 2FA:**
   - Click "Turn On Two-Factor Authentication"
   - **IMPORTANT:** When asked which app to use, select **"Other"** or **"Can't scan?"**
   - **DO NOT** select Google Authenticator, Authy, etc.

4. **Copy the Secret Key:**
   - Robinhood will show an alphanumeric code (e.g., `ABCD1234EFGH5678IJKL`)
   - This is your **TOTP Secret Key**
   - **Save this key immediately** - you'll need it for your `.env` file

5. **Complete Setup:**
   - Use an authenticator app (Google Authenticator, Authy, etc.) to scan the QR code
   - Enter the 6-digit code to verify
   - Save backup codes

---

### Step 3: Get Your Credentials

You'll need THREE things:

1. **Username (Email):** Your Robinhood login email
2. **Password:** Your Robinhood password
3. **TOTP Secret:** The alphanumeric key from Step 2

**Example TOTP Secret:**
```
JBSWY3DPEHPK3PXP  (this is just an example, yours will be different)
```

---

### Step 4: Update Your .env File

Add these lines to your `.env` file:

```env
# Robinhood Configuration (UNOFFICIAL API - Use at your own risk)
ROBINHOOD_USERNAME=your_email@example.com
ROBINHOOD_PASSWORD=your_password
ROBINHOOD_TOTP_SECRET=YOUR_TOTP_SECRET_HERE

# Example:
# ROBINHOOD_USERNAME=john.doe@gmail.com
# ROBINHOOD_PASSWORD=MySecurePassword123!
# ROBINHOOD_TOTP_SECRET=JBSWY3DPEHPK3PXP
```

**Security Tips:**
- ⚠️ **Never commit** `.env` to git
- ⚠️ **Keep your TOTP secret secure** - it can be used to access your account
- ⚠️ **Use a strong password**
- ⚠️ **Consider using a dedicated trading account** instead of your main account

---

### Step 5: Test Authentication

```bash
python robinhood_trader.py --test-auth
```

**Expected Output (Success):**
```
INFO - Authenticating with Robinhood as your_email@example.com...
INFO - Generated 2FA code from TOTP secret
INFO - Authentication successful!
```

**Expected Output (Failure):**
```
ERROR - Authentication failed: [error message]
```

---

## 🧪 Testing Your Setup

### Test Authentication:
```bash
python robinhood_trader.py --test-auth
```

### Get Account Info:
```bash
python robinhood_trader.py --account
```

### Get Positions:
```bash
python robinhood_trader.py --positions
```

### Get Stock Quote:
```bash
python robinhood_trader.py --quote AAPL
```

### Place Test Order (Dry Run):
```bash
python robinhood_trader.py --trade --symbol AAPL --qty 1 --side buy
```

### Place Live Order (⚠️ REAL MONEY):
```bash
python robinhood_trader.py --trade --symbol AAPL --qty 1 --side buy --live
```

---

## 🔍 Troubleshooting

### Error: "robin-stocks library not installed"

**Solution:**
```bash
pip install robin-stocks pyotp
```

---

### Error: "Authentication failed: invalid credentials"

**Possible Causes:**
1. ❌ Wrong username or password
2. ❌ TOTP secret is incorrect
3. ❌ Robinhood changed their authentication method

**Solutions:**
1. Double-check username/password
2. Re-enable 2FA and get a new TOTP secret
3. Check if robin-stocks library has updates:
   ```bash
   pip install --upgrade robin-stocks
   ```

---

### Error: "Failed to generate TOTP code"

**Possible Causes:**
1. ❌ TOTP secret is missing or incorrect
2. ❌ TOTP secret has spaces or special characters

**Solutions:**
1. Remove any spaces from TOTP secret in `.env` file
2. Re-enable 2FA to get a fresh TOTP secret
3. Ensure TOTP secret is in all CAPS (if applicable)

---

### Error: "challenge_type: sms" or "challenge_type: email"

**This means Robinhood requires additional verification.**

**Solution:**
Unfortunately, the unofficial API doesn't fully support SMS/Email challenges. You may need to:
1. Try authenticating through the Robinhood app first
2. Wait 24 hours and try again
3. Use the official Robinhood Crypto API instead (crypto only)

---

### Warning: "Authentication stopped working suddenly"

**Robinhood frequently changes their API to prevent unofficial access.**

**What to do:**
1. Check for robin-stocks updates:
   ```bash
   pip install --upgrade robin-stocks
   ```
2. Check GitHub issues: [robin-stocks Issues](https://github.com/jmfernandes/robin_stocks/issues)
3. Consider switching to an officially supported broker (Alpaca, IBKR, TastyTrade)

---

## 📊 How It Works

### Authentication Flow:

1. **Username/Password** → Robinhood servers
2. **TOTP Secret** → Generate 6-digit code using pyotp
3. **6-digit code** → Sent to Robinhood for 2FA verification
4. **Session Token** → Stored locally for subsequent requests

### Session Management:

- Sessions are saved in `~/.tokens/robinhood.pickle`
- Sessions may expire after 24 hours
- Re-authentication required when session expires

---

## 🆚 Official vs Unofficial API

| Feature | Official API | Unofficial API (robin-stocks) |
|---------|--------------|-------------------------------|
| **Stocks Trading** | ❌ No | ✅ Yes (unstable) |
| **Crypto Trading** | ✅ Yes | ✅ Yes |
| **Options Trading** | ❌ No | ✅ Yes (unstable) |
| **Officially Supported** | ✅ Yes | ❌ No |
| **Rate Limits** | Known | Unknown |
| **Reliability** | High | Low (may break) |
| **Account Risk** | None | Possible TOS violation |
| **Setup Complexity** | Medium | Medium |

---

## 🔐 Security Best Practices

### 1. **Use Environment Variables**
Never hardcode credentials in your code:
```python
# ❌ BAD
username = "myemail@gmail.com"
password = "mypassword"

# ✅ GOOD
username = os.getenv("ROBINHOOD_USERNAME")
password = os.getenv("ROBINHOOD_PASSWORD")
```

### 2. **Protect Your .env File**
Add to `.gitignore`:
```
.env
*.pickle
.tokens/
```

### 3. **Rotate Credentials Regularly**
- Change password every 90 days
- Re-generate TOTP secret periodically

### 4. **Monitor Account Activity**
- Check Robinhood app regularly for unauthorized activity
- Enable email/push notifications for trades

### 5. **Use Separate Trading Account**
- Don't use your main Robinhood account for API trading
- Create a dedicated account with limited funds

---

## 🚀 Alternative: Official Robinhood Crypto API

If you only need **cryptocurrency trading**, use the official API:

### Setup:
1. Go to [Robinhood API Credentials Portal](https://robinhood.com/crypto/api)
2. Create API credentials (requires active Robinhood Crypto account)
3. Use official documentation: https://docs.robinhood.com/crypto/trading/

### Benefits:
- ✅ Officially supported
- ✅ No risk of account suspension
- ✅ Stable authentication
- ✅ Better documentation

### Limitation:
- ❌ Crypto only, no stocks/options

---

## 📚 Additional Resources

- [robin-stocks Documentation](https://robin-stocks.readthedocs.io/)
- [robin-stocks GitHub](https://pypi.org/project/robin-stocks/)
- [Robinhood Official Crypto API](https://docs.robinhood.com/)
- [Stack Overflow: robin-stocks Issues](https://stackoverflow.com/questions/tagged/robinhood-api)
- [AlgoTrading101 Robinhood Guide](https://algotrading101.com/learn/robinhood-api-guide/)

---

## ⚠️ Final Disclaimer

**By using this unofficial Robinhood integration, you acknowledge:**

1. This is **NOT officially supported** by Robinhood
2. Your account **may be suspended** for API usage
3. The integration **may break at any time** without warning
4. You are **responsible for any losses** incurred
5. This is for **educational purposes only**

**Recommended for production:**
- Use **Alpaca** (free, officially supported)
- Use **Interactive Brokers** (professional platform)
- Use **TastyTrade** (options trading)

---

## ✅ Quick Setup Checklist

- [ ] Installed `robin-stocks` and `pyotp`
- [ ] Enabled 2FA on Robinhood account
- [ ] Copied TOTP secret key
- [ ] Added credentials to `.env` file
- [ ] Tested authentication with `--test-auth`
- [ ] Tested account info with `--account`
- [ ] Read and understood the warnings
- [ ] Ready to use (at your own risk!)

---

**Remember:** This is an unofficial API. For reliable, production-grade trading, use officially supported brokers!

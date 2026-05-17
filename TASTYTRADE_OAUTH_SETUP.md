# TastyTrade OAuth2 Setup Guide

## 🚨 IMPORTANT: Authentication Change

**TastyTrade is discontinuing username/password authentication on December 1st, 2025.**

You must migrate to OAuth2 authentication to continue using the API after this date.

---

## Step-by-Step OAuth2 Setup

### Step 1: Create OAuth2 Application

1. Go to [my.tastytrade.com](https://my.tastytrade.com) and log in

2. Navigate to:
   ```
   Manage → My Profile → API → OAuth Applications
   ```

3. Click **"Create Application"**
   - **Name**: Choose any name (e.g., "Trading Bot")
   - **Redirect URI**: Use `http://localhost` (not needed for personal use)
   - Click **Save**

4. You'll see your application listed with:
   - **Client ID**: (you'll see this)
   - **Client Secret**: Click "Show" to reveal it
   - **Copy and save the Client Secret** - you'll need this!

---

### Step 2: Generate Refresh Token

1. In your OAuth application, click **"Manage"**

2. Scroll down to **"Create Grant"** section

3. Click **"Create Grant"** button

4. You'll receive a **Refresh Token**
   - **Copy and save this token** - you'll need it!
   - ⚠️ This token won't be shown again, so save it securely

---

### Step 3: Update Your .env File

Open your `.env` file and add the OAuth2 credentials:

```env
# OAuth2 Authentication (REQUIRED after Dec 1, 2025)
TASTY_CLIENT_SECRET=your_client_secret_here
TASTY_REFRESH_TOKEN=your_refresh_token_here
TASTY_LIVE=True  # Set to False for sandbox/certification environment

# Legacy authentication (will be removed Dec 1, 2025)
# TASTY_USERNAME=sireesh.ch@gmail.com
# TASTY_PASSWORD=your_password
```

**Important:**
- Comment out or remove `TASTY_USERNAME` and `TASTY_PASSWORD`
- The code will try OAuth2 first, then fall back to username/password

---

### Step 4: Test Authentication

Run this command to test OAuth2 authentication:

```bash
python main_tastytrade.py --test-auth
```

**Expected Output (Success):**
```
INFO - Authenticating with OAuth2 (LIVE)...
INFO - OAuth2 authentication successful!
INFO - Using account: XXXX1234
```

**Expected Output (Failure - using legacy method):**
```
WARNING - Using deprecated username/password authentication.
WARNING - Please migrate to OAuth2 before December 1, 2025!
INFO - Authenticating as your_email@example.com (LIVE)...
```

---

## Troubleshooting

### Error: "OAuth2 authentication failed"

**Possible Causes:**
1. **Incorrect Client Secret or Refresh Token**
   - Double-check you copied them correctly
   - No extra spaces or line breaks

2. **Wrong Environment**
   - If using sandbox, set `TASTY_LIVE=False`
   - If using production, set `TASTY_LIVE=True`
   - Refresh token must match the environment

3. **Expired or Invalid Refresh Token**
   - Generate a new refresh token in the OAuth application dashboard

### Error: "invalid_credentials" (with username/password)

This occurs when:
- Your password is incorrect
- 2FA is enabled (2FA blocks username/password API access)
- You're using sandbox credentials in production environment (or vice versa)

**Solution:** Migrate to OAuth2 - it's compatible with 2FA!

---

## OAuth2 vs Username/Password

| Feature | OAuth2 | Username/Password |
|---------|--------|-------------------|
| Security | ✅ High (short-lived tokens) | ❌ Lower (long-lived session) |
| 2FA Compatible | ✅ Yes | ❌ No |
| Expiration | 15 min (auto-refresh) | 24 hours |
| Supported After Dec 1, 2025 | ✅ Yes | ❌ No (Discontinued) |
| Setup Complexity | Medium | Easy |

---

## Additional Resources

- [TastyTrade OAuth2 Guide](https://developer.tastytrade.com/api-guides/oauth/)
- [GitHub Issue #269 - Migration Notice](https://github.com/tastyware/tastytrade/issues/269)
- Support: api.support@tastytrade.com

---

## Code Changes Made

The authentication code has been updated to support both methods:

1. **Tries OAuth2 first** (if `TASTY_CLIENT_SECRET` and `TASTY_REFRESH_TOKEN` are set)
2. **Falls back to username/password** (if OAuth2 credentials are not present)
3. **Shows warnings** when using deprecated authentication

This ensures backward compatibility while encouraging migration to OAuth2.

---

## Quick Reference

### OAuth2 Environment Variables:
```env
TASTY_CLIENT_SECRET=<from OAuth app settings>
TASTY_REFRESH_TOKEN=<from Create Grant button>
TASTY_LIVE=True
```

### Test Commands:
```bash
# Test authentication
python main_tastytrade.py --test-auth

# Get option chain
python main_tastytrade.py --chain SPY

# Start backend server
python backend_server.py
```

---

**Remember:** OAuth2 is required by December 1st, 2025. Migrate now to avoid disruption!

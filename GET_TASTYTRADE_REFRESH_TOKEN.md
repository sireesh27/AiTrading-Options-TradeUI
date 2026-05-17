# How to Get Your TastyTrade Refresh Token

## 🎯 Quick Overview

You need TWO things from TastyTrade:
1. **Client Secret** (from OAuth application)
2. **Refresh Token** (from "Create Grant")

---

## 📋 Step-by-Step Instructions

### Step 1: Log Into TastyTrade

1. Go to **[my.tastytrade.com](https://my.tastytrade.com)**
2. Log in with your TastyTrade credentials

---

### Step 2: Navigate to OAuth Applications

Click through the following path:

```
Manage (top menu) → My Profile → API → OAuth Applications
```

Or directly visit: `my.tastytrade.com/manage/api`

---

### Step 3: Create a New OAuth Application

1. Click the **"+ New OAuth client"** button (or similar)

2. Fill in the application details:
   - **Name**: Give it any name (e.g., "Trading Bot", "Python API", etc.)
   - **Redirect URI**: Enter `http://localhost:8000`
     - ⚠️ Must be a full URI (include `http://` or `https://`)
     - For personal use, `http://localhost:8000` is fine

3. **Scopes**: Check ALL the scopes you need:
   - ✅ Read account data
   - ✅ Place orders
   - ✅ Read positions
   - ✅ Market data access
   - (Select all that apply to your use case)

4. Click **"Save"** or **"Create"**

---

### Step 4: Get Your Client Secret

After creating the application, you'll see:

**⚠️ IMPORTANT: This is shown ONLY ONCE!**

```
Client ID: abc123def456... (you can see this anytime)
Client Secret: xyz789secret... (SAVE THIS NOW!)
```

**Action Required:**
- **Copy the Client Secret** immediately
- Paste it into your `.env` file as `TASTY_CLIENT_SECRET`
- If you lose it, you'll need to regenerate it

---

### Step 5: Generate Your Refresh Token (EASIEST METHOD)

1. In the **OAuth Applications** list, find your newly created app

2. Click **"Manage"** next to your application

3. Scroll down to find the **"Create Grant"** section

4. Click the **"Create Grant"** button

5. You'll see your **Refresh Token** displayed:
   ```
   Refresh Token: abcdef123456789...
   ```

6. **Copy this token immediately!**
   - Paste it into your `.env` file as `TASTY_REFRESH_TOKEN`
   - ⚠️ Save it securely - it won't be shown again

---

### Step 6: Update Your .env File

Open your `.env` file and add these lines:

```env
# TastyTrade OAuth2 Credentials
TASTY_CLIENT_SECRET=your_client_secret_from_step_4
TASTY_REFRESH_TOKEN=your_refresh_token_from_step_5
TASTY_LIVE=True

# Comment out or remove old credentials
# TASTY_USERNAME=sireesh.ch@gmail.com
# TASTY_PASSWORD=SASaathviS9$Tt
```

**Example:**
```env
TASTY_CLIENT_SECRET=xyz789secretABC123DEF456
TASTY_REFRESH_TOKEN=abcdef123456789ghijkl987654321
TASTY_LIVE=True
```

---

### Step 7: Test Your Setup

Run this command to verify authentication:

```bash
cd "c:\Sireesh\AiTrading\Options\TradeUI"
python main_tastytrade.py --test-auth
```

**Expected Output (SUCCESS):**
```
INFO - Authenticating with OAuth2 (LIVE)...
INFO - OAuth2 authentication successful!
INFO - Using account: XXXX1234
```

---

## 🔧 Troubleshooting

### Can't Find OAuth Applications Menu?

**Try these URLs directly:**
- **Live Account**: [my.tastytrade.com/manage/api](https://my.tastytrade.com/manage/api)
- **Sandbox Account**: [my.cert.tastyworks.com/manage/api](https://my.cert.tastyworks.com/manage/api)

### Lost Your Client Secret?

1. Go to **OAuth Applications**
2. Click **"Manage"** on your app
3. Click **"Settings"**
4. Click **"Regenerate Client Secret"**
5. Copy the new secret (old one will stop working)

### Lost Your Refresh Token?

1. Go to **OAuth Applications**
2. Click **"Manage"** on your app
3. Click **"Create Grant"** again
4. You'll get a NEW refresh token
5. Old refresh token may still work (they don't expire)

### Error: "OAuth2 authentication failed"

**Possible causes:**
- ❌ Wrong Client Secret (check for spaces or typos)
- ❌ Wrong Refresh Token (check for spaces or typos)
- ❌ Wrong environment (`TASTY_LIVE=True` but using sandbox tokens)
- ❌ Tokens from different accounts

**Solution:**
1. Double-check you copied the tokens correctly (no extra spaces)
2. Verify `TASTY_LIVE` setting matches your token environment
3. Regenerate both tokens if still failing

---

## 📝 Important Notes

### About Refresh Tokens:
- ✅ **Never expire** - Generate once, use forever
- ✅ **No rate limits** on refresh
- ✅ **Works with 2FA** enabled
- ⚠️ **Keep them secret** - Anyone with your refresh token can access your account

### About Access Tokens:
- Generated automatically from refresh token
- Expire after **15 minutes**
- The SDK handles auto-refresh for you
- You never need to manually manage access tokens

### Security Best Practices:
1. **Never commit** `.env` to git
2. **Don't share** your refresh token
3. **Regenerate tokens** if compromised
4. **Use separate tokens** for different applications

---

## 🎥 Visual Guide (Text Description)

If you're having trouble finding the menus, here's what to look for:

```
TastyTrade Website Header:
┌─────────────────────────────────────────┐
│  [Trade] [Manage] [Research] [Profile] │  ← Click "Manage"
└─────────────────────────────────────────┘

After clicking Manage:
┌─────────────────────────────────────────┐
│  Sidebar Menu:                          │
│  • My Profile ← Click this              │
│    ├─ Personal Info                     │
│    ├─ API  ← Then click this            │
│    │  └─ OAuth Applications ← Finally   │
│    └─ Settings                          │
└─────────────────────────────────────────┘

OAuth Applications Page:
┌─────────────────────────────────────────┐
│  OAuth Applications                     │
│  [+ New OAuth client]  ← Click to start │
│                                         │
│  Your Applications:                     │
│  • Trading Bot        [Manage]          │
│                                         │
└─────────────────────────────────────────┘

After clicking "Manage" on your app:
┌─────────────────────────────────────────┐
│  Application Details                    │
│  Client ID: abc123...                   │
│  Client Secret: ******  [Show]          │
│                                         │
│  Grants                                 │
│  [Create Grant]  ← Click to get token   │
│                                         │
└─────────────────────────────────────────┘
```

---

## 📚 Additional Resources

- [TastyTrade OAuth Guide](https://developer.tastytrade.com/oauth/)
- [TastyTrade API Documentation](https://developer.tastytrade.com/)
- [TastyTrade Help Center](https://support.tastytrade.com/support/s/solutions/articles/43000578659)
- [Python SDK Documentation](https://tastyworks-api.readthedocs.io/en/latest/sessions.html)

---

## ✅ Quick Checklist

- [ ] Logged into my.tastytrade.com
- [ ] Created OAuth application
- [ ] Copied Client Secret to `.env` file
- [ ] Generated refresh token via "Create Grant"
- [ ] Copied Refresh Token to `.env` file
- [ ] Set `TASTY_LIVE=True` in `.env`
- [ ] Commented out old username/password
- [ ] Tested with `python main_tastytrade.py --test-auth`
- [ ] Saw "OAuth2 authentication successful!" message

---

**You're all set! Your TastyTrade API will now work with OAuth2 authentication.**

# IBKR Web API — Headless OAuth 1.0a Setup

This lets the backend trade through IBKR **fully unattended** — no IB Gateway, no
TWS, no VM, no weekly VNC re-login. IBKR hosts the brokerage session; your backend
authenticates with OAuth 1.0a credentials.

> **Account note:** IBKR officially frames OAuth 1.0a as "institutional," but
> individual accountholders have successfully self-registered (paper + live).
> OAuth 2.0 for individuals is "coming, no ETA." OAuth 1.0a is the working path today.
> Start with **paper** to validate everything safely before touching live.

---

## Step 1 — Register an OAuth consumer (in your IBKR account)

1. Log in to **IBKR Client Portal** (the account you'll trade with — use your
   **paper** account login first).
2. Go to **Settings → Account Settings → (search) "OAuth"**, or open the
   **API → Self-Service OAuth** section.
3. Register a new OAuth application / consumer. IBKR assigns you a
   **Consumer Key** (25-char hex string).

## Step 2 — Generate keys & tokens

In the self-service portal you generate and download:

| Item | What it is |
|------|-----------|
| **Consumer Key** | Identifies your app (from Step 1) |
| **Access Token** | Your account's access token |
| **Access Token Secret** | Secret paired with the access token |
| **Private Signature Key** | RSA private key — signs each request (`.pem`) |
| **Private Encryption Key** | RSA private key — decrypts the Live Session Token (`.pem`) |
| **DH parameters** | Diffie-Hellman prime file (`dhparam.pem`) |

> The portal walks you through generating an RSA keypair (you upload the public
> keys to IBKR, keep the **private** `.pem` files), and Diffie-Hellman params.

## Step 3 — Extract the DH prime

The app needs the DH **prime** as a hex string. From `dhparam.pem`:

```bash
openssl dhparam -in dhparam.pem -text -noout
```
Copy the long `prime:`/`P:` hex value (strip colons/whitespace) → this is
`IBKR_WEBAPI_PAPER_DH_PRIME`. The generator is almost always `2`.

## Step 4 — Place the key files (outside git)

```
TradeUI/
  secrets/
    paper_private_signature.pem
    paper_private_encryption.pem
    live_private_signature.pem      (later, for live)
    live_private_encryption.pem
```
`secrets/` and `*.pem` are already in `.gitignore` — they never get committed.

## Step 5 — Fill in `.env`

Copy the block from `.env.example` and set the paper values:

```dotenv
IBKR_API_MODE=webapi

IBKR_WEBAPI_PAPER_CONSUMER_KEY=xxxxxxxxxxxxxxxxxxxxxxxxx
IBKR_WEBAPI_PAPER_ACCESS_TOKEN=xxxxxxxx
IBKR_WEBAPI_PAPER_ACCESS_TOKEN_SECRET=xxxxxxxx
IBKR_WEBAPI_PAPER_DH_PRIME=00c6f1... (long hex)
IBKR_WEBAPI_PAPER_ENCRYPTION_KEY_FP=./secrets/paper_private_encryption.pem
IBKR_WEBAPI_PAPER_SIGNATURE_KEY_FP=./secrets/paper_private_signature.pem
IBKR_WEBAPI_PAPER_DH_GENERATOR=2
IBKR_WEBAPI_PAPER_REALM=limited_poa
```

## Step 6 — Test

```bash
python test_ibkr_webapi.py --account paper
```
This runs the full loop: OAuth → Live Session Token → brokerage session →
account/positions → a stock quote. If it prints your account and a SPY quote,
you're connected. Then start the backend normally:

```bash
python backend_server.py     # picks up IBKR_API_MODE=webapi automatically
```

---

## How it stays unattended

- On first authenticated call, `ibind` runs the OAuth 1.0a **Live Session Token**
  handshake (Diffie-Hellman + RSA-SHA256) — no human, no 2FA prompt.
- A background **tickler** pings `/tickle` every 60s to keep the hosted session
  alive. If IBKR ever drops the session, the next request re-initializes it.
- Nothing to restart, no VNC, no VM.

## Going live

Repeat Steps 1–5 against your **live** IBKR login, fill the `IBKR_WEBAPI_LIVE_*`
vars + `secrets/live_*.pem`, and the backend serves both accounts. Orders still
default to **paper** unless a request explicitly sets `account: "live"`.

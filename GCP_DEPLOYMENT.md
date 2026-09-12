# Deploying the IBKR Gateways to GCP

Runbook for running the IB Gateway containers (live + paper + weekly scheduler)
on a Google Compute Engine VM, and connecting the trading app to them.

- **Project:** `options-data-475811`  **Zone:** `us-south1-a`  **VM:** `duckdb-vm`
- **What gets deployed:** `docker-compose-ibkr.yml` → `ib-gateway-live`,
  `ib-gateway-paper`, `ib-gateway-scheduler`
- **Script:** `deploy_ibkr.sh` (runs on the VM)

---

## 0. Before you start

### Resize the VM (required)
`duckdb-vm` is an **e2-small (2 GB RAM)**. The two gateways need ~4 GB and the
deploy script refuses to run below 3.5 GB.

| Machine type | RAM | Cost (approx) | Verdict |
|---|---|---|---|
| e2-small | 2 GB | ~$12/mo | ❌ will OOM |
| e2-medium | 4 GB | ~$25/mo | ⚠️ works, tight with DuckDB on the same box |
| **e2-standard-2** | 8 GB | ~$49/mo | ✅ recommended |

Console → Compute Engine → `duckdb-vm` → **Stop** → **Edit** → Machine type →
**Save** → **Start**. Expect ~2 minutes of downtime for anything already on it.

### Run the gateways in ONE place only
IBKR allows **one session per login**. If the gateways are running on your PC
*and* on the VM with the same logins, they will keep kicking each other off.
Before starting them in the cloud, stop the local ones:

```powershell
docker compose -f docker-compose-ibkr.yml down     # on your PC
```

### Have these ready
- **Live** IBKR username + password (IB Key 2FA on your phone)
- **Paper** username + password — the dedicated paper user, *not* the live
  login (IB rejects the live login for paper: *"multiple Paper Trading users"*).
  Client Portal → Settings → Account Settings → **Paper Trading Account**.
- A VNC password (only used if you ever need to look at the gateway screen)

---

## 1. Open a shell on the VM

Easiest: the **SSH** button on the instance page (browser terminal). Or, from
Cloud Shell:

```bash
gcloud compute ssh duckdb-vm --zone us-south1-a --project options-data-475811
```

## 2. Run the deploy script

Download first — it prompts for credentials, which `curl | bash` cannot do:

```bash
curl -sSLo deploy_ibkr.sh https://raw.githubusercontent.com/sireesh27/AiTrading-Options-TradeUI/master/deploy_ibkr.sh
bash deploy_ibkr.sh
```

The script:
1. checks RAM (aborts on < 3.5 GB),
2. installs Docker + compose if missing,
3. clones/updates the repo into `~/AiTrading-Options-TradeUI`,
4. prompts for the live, paper and VNC credentials and writes them to
   `.env` (`chmod 600`, git-ignored) together with `IBKR_HOST=127.0.0.1`,
5. pulls the image and starts live, paper and the scheduler.

**No GCP firewall rules are needed.** The API ports (4001/4002) and VNC ports
(5900/5901) are bound to `127.0.0.1` on the VM — the TWS API socket is
unauthenticated, so it is never exposed to the internet. Access is via SSH
tunnel (step 4).

## 3. Approve the live login

The live gateway sends an **IB Key push** to the IBKR Mobile app — approve it.
Paper logs in on its own (no 2FA). Watch progress:

```bash
docker logs -f ib-gateway-live | grep -E 'Second Factor|Login has completed'
docker compose -f docker-compose-ibkr.yml ps        # both should become healthy
```

## 4. Connect the app — two options (no code changes either way)

### Option A — gateways in the cloud, app on your PC
Open an SSH tunnel; the local backend then works exactly as it does today
(`IBKR_HOST=127.0.0.1`, ports 4001/4002):

```powershell
gcloud compute ssh duckdb-vm --zone us-south1-a --project options-data-475811 -- -L 4001:localhost:4001 -L 4002:localhost:4002
```
Keep that window open; run `python backend_server.py` and the frontend locally.

### Option B — everything on the VM (always-on)
On the VM:
```bash
cd ~/AiTrading-Options-TradeUI
# add TastyTrade / Alpaca / Massive keys to .env (see .env.example)
pip install -r requirements.txt && python backend_server.py      # :8000
cd frontend && npm install && npm run dev                          # :5173
```
From your PC, tunnel the app ports and open http://localhost:5173 — the
frontend calls `localhost:8000`, so it works unchanged through the tunnel:
```powershell
gcloud compute ssh duckdb-vm --zone us-south1-a --project options-data-475811 -- -L 8000:localhost:8000 -L 5173:localhost:5173
```
For true 24/7 operation run the backend as a systemd service (not yet set up).

> **Local gcloud:** tunnels need a working `gcloud compute ssh` on your PC. If
> `gcloud` is not recognised in PowerShell, install the Google Cloud SDK with
> the official *interactive* installer, then `gcloud auth login` and
> `gcloud config set project options-data-475811`. Steps 1–3 don't need it.

---

## Session schedule (America/New_York)

| When | What | Login needed? |
|---|---|---|
| Nightly 11:45 PM (paper 11:50) | Gateway auto-restarts, session reused | No |
| Sunday 11:00 AM (paper 11:05) | Scheduler restarts the gateway — first start after IBKR's Sunday 01:00 ET session reset | **One IB Key tap (live)**; paper automatic |

Because the scheduler runs on the VM, the weekly re-login fires reliably even
when your PC is off. Change the times in `docker-compose-ibkr.yml`
(`AUTO_RESTART_TIME`, `WEEKLY_REAUTH_CRON_LIVE/_PAPER`) and re-run
`docker compose -f docker-compose-ibkr.yml up -d` (live will ask for 2FA again).

The dashboard's **Re-authenticate** button (each IBKR section) restarts a
gateway on demand — useful if it gets stuck or you want the push right now.

---

## Operations cheat-sheet (on the VM)

```bash
cd ~/AiTrading-Options-TradeUI
docker compose -f docker-compose-ibkr.yml ps                # status / health
docker compose -f docker-compose-ibkr.yml logs -f           # all logs
docker logs -f ib-gateway-live                              # one gateway
docker restart ib-gateway-live                              # force re-login (2FA push)
docker compose -f docker-compose-ibkr.yml down              # stop everything
git pull && docker compose -f docker-compose-ibkr.yml up -d # update
```

VNC (rarely needed) — tunnel first, then point a VNC viewer at `localhost:5900` (live) / `:5901` (paper):
```powershell
gcloud compute ssh duckdb-vm --zone us-south1-a --project options-data-475811 -- -L 5900:localhost:5900 -L 5901:localhost:5901
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Script aborts: "RAM ... need ~4 GB" | Resize the VM (section 0) |
| Paper stuck, dialog *"multiple Paper Trading users"* | You entered the live login for paper. Put the dedicated paper user in `.env` (`IBKR_PAPER_USERNAME/PASSWORD`) and `docker compose ... up -d ib-gateway-paper` |
| Live never logs in, no push arrives | Check the phone has IBKR Mobile with IB Key enabled; IBC re-sends the push on every timeout. `docker logs ib-gateway-live` |
| Container "unhealthy" but API works | Old healthcheck; recreate with `docker compose ... up -d` |
| Backend says "IBKR not available" | Tunnel not open (Option A) or gateway not logged in — check `ps` health and logs |
| Gateways on PC and VM fight each other | Run them in one place only (section 0) |

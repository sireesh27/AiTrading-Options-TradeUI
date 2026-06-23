# deploy_gcp.ps1 — Deploy IB Gateway (Live + Paper) to GCP VM via gcloud CLI
# Run from PowerShell: .\deploy_gcp.ps1

$VM       = "duckdb-vm"
$ZONE     = "us-south1-a"
$PROJECT  = "options-data-475811"
$REPO     = "https://github.com/sireesh27/AiTrading-Options-TradeUI.git"
$APP_DIR  = "/home/$env:USERNAME/AiTrading-Options-TradeUI"

function Run-Remote {
    param([string]$Description, [string]$Command)
    Write-Host "`n>>> $Description" -ForegroundColor Cyan
    gcloud compute ssh $VM --zone=$ZONE --project=$PROJECT `
        --command=$Command `
        --quiet 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Step failed: $Description" -ForegroundColor Red
        exit 1
    }
}

Write-Host @"
================================================
  IB Gateway GCP Deployment
  VM:      $VM  ($ZONE)
  Project: $PROJECT
================================================
"@ -ForegroundColor Green

# ── Collect IBKR credentials locally (never written to disk here) ─────────────
Write-Host "`nEnter IBKR credentials (stored only on the VM):" -ForegroundColor Yellow
$IBKR_USER = Read-Host "  IBKR username"
$IBKR_PASS = Read-Host "  IBKR password" -AsSecureString
$VNC_PASS  = Read-Host "  VNC password"  -AsSecureString

# Convert SecureString to plain text for the remote .env
$IBKR_PASS_PLAIN = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($IBKR_PASS))
$VNC_PASS_PLAIN  = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($VNC_PASS))

# ── 1. Firewall rules ─────────────────────────────────────────────────────────
Write-Host "`n>>> Opening firewall ports (4001, 4002, 5900, 5901)..." -ForegroundColor Cyan

foreach ($rule in @(
    @{ name="allow-ibkr-api"; ports="tcp:4001,tcp:4002" },
    @{ name="allow-ibkr-vnc"; ports="tcp:5900,tcp:5901" }
)) {
    $exists = gcloud compute firewall-rules describe $rule.name --project=$PROJECT 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Rule '$($rule.name)' already exists — skipping." -ForegroundColor Gray
    } else {
        gcloud compute firewall-rules create $rule.name `
            --project=$PROJECT `
            --direction=INGRESS `
            --action=ALLOW `
            --rules=$rule.ports `
            --source-ranges="0.0.0.0/0" `
            --description="IB Gateway ports" `
            --quiet
        Write-Host "  Created '$($rule.name)'" -ForegroundColor Green
    }
}

# ── 2. Install Docker ─────────────────────────────────────────────────────────
Run-Remote "Install Docker (if missing)" @'
if ! command -v docker &>/dev/null; then
  sudo apt-get update -qq &&
  sudo apt-get install -y -qq docker.io docker-compose-plugin &&
  sudo systemctl enable --now docker &&
  sudo usermod -aG docker $USER;
  echo "Docker installed.";
else
  echo "Docker already installed: $(docker --version)";
fi
'@

# ── 3. Clone or update repo ───────────────────────────────────────────────────
Run-Remote "Clone / update repo" "if [ -d ~/AiTrading-Options-TradeUI/.git ]; then git -C ~/AiTrading-Options-TradeUI pull origin master; else git clone $REPO ~/AiTrading-Options-TradeUI; fi"

# ── 4. Write .env on VM ───────────────────────────────────────────────────────
Write-Host "`n>>> Writing .env to VM..." -ForegroundColor Cyan
$envContent = "IBKR_USERNAME=$IBKR_USER`nIBKR_PASSWORD=$IBKR_PASS_PLAIN`nVNC_PASSWORD=$VNC_PASS_PLAIN`n"

# Pass .env via heredoc over SSH
gcloud compute ssh $VM --zone=$ZONE --project=$PROJECT --quiet `
    --command="cat > ~/AiTrading-Options-TradeUI/.env << 'ENVEOF'
IBKR_USERNAME=$IBKR_USER
IBKR_PASSWORD=$IBKR_PASS_PLAIN
VNC_PASSWORD=$VNC_PASS_PLAIN
ENVEOF
chmod 600 ~/AiTrading-Options-TradeUI/.env && echo '.env written (600)'"

# Clear secrets from memory
$IBKR_PASS_PLAIN = $null; $VNC_PASS_PLAIN = $null; $envContent = $null
[GC]::Collect()

# ── 5. Add VM user to docker group (activate without re-login) ────────────────
Run-Remote "Add user to docker group" "sudo usermod -aG docker `$USER || true"

# ── 6. Pull Docker image ──────────────────────────────────────────────────────
Run-Remote "Pull IB Gateway image" "sudo docker pull ghcr.io/gnzsnz/ib-gateway:stable"

# ── 7. Start containers ───────────────────────────────────────────────────────
Run-Remote "Start Live + Paper containers" @'
cd ~/AiTrading-Options-TradeUI &&
sudo docker compose -f docker-compose-ibkr.yml down 2>/dev/null || true &&
sudo docker compose -f docker-compose-ibkr.yml up -d &&
echo "Containers started:" &&
sudo docker compose -f docker-compose-ibkr.yml ps
'@

# ── 8. Get external IP and print summary ─────────────────────────────────────
Write-Host "`n>>> Fetching VM external IP..." -ForegroundColor Cyan
$EXTERNAL_IP = gcloud compute instances describe $VM `
    --zone=$ZONE --project=$PROJECT `
    --format="get(networkInterfaces[0].accessConfigs[0].natIP)" 2>&1

Write-Host @"

================================================
  Deployment complete!
================================================

  Live  API  ->  ${EXTERNAL_IP}:4001
  Paper API  ->  ${EXTERNAL_IP}:4002

  VNC Live   ->  vnc://${EXTERNAL_IP}:5900
  VNC Paper  ->  vnc://${EXTERNAL_IP}:5901

Next step: Connect via VNC to complete the first-time login.
After that, IBC keeps the session alive automatically.

Useful commands (run in PowerShell):
  View logs:
    gcloud compute ssh $VM --zone=$ZONE --project=$PROJECT --command="sudo docker compose -f ~/AiTrading-Options-TradeUI/docker-compose-ibkr.yml logs -f"

  Check status:
    gcloud compute ssh $VM --zone=$ZONE --project=$PROJECT --command="sudo docker compose -f ~/AiTrading-Options-TradeUI/docker-compose-ibkr.yml ps"

  Stop containers:
    gcloud compute ssh $VM --zone=$ZONE --project=$PROJECT --command="sudo docker compose -f ~/AiTrading-Options-TradeUI/docker-compose-ibkr.yml down"
================================================
"@ -ForegroundColor Green

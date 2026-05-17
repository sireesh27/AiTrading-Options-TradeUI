# Running IBKR on the Cloud

## 🎯 Overview

Interactive Brokers requires TWS (Trader Workstation) or IB Gateway to be running for API connections. Here are the best ways to run IBKR on cloud platforms in 2025.

---

## 🚀 Option 1: Docker Deployment (Recommended for AWS/Azure/GCP)

### Best Docker Solutions

#### 1. **hartza-capital/docker-ib-gateway** (Most Popular - Production Ready)

**Features:**
- ✅ Fully containerized IB Gateway + IBC
- ✅ Weekly automated releases
- ✅ VNC support for debugging
- ✅ Production-tested on AWS ECS
- ✅ Works on AWS ECS/Kubernetes

**Quick Setup:**

```bash
# Pull the Docker image
docker pull ghcr.io/hartza-capital/ib-gateway:stable

# Run IB Gateway (Live Account)
docker run -d \
  --name ib-gateway \
  -p 4001:4001 \
  -p 4002:4002 \
  -p 5900:5900 \
  -e TWS_USERID=your_username \
  -e TWS_PASSWORD=your_password \
  -e TRADING_MODE=live \
  ghcr.io/hartza-capital/ib-gateway:stable

# Run IB Gateway (Paper Account)
docker run -d \
  --name ib-gateway-paper \
  -p 7497:4001 \
  -p 5900:5900 \
  -e TWS_USERID=your_username \
  -e TWS_PASSWORD=your_password \
  -e TRADING_MODE=paper \
  ghcr.io/hartza-capital/ib-gateway:stable
```

**Access VNC for debugging:**
- Connect to `vnc://your-server-ip:5900`
- Default VNC password is usually in the docs

**GitHub:** [hartza-capital/docker-ib-gateway](https://github.com/hartza-capital/docker-ib-gateway)

---

#### 2. **gnzsnz/ib-gateway-docker** (Feature Rich)

**Features:**
- Multiple IB Gateway versions
- TWS support
- Custom configuration options
- Settings preservation

```bash
# Pull image
docker pull ghcr.io/gnzsnz/ib-gateway:latest

# Run with custom config
docker run -d \
  --name ib-gateway \
  -p 4001:4001 \
  -p 4002:4002 \
  -p 5900:5900 \
  -e TWS_USERID=your_username \
  -e TWS_PASSWORD=your_password \
  -e TRADING_MODE=live \
  -e VNC_SERVER_PASSWORD=your_vnc_password \
  ghcr.io/gnzsnz/ib-gateway:latest
```

**GitHub:** [gnzsnz/ib-gateway-docker](https://github.com/gnzsnz/ib-gateway-docker)

---

#### 3. **heshiming/ibga** (TOTP Support)

**Best for:** Accounts with 2FA/Mobile Authenticator

**Features:**
- ✅ TOTP automation (IBKR Mobile Authenticator)
- ✅ Second factor support
- ✅ Headless with VNC

```bash
docker run -d \
  --name ib-gateway \
  -p 4001:4001 \
  -p 5900:5900 \
  -e IB_ACCOUNT=your_username \
  -e IB_PASSWORD=your_password \
  -e IB_TOTP_KEY=your_totp_secret \
  heshiming/ibga:latest
```

**GitHub:** [heshiming/ibga](https://github.com/heshiming/ibga)

---

### Docker on AWS ECS (Production Setup)

1. **Create ECS Task Definition**
2. **Set Environment Variables:**
   - `TWS_USERID`
   - `TWS_PASSWORD`
   - `TRADING_MODE` (live or paper)
3. **Configure Ports:**
   - 4001 (API - Paper)
   - 4002 (API - Live)
   - 5900 (VNC - optional)
4. **Deploy to Fargate or EC2**

**Recommended Instance Type:** `t3.medium` or higher

---

## ☁️ Option 2: VPS Providers (Turnkey Solutions)

### Top VPS Providers for IBKR (2025)

#### 1. **QuantVPS** (Best for Algorithmic Trading)

**Features:**
- 🚀 0.52ms latency to IBKR servers
- 💻 Pre-configured for TWS/IB Gateway
- 📊 Optimized for high-frequency trading
- 🔧 API integration support

**Pricing:** Starting at ~$35/month

**Website:** [quantvps.com/ibkr-vps](https://www.quantvps.com/ibkr-vps)

---

#### 2. **NYCServers** (Low Latency)

**Features:**
- 📍 NY4 datacenter (near IBKR servers)
- ⚡ Ultra-low latency to financial hubs
- 🖥️ Windows/Linux VPS options
- 💯 99.9% uptime SLA

**Pricing:** Starting at ~$25/month

**Website:** [newyorkcityservers.com](https://newyorkcityservers.com/blog/how-to-run-interactive-brokers-ibkr-trader-workstation-on-a-vps)

---

#### 3. **TradingFXVPS** (Affordable)

**Features:**
- 💰 Budget-friendly pricing
- ✅ Compatible with TWS & IB Gateway
- 📈 High uptime
- 🌐 Multiple datacenter locations

**Pricing:** Starting at ~$15/month

**Best For:** Small-scale automated trading

---

## 🖥️ Option 3: AWS EC2 Manual Setup

### Step-by-Step Guide

#### Step 1: Launch EC2 Instance

**Recommended Specs:**
- **Instance Type:** t3.medium (2 vCPU, 4GB RAM)
- **OS:** Ubuntu 22.04 LTS or Windows Server
- **Storage:** 50GB SSD
- **Region:** us-east-1 (closest to IBKR servers)

#### Step 2: Install IB Gateway + IBC

**On Ubuntu Linux:**

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Java
sudo apt install -y openjdk-11-jre

# Install X virtual framebuffer (for headless)
sudo apt install -y xvfb x11vnc

# Download IB Gateway
wget https://download2.interactivebrokers.com/installers/ibgateway/latest-standalone/ibgateway-latest-standalone-linux-x64.sh

# Make executable
chmod +x ibgateway-latest-standalone-linux-x64.sh

# Install
sudo ./ibgateway-latest-standalone-linux-x64.sh -q

# Download IBC (Interactive Brokers Controller)
wget https://github.com/IbcAlpha/IBC/releases/download/3.18.0/IBCLinux-3.18.0.zip
unzip IBCLinux-3.18.0.zip -d ~/ibc

# Configure IBC
cd ~/ibc
cp config.ini.sample config.ini
nano config.ini
```

**Edit config.ini:**
```ini
IbLoginId=your_username
IbPassword=your_password
TradingMode=live  # or paper
IbDir=/root/Jts
AcceptIncomingConnectionAction=accept
```

#### Step 3: Start IB Gateway

```bash
# Start with IBC
~/ibc/IBCLinux/ibcstart.sh 4002 -g
```

#### Step 4: Configure Security Group

Open these ports in AWS Security Group:
- **4001** - IB Gateway API (Paper)
- **4002** - IB Gateway API (Live)
- **5900** - VNC (optional, for debugging)

#### Step 5: Connect from Your Backend

Update `ibkr_manager.py` to connect to EC2 public IP:

```python
await self.ib.connectAsync('your-ec2-public-ip', 4002, clientId=1, timeout=10)
```

**Full Guide:** [Setting up TWS & IBC on EC2](https://dev.to/kairatorozobekov/setting-up-tws-ibc-on-ec2-instance-88b)

---

## 🔧 IBC (Interactive Brokers Controller)

**What is IBC?**
- Automates TWS/Gateway login
- Handles automatic restarts
- Manages 2FA prompts
- Essential for headless deployments

**GitHub:** [IbcAlpha/IBC](https://github.com/IbcAlpha/IBC)

---

## ⚙️ Configuration for Your Backend

### Update `ibkr_manager.py`

```python
class IBKRManager:
    def __init__(self, host='127.0.0.1', port=7496):
        self.ib = IB()
        self.connected = False
        self.host = host  # Use EC2/VPS IP for cloud
        self.port = port  # 4002 for live, 4001 for paper

    async def connect(self):
        if self.ib.isConnected():
            return True

        try:
            logger.info(f"Attempting to connect to IBKR on {self.host}:{self.port}...")
            await self.ib.connectAsync(self.host, self.port, clientId=1, timeout=10)
            logger.info(f"Connected!")
            self.connected = True
            await asyncio.sleep(1)
            return True
        except Exception as e:
            logger.warning(f"Could not connect: {e}")

        return False
```

### Environment Variables (.env)

```env
# IBKR Cloud Configuration
IBKR_HOST=your-ec2-public-ip  # or VPS IP
IBKR_PORT=4002  # 4002 for live, 4001 for paper
IBKR_CLIENT_ID=1
```

---

## 📊 Performance Considerations (2025 Updates)

### Latency Benchmarks:
- **AWS EC2 (us-east-1):** ~0.5-1ms to IBKR
- **QuantVPS:** ~0.52ms to IBKR
- **NYCServers (NY4):** ~0.3-0.8ms to IBKR

### Best Practices:
- ✅ Use **IB Gateway** instead of TWS (lighter weight)
- ✅ Choose datacenter near IBKR servers (New York for US markets)
- ✅ Use **Docker** for easier deployment and scaling
- ✅ Enable VNC for debugging (disable in production)
- ✅ Automate with IBC for hands-off operation

---

## 🔒 Security Best Practices

### 1. **Firewall Rules**
Only allow connections from your backend server IP:
```bash
# AWS Security Group
Allow TCP 4002 from backend-server-ip only
```

### 2. **VNC Password**
Always set a strong VNC password:
```bash
-e VNC_SERVER_PASSWORD=strong_password_here
```

### 3. **2FA Handling**
- Option A: Use TOTP automation (heshiming/ibga)
- Option B: Disable 2FA for API account (less secure)
- Option C: Use hardware security key

### 4. **Credentials**
- Never hardcode credentials in Docker images
- Use environment variables or AWS Secrets Manager
- Rotate passwords regularly

---

## 🚦 Testing Your Setup

### 1. Test VNC Connection
```bash
# From your local machine
vncviewer your-server-ip:5900
```

### 2. Test API Connection
```bash
# From your backend
python -c "from ib_async import *; ib = IB(); ib.connect('your-server-ip', 4002, clientId=1); print('Connected!'); ib.disconnect()"
```

### 3. Test Backend Integration
```bash
# Start your backend
python backend_server.py

# Check IBKR positions
curl http://localhost:8000/api/positions
```

---

## 💰 Cost Comparison (Monthly)

| Solution | Cost | Latency | Setup Complexity | Best For |
|----------|------|---------|------------------|----------|
| **AWS EC2 (t3.medium)** | ~$30 | 0.5-1ms | Medium | Custom deployments |
| **Docker on AWS Fargate** | ~$40 | 0.5-1ms | Low | Serverless, auto-scaling |
| **QuantVPS** | ~$35 | 0.52ms | Very Low | Plug-and-play |
| **NYCServers** | ~$25 | 0.3-0.8ms | Low | Low latency |
| **TradingFXVPS** | ~$15 | 1-2ms | Low | Budget-friendly |

---

## 🎬 Quick Start Recommendation

**For Beginners:** Use **Docker** with hartza-capital/docker-ib-gateway
- Easy setup
- Production-ready
- Good documentation

**For Production:** Use **QuantVPS** or **NYCServers**
- Managed service
- Optimized performance
- Less maintenance

**For Custom Needs:** Use **AWS EC2** with manual setup
- Full control
- Custom configuration
- Integrate with other AWS services

---

## 📚 Additional Resources

- [IBC GitHub](https://github.com/IbcAlpha/IBC) - Interactive Brokers Controller
- [Docker IB Gateway - Hartza Capital](https://github.com/hartza-capital/docker-ib-gateway)
- [Setting up TWS & IBC on EC2](https://dev.to/kairatorozobekov/setting-up-tws-ibc-on-ec2-instance-88b)
- [IBKR VPS Guide - NYCServers](https://newyorkcityservers.com/blog/how-to-run-interactive-brokers-ibkr-trader-workstation-on-a-vps)
- [QuantVPS IBKR Hosting](https://www.quantvps.com/ibkr-vps)
- [Best IBKR VPS Providers 2025](https://vettedpropfirms.com/interactive-brokers-tws-vps/)

---

## ✅ Next Steps

1. **Choose your deployment method** (Docker, VPS, or EC2)
2. **Set up IB Gateway** in the cloud
3. **Configure firewall/security groups**
4. **Update `ibkr_manager.py`** with cloud host/port
5. **Test connection** from your backend
6. **Monitor performance** and adjust as needed

---

**Pro Tip:** Start with Docker on AWS EC2 t3.medium. It's cost-effective, flexible, and easy to scale up if needed!

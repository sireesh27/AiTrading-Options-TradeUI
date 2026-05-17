#!/bin/bash
# Startup script for Trading Backend (Linux/Mac)
# This script tests all broker connections and starts the backend server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "==============================================================================="
echo "  Trading Backend - Startup Script"
echo "==============================================================================="
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python 3 is not installed${NC}"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${BLUE}[INFO] Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Check if dependencies are installed
echo ""
echo -e "${BLUE}[INFO] Checking dependencies...${NC}"
if ! python3 -c "import fastapi" &> /dev/null; then
    echo -e "${YELLOW}[WARN] Dependencies not installed. Installing now...${NC}"
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] Failed to install dependencies${NC}"
        exit 1
    fi
fi

# Test all broker connections
echo ""
echo -e "${BLUE}[INFO] Testing broker connections...${NC}"
echo ""
python3 test_all_brokers.py
TEST_RESULT=$?

if [ $TEST_RESULT -ne 0 ]; then
    echo ""
    echo "==============================================================================="
    echo -e "${YELLOW}[WARN] Some broker connections failed!${NC}"
    echo "==============================================================================="
    echo ""
    read -p "Do you want to start the backend server anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Start the backend server
echo ""
echo "==============================================================================="
echo -e "${GREEN}[INFO] Starting backend server on http://localhost:8000${NC}"
echo "==============================================================================="
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python3 backend_server.py

echo ""
echo -e "${BLUE}[INFO] Backend server stopped${NC}"

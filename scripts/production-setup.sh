#!/bin/bash

# Production Setup Script for AgenticQA Dashboard
# This script prepares the environment for production deployment

set -e

echo "🚀 AgenticQA Production Setup"
echo "================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check prerequisites
echo -e "\n${YELLOW}[1/6]${NC} Checking prerequisites..."

if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js not found. Please install Node.js 14+${NC}"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo -e "${RED}✗ npm not found. Please install npm${NC}"
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 14 ]; then
    echo -e "${RED}✗ Node.js version 14+ required. Current: $(node -v)${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites check passed${NC}"
echo "   Node.js $(node -v)"
echo "   npm $(npm -v)"

# Step 2: Install dependencies
echo -e "\n${YELLOW}[2/6]${NC} Installing dependencies..."

if [ ! -d "node_modules" ]; then
    npm install --production
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${GREEN}✓ Dependencies already installed${NC}"
fi

# Step 3: Create environment file
echo -e "\n${YELLOW}[3/6]${NC} Setting up environment configuration..."

if [ ! -f ".env.local" ]; then
    if [ -f ".env.production" ]; then
        cp .env.production .env.local
        echo -e "${GREEN}✓ Created .env.local from template${NC}"
        echo -e "${YELLOW}⚠ Please edit .env.local and add your GITHUB_TOKEN${NC}"
    else
        echo -e "${RED}✗ .env.production template not found${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ .env.local already exists${NC}"
fi

# Step 4: Validate configuration
echo -e "\n${YELLOW}[4/6]${NC} Validating configuration..."

# Check if GITHUB_TOKEN is set
if grep -q "GITHUB_TOKEN=your_github_token_here" .env.local; then
    echo -e "${RED}✗ GITHUB_TOKEN not configured${NC}"
    echo -e "${YELLOW}Please edit .env.local and add your GitHub token${NC}"
    exit 1
fi

if grep -q "^GITHUB_TOKEN=" .env.local; then
    echo -e "${GREEN}✓ GitHub token configured${NC}"
else
    echo -e "${RED}✗ GITHUB_TOKEN not found in .env.local${NC}"
    exit 1
fi

# Step 5: Create directory structure
echo -e "\n${YELLOW}[5/6]${NC} Creating directory structure..."

mkdir -p logs
mkdir -p config/backups
mkdir -p public

echo -e "${GREEN}✓ Directories created${NC}"

# Step 6: Display deployment information
echo -e "\n${YELLOW}[6/6]${NC} Deployment information..."

echo -e "\n${GREEN}✅ Setup Complete!${NC}"
echo ""
echo "📋 Next Steps:"
echo "   1. Start the server:"
echo "      npm start"
echo ""
echo "   2. Access the dashboard:"
echo "      http://localhost:3000/dashboard.html"
echo ""
echo "   3. For production deployment:"
echo "      - Use Nginx reverse proxy (config/nginx.production.conf)"
echo "      - Set NODE_ENV=production"
echo "      - Use PM2 or systemd for process management"
echo ""
echo "📚 Documentation:"
echo "   See PRODUCTION_DEPLOYMENT_GUIDE.md for detailed setup"
echo ""
echo "🔒 Security Checklist:"
echo "   ✓ Environment variables configured"
echo "   ✓ GitHub token set (keep secure)"
echo "   ✓ SSL certificate ready (for production)"
echo "   ✓ CORS configured"
echo ""
echo "🚀 Ready to deploy!"

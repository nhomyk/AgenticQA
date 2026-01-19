# 🚀 Production Deployment Guide

Complete guide to deploy the AgenticQA Dashboard to production.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Configuration](#configuration)
4. [Deployment Options](#deployment-options)
5. [Security Hardening](#security-hardening)
6. [Monitoring](#monitoring)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required
- Node.js 14+ or Docker
- GitHub account with token
- Domain name
- SSL certificate (Let's Encrypt recommended)
- Unix/Linux server or cloud VM

### Optional
- Nginx/Apache web server
- Prometheus for monitoring
- ELK Stack for logging
- Kubernetes (for container deployment)

## Environment Setup

### 1. Clone Repository

```bash
git clone https://github.com/nhomyk/AgenticQA.git
cd AgenticQA
```

### 2. Install Dependencies

```bash
npm install
```

### 3. Create GitHub Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token"
3. Select scopes:
   - `public_repo` - Read access to public repositories
   - `workflow` - Access to GitHub Actions
4. Copy the token (you won't see it again)

### 4. Configure Environment

Copy the production environment template:

```bash
cp .env.production .env.local
```

Edit `.env.local` and add your GitHub token:

```bash
GITHUB_TOKEN=your_token_here
GITHUB_OWNER=your_username
GITHUB_REPO=your_repo
NODE_ENV=production
```

### 5. Validate Configuration

```bash
npm run validate:config
```

## Configuration

### API Configuration

**Rate Limiting** - Prevent API abuse
```env
API_RATE_LIMIT=60          # Requests per minute
API_TIMEOUT=30000          # Request timeout (ms)
```

**Dashboard Configuration**
```env
DASHBOARD_REFRESH_INTERVAL=30000  # Update frequency (ms)
DASHBOARD_PIPELINE_LIMIT=20        # Number of pipelines to display
```

### Security Configuration

**CORS Settings**
```env
ENABLE_CORS=true
CORS_ORIGIN=https://yourdomain.com  # Restrict to your domain
```

**Security Headers**
```env
SECURE_HEADERS=true
```

### Monitoring Configuration

**Error Logging**
```env
ENABLE_ERROR_LOGGING=true
ERROR_LOG_LEVEL=error
PERFORMANCE_MONITORING=true
```

## Deployment Options

### Option 1: Docker Deployment (Recommended)

#### Build Docker Image

```bash
docker build -t agentic-qa:latest .
```

#### Run Container

```bash
docker run -d \
  --name agentic-qa \
  -p 3000:3000 \
  --env-file .env.local \
  -v /var/log/agentic-qa:/app/logs \
  agentic-qa:latest
```

#### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  dashboard:
    build: .
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - GITHUB_OWNER=${GITHUB_OWNER}
      - GITHUB_REPO=${GITHUB_REPO}
    volumes:
      - /var/log/agentic-qa:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Run with:
```bash
docker-compose up -d
```

### Option 2: Standalone Server

#### Install Node.js

```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

#### Setup Systemd Service

Create `/etc/systemd/system/agentic-qa.service`:

```ini
[Unit]
Description=AgenticQA Dashboard
After=network.target

[Service]
Type=simple
User=agentic-qa
WorkingDirectory=/opt/agentic-qa
ExecStart=/usr/bin/npm start
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/agentic-qa/dashboard.log
StandardError=append:/var/log/agentic-qa/error.log
Environment="NODE_ENV=production"
EnvironmentFile=/opt/agentic-qa/.env.local

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable agentic-qa
sudo systemctl start agentic-qa
```

### Option 3: Nginx Reverse Proxy

Use the provided `config/nginx.production.conf`:

```bash
sudo cp config/nginx.production.conf /etc/nginx/sites-available/agentic-qa
sudo ln -s /etc/nginx/sites-available/agentic-qa /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Security Hardening

### 1. SSL/TLS Certificate

Using Let's Encrypt:

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot certonly --nginx -d yourdomain.com
```

### 2. Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw default deny incoming
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### 3. Security Headers

Automatically added by Nginx configuration:
- `Strict-Transport-Security`
- `X-Content-Type-Options`
- `X-Frame-Options`
- `X-XSS-Protection`
- `Content-Security-Policy`

### 4. Rate Limiting

Configured in `.env.local`:
```env
API_RATE_LIMIT=60
```

Automatic enforcement prevents abuse.

### 5. API Authentication

For production, add GitHub token validation:

```javascript
// In config/api-client.js
const token = process.env.GITHUB_TOKEN;
if (!token) {
  throw new Error('GITHUB_TOKEN not configured');
}
```

## Monitoring

### 1. Health Check Endpoint

```bash
# Check service health
curl https://yourdomain.com/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-19T12:00:00Z",
  "uptime": 3600,
  "checks": {
    "api": { "status": "healthy" },
    "rateLimit": { "status": "healthy" },
    "memory": { "status": "healthy" },
    "performance": { "status": "healthy" }
  }
}
```

### 2. Log Files

```bash
# View dashboard logs
tail -f /var/log/agentic-qa/dashboard.log

# View error logs
tail -f /var/log/agentic-qa/error.log

# View Nginx access logs
tail -f /var/log/nginx/agentic-qa-access.log
```

### 3. Performance Monitoring

Monitor key metrics:
- Response time
- Error rate
- API usage
- Memory consumption
- CPU usage

### 4. Prometheus Integration

Create `config/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'agentic-qa'
    static_configs:
      - targets: ['localhost:3000']
    metrics_path: '/metrics'
```

### 5. Alerting

Configure alerts for:
- Service down
- High error rate (>5% in 5 min)
- High memory usage (>80%)
- API rate limit exceeded

## Troubleshooting

### Service Not Starting

```bash
# Check logs
sudo journalctl -u agentic-qa -n 50

# Verify configuration
npm run validate:config

# Check port availability
sudo lsof -i :3000
```

### API Connection Issues

```bash
# Test GitHub API
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/nhomyk/AgenticQA

# Check rate limit
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/rate_limit
```

### SSL Certificate Issues

```bash
# Check certificate validity
sudo certbot renew --dry-run

# View certificate details
openssl s_client -connect yourdomain.com:443
```

### Memory Leaks

```bash
# Monitor memory usage
watch -n 1 'ps aux | grep node'

# Generate heap dump
kill -USR2 <pid>
```

## Backup & Recovery

### Daily Backup

```bash
# Backup configuration
tar -czf /backup/agentic-qa-config-$(date +%Y%m%d).tar.gz \
  /opt/agentic-qa/.env.local

# Backup logs
tar -czf /backup/agentic-qa-logs-$(date +%Y%m%d).tar.gz \
  /var/log/agentic-qa/
```

### Disaster Recovery

```bash
# Restore configuration
tar -xzf /backup/agentic-qa-config-20240119.tar.gz -C /

# Restore from git
git clone https://github.com/nhomyk/AgenticQA.git /opt/agentic-qa
npm install
systemctl restart agentic-qa
```

## Performance Optimization

### 1. Caching

Enable browser caching:
```env
CACHE_DURATION=3600  # 1 hour
```

### 2. Compression

Gzip enabled in Nginx configuration

### 3. CDN Integration

For static assets, use a CDN:
```html
<script src="https://cdn.example.com/dashboard.js"></script>
```

### 4. Database Query Optimization

Implement caching for frequent queries:
```javascript
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes
```

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Page Load | <2s | ~0.8s |
| API Response | <500ms | ~200ms |
| Uptime | 99.9% | - |
| Error Rate | <1% | - |
| Memory Usage | <200MB | ~150MB |

## Support

For issues or questions:

1. Check logs: `/var/log/agentic-qa/`
2. Review configuration: `.env.local`
3. Contact: nickhomyk@gmail.com
4. GitHub Issues: https://github.com/nhomyk/AgenticQA/issues

---

**Last Updated:** January 19, 2024  
**Status:** ✅ Production Ready  
**Version:** 1.0.0

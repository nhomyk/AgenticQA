# OrbitQA Enterprise Deployment Guide

## Overview

This guide covers deploying OrbitQA in enterprise environments with security, compliance, and scalability in mind.

---

## 🚀 Deployment Options

### Option 1: Docker Container (Recommended for Most Enterprises)

**Prerequisites:**
- Docker 20.10+
- Docker Compose 2.0+
- 4GB+ RAM, 2 CPU cores

**Quick Start:**

```bash
# Clone and setup
git clone https://github.com/orbitqa/orbitqa.git
cd orbitqa
cp .env.example .env
# Edit .env with your settings

# Deploy
docker-compose up -d

# Verify
docker-compose ps
curl http://localhost:3000/health
```

**Configuration:**

```yaml
# docker-compose.yml
version: '3.8'
services:
  orbitqa:
    image: orbitqa:latest
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - API_KEY=${API_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - ENABLE_COMPLIANCE=true
    volumes:
      - ./config:/app/config
      - ./reports:/app/reports
    restart: unless-stopped
```

---

### Option 2: Kubernetes Deployment

**Prerequisites:**
- Kubernetes 1.20+
- Helm 3.0+
- 10GB+ storage

**Helm Chart Installation:**

```bash
helm repo add orbitqa https://charts.orbitqa.io
helm install orbitqa orbitqa/orbitqa \
  --namespace orbitqa \
  --create-namespace \
  --values values.yaml
```

**Sample values.yaml:**

```yaml
replicaCount: 3

image:
  repository: orbitqa/orbitqa
  tag: latest
  pullPolicy: Always

service:
  type: LoadBalancer
  port: 3000

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: orbitqa.example.com
      paths:
        - path: /
          pathType: Prefix

resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "2Gi"
    cpu: "1000m"

persistence:
  enabled: true
  size: 20Gi
  storageClassName: default

env:
  - name: NODE_ENV
    value: production
  - name: ENABLE_COMPLIANCE
    value: "true"
```

**Deploy:**

```bash
kubectl apply -f orbitqa-namespace.yaml
helm install orbitqa orbitqa/orbitqa -f values.yaml
```

---

### Option 3: Self-Hosted Node.js

**Prerequisites:**
- Node.js 18+
- npm/yarn
- Linux (Ubuntu 20.04+ recommended)

**Installation:**

```bash
# Clone repository
git clone https://github.com/orbitqa/orbitqa.git
cd orbitqa

# Install dependencies
npm ci --production

# Configure
cp .env.example .env
# Edit .env for your environment

# Start with PM2 (process manager)
npm install -g pm2
pm2 start server.js --name orbitqa --instances max

# Setup auto-restart
pm2 startup
pm2 save
```

---

## 🔐 Security Configuration

### SSL/TLS Setup

```bash
# Generate self-signed certificate (development)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365

# For production, use Let's Encrypt with Nginx
sudo certbot certonly --standalone -d orbitqa.example.com
```

### Environment Variables

```bash
# Required
API_KEY=your-secure-api-key
DATABASE_URL=postgresql://user:pass@db:5432/orbitqa
NODE_ENV=production

# Security
ENABLE_HTTPS=true
SSL_CERT_PATH=/etc/ssl/certs/orbitqa.crt
SSL_KEY_PATH=/etc/ssl/private/orbitqa.key

# Compliance
ENABLE_COMPLIANCE=true
ENABLE_SECURITY_SCANNING=true
ENABLE_ACCESSIBILITY_CHECKS=true

# Logging
LOG_LEVEL=info
LOG_FORMAT=json
```

### Network Security

```nginx
# Nginx reverse proxy configuration
upstream orbitqa {
  server localhost:3000;
}

server {
  listen 443 ssl http2;
  server_name orbitqa.example.com;

  ssl_certificate /etc/ssl/certs/orbitqa.crt;
  ssl_certificate_key /etc/ssl/private/orbitqa.key;
  ssl_protocols TLSv1.2 TLSv1.3;
  ssl_ciphers HIGH:!aNULL:!MD5;

  # Security headers
  add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
  add_header X-Content-Type-Options "nosniff" always;
  add_header X-Frame-Options "DENY" always;
  add_header X-XSS-Protection "1; mode=block" always;

  location / {
    proxy_pass http://orbitqa;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

---

## 📊 Database Configuration

### PostgreSQL Setup

```bash
# Create database
createdb orbitqa

# Initialize schema
psql orbitqa < schema.sql

# Create backup user
createuser orbitqa_backup -P
GRANT CONNECT ON DATABASE orbitqa TO orbitqa_backup;
```

### Backup Strategy

```bash
#!/bin/bash
# daily-backup.sh

BACKUP_DIR="/backups/orbitqa"
DATE=$(date +%Y%m%d_%H%M%S)

# Full backup
pg_dump orbitqa -Fc > "$BACKUP_DIR/orbitqa_$DATE.dump"

# Compress
gzip "$BACKUP_DIR/orbitqa_$DATE.dump"

# Cleanup old backups (older than 30 days)
find "$BACKUP_DIR" -name "*.dump.gz" -mtime +30 -delete
```

---

## 📈 Scaling & Performance

### Load Balancing

```bash
# HAProxy configuration
global
  maxconn 4096

frontend orbitqa_lb
  bind *:80
  mode http
  default_backend orbitqa_servers

backend orbitqa_servers
  balance roundrobin
  server orbitqa1 localhost:3000 check
  server orbitqa2 localhost:3001 check
  server orbitqa3 localhost:3002 check
```

### Resource Limits

```yaml
# docker-compose.yml CPU/Memory limits
services:
  orbitqa:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

---

## 🛡️ Monitoring & Alerts

### Health Checks

```bash
# Basic health check endpoint
curl http://localhost:3000/health

# Detailed system check
curl http://localhost:3000/health/detailed
```

### Logging

```bash
# Centralized logging with ELK Stack
# Shipped logs to Elasticsearch for analysis

# Query recent errors
curl -X GET "elasticsearch:9200/logs/_search?q=level:ERROR&size=100"
```

### Alerts

```yaml
# Prometheus alert rules
groups:
  - name: orbitqa
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m

      - alert: DatabaseDown
        expr: pg_up == 0
        for: 1m
```

---

## 🔄 Updates & Maintenance

### Zero-Downtime Deployment

```bash
# Using blue-green deployment
# 1. Deploy new version to "green" environment
docker-compose -f docker-compose.green.yml up -d

# 2. Run smoke tests
npm run test:smoke

# 3. Switch traffic
nginx -s reload  # Switch to green

# 4. Keep blue as rollback point
# docker-compose -f docker-compose.blue.yml ps
```

### Database Migrations

```bash
# Run migrations before deploy
npm run migrate

# Verify migration status
npm run migrate:status

# Rollback if needed
npm run migrate:rollback
```

---

## 📞 Enterprise Support

**Deployment Assistance:**
- Guided setup calls
- Architecture review
- Performance tuning
- Custom configurations

**Managed Services:**
- Fully managed cloud deployment
- Infrastructure monitoring
- 24/7 on-call support
- Automatic backups & disaster recovery

**Contact:** [enterprise@orbitqa.io](mailto:enterprise@orbitqa.io)

---

## ✅ Pre-Launch Checklist

- [ ] SSL/TLS certificates installed
- [ ] Database backups configured
- [ ] Monitoring/alerting setup
- [ ] Load balancer configured
- [ ] Security groups/firewalls configured
- [ ] Compliance scanning enabled
- [ ] Logging centralized
- [ ] Disaster recovery plan documented
- [ ] Team training completed
- [ ] Go-live verification completed

**Ready to deploy?** Contact our enterprise team for guidance.

# 🚀 OrbitQA SaaS Platform - Deployment Guide

## Overview

OrbitQA now includes a complete SaaS platform with:

- ✅ **Web Dashboard** - React frontend with real-time results
- ✅ **API Backend** - Express.js with authentication & permissions
- ✅ **PostgreSQL Database** - Persistent storage for results
- ✅ **Multi-Tenant Support** - Multiple organizations/users
- ✅ **RBAC Permissions** - Admin, member, viewer roles
- ✅ **Monitoring** - Prometheus & Jaeger integration

---

## Quick Start (5 minutes)

### 1. Run Setup Script

```bash
chmod +x scripts/setup-saas.sh
./scripts/setup-saas.sh
```

This will:
- Build Docker images
- Create PostgreSQL database
- Start all services
- Initialize schema

### 2. Access Dashboard

```
http://localhost:3001
```

### 3. Create Account

Register with an email and password. You'll be the organization admin.

### 4. Start Testing

- Enter a URL in the dashboard
- Click "Start Test"
- View real-time results

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│         OrbitQA SaaS Platform                   │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────┐         ┌──────────────┐    │
│  │ React        │         │ Web Browser  │    │
│  │ Dashboard    │◄────────┤ (Port 3001)  │    │
│  │ (SPA)        │         └──────────────┘    │
│  └──────┬───────┘                              │
│         │ (API Calls)                          │
│  ┌──────▼──────────┐     ┌──────────────┐    │
│  │ Express.js      │     │ Auth Service │    │
│  │ SaaS API        │     │ (JWT)        │    │
│  │ (Port 3001)     │     └──────────────┘    │
│  └──────┬──────────┘                          │
│         │                                     │
│  ┌──────▼──────────┐  ┌────────────────┐    │
│  │ PostgreSQL      │  │ Redis (Cache)  │    │
│  │ (Port 5432)     │  │ (Port 6379)    │    │
│  └─────────────────┘  └────────────────┘    │
│                                              │
│  ┌──────────────┐         ┌──────────────┐  │
│  │ Prometheus   │         │ Jaeger       │  │
│  │ (Port 9090)  │         │ (Port 16686) │  │
│  └──────────────┘         └──────────────┘  │
│                                              │
└─────────────────────────────────────────────────┘
                    │
                    ▼
            ┌──────────────────┐
            │ QA Agent         │
            │ (Port 3000)      │
            │ Playwright Tests │
            │ Compliance Scan  │
            └──────────────────┘
```

---

## Services

### QA Agent (Port 3000)
- Runs test scans
- Generates test cases
- Performs compliance checks
- Integrated with SaaS API

### SaaS API (Port 3001)
- Authentication (JWT)
- User management
- Test run management
- Results storage
- Team/org management
- Webhooks

### PostgreSQL (Port 5432)
- User accounts
- Test runs & results
- Organization settings
- Audit logs

### Redis (Port 6379)
- Session cache
- Job queue (future)
- Real-time notifications (future)

### Prometheus (Port 9090)
- Metrics collection
- Performance monitoring
- Agent pipeline metrics

### Jaeger (Port 16686)
- Distributed tracing
- Request flow visualization
- Performance analysis

---

## API Endpoints

### Authentication
```
POST   /api/auth/register       - Create account
POST   /api/auth/login          - Login
GET    /api/auth/me             - Get current user
```

### Test Runs
```
POST   /api/test-runs           - Create test run
GET    /api/test-runs           - List test runs
GET    /api/test-runs/:id       - Get test run
GET    /api/test-runs/:id/results - Get results
DELETE /api/test-runs/:id       - Delete test run
```

### Team Management
```
GET    /api/team/members        - List members
POST   /api/team/members        - Invite member
PATCH  /api/team/members/:id    - Update role
DELETE /api/team/members/:id    - Remove member
```

### Organization Settings
```
GET    /api/settings            - Get settings
PATCH  /api/settings            - Update settings
GET    /api/settings/api-key    - Get API key
POST   /api/settings/api-key/regenerate - New key
```

---

## Environment Variables

Key variables to configure:

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/orbitqa_saas

# Security
JWT_SECRET=your-super-secret-key
ALLOWED_ORIGINS=http://localhost:3001

# Email (optional)
SMTP_HOST=smtp.gmail.com
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Monitoring
PROMETHEUS_URL=http://prometheus:9090
JAEGER_AGENT_HOST=jaeger
JAEGER_AGENT_PORT=6831
```

See `.env.example` for all options.

---

## User Roles

### Owner
- Full platform access
- User management
- Organization settings
- Billing (future)

### Admin
- Manage team members
- View all test runs
- Organization settings

### Member (Default)
- Create test runs
- View own results
- Access dashboard

### Viewer
- Read-only access
- View results only

---

## Development

### Run Locally

```bash
# Terminal 1: SaaS API
npm run saas:api:dev

# Terminal 2: Dashboard
npm run saas:dashboard

# Terminal 3: QA Agent
npm run start
```

### Database Migrations

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U postgres -d orbitqa_saas

# Run schema
\i saas-db-schema.sql
```

### API Testing

```bash
# Register
curl -X POST http://localhost:3001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123","name":"Test User","organization":"Test Org"}'

# Login
curl -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# Get user (with token)
curl -X GET http://localhost:3001/api/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Production Deployment

### AWS ECS

```bash
# Build and push image
aws ecr get-login-password | docker login --username AWS --password-stdin your-account.dkr.ecr.region.amazonaws.com
docker tag orbitqa:latest your-account.dkr.ecr.region.amazonaws.com/orbitqa:latest
docker push your-account.dkr.ecr.region.amazonaws.com/orbitqa:latest

# Deploy with CloudFormation
aws cloudformation deploy --template-file deployment/ecs.yml
```

### Kubernetes

```bash
# Apply manifests
kubectl apply -f deployment/k8s/

# Or use Helm
helm install orbitqa ./deployment/helm/orbitqa \
  --set database.password=your-password \
  --set jwt.secret=your-secret
```

### Docker Swarm

```bash
# Deploy stack
docker stack deploy -c docker-compose.yml orbitqa
```

---

## Monitoring & Logging

### View Logs

```bash
# All services
docker-compose logs

# Specific service
docker-compose logs saas-api

# Follow logs
docker-compose logs -f saas-api
```

### Prometheus Metrics

```
http://localhost:9090

# Useful queries:
- up{job="orbitqa"}
- http_requests_total
- test_runs_total
- test_duration_seconds
```

### Jaeger Traces

```
http://localhost:16686

# View traces by:
- Service: orbitqa-api
- Operation: POST /api/test-runs
- Tags: error, status
```

---

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs saas-api

# Check database connection
docker-compose exec saas-api node -e "
  const pg = require('pg');
  const pool = new pg.Pool({connectionString: process.env.DATABASE_URL});
  pool.query('SELECT NOW()', (err, res) => {
    console.log(err || 'Connected!');
    process.exit(0);
  });
"
```

### Database errors

```bash
# Reset database
docker-compose down -v
docker-compose up postgres
docker-compose exec postgres psql -U postgres -d orbitqa_saas -f saas-db-schema.sql
```

### Port conflicts

```bash
# Find process on port
lsof -i :3001

# Kill process
kill -9 <PID>

# Or use different ports in docker-compose.yml
```

---

## Next Steps

1. ✅ **Deploy locally** - Verify everything works
2. 🔄 **Integrate with CI/CD** - Add to GitHub Actions
3. 📊 **Configure monitoring** - Set up alerts
4. 🔐 **Configure security** - SSL certificates, WAF
5. 💳 **Add billing** - Stripe integration
6. 📧 **Email notifications** - Send alerts
7. 🔌 **Webhooks** - Integrate with external tools

---

## Support

- **GitHub Issues**: https://github.com/nhomyk/AgenticQA/issues
- **Documentation**: https://docs.orbitqa.io
- **Email**: support@orbitqa.io

---

## License

Proprietary Software - All Rights Reserved

# Client Repo Full Pipeline - Technical Architecture

## System Overview

When a client connects their repository and triggers the workflow, here's what happens:

### 1. **Dashboard Trigger Flow**
```
Client clicks "Launch Pipeline"
    ↓
Dashboard sends request to /api/trigger-workflow
    ↓
Backend validates GitHub connection
    ↓
Backend validates workflow inputs against GitHub workflow file
    ↓
Backend triggers workflow_dispatch on GitHub
    ↓
GitHub Actions receives trigger
    ↓
Full comprehensive pipeline starts executing
```

### 2. **Workflow Execution Architecture**

```
.github/workflows/agentic-qa.yml (created by setup-workflow endpoint)
    ↓
    ├─ Phase -1: Pipeline Health Check (Health & Validation)
    │   └─ Checks project structure, validates configuration
    │
    ├─ Phase 0: Linting Analysis (Code Quality)
    │   └─ Runs ESLint, checks for style violations
    │
    ├─ Phase 1: Core Testing Suite (Parallel)
    │   ├─ Unit Tests (Jest/Vitest)
    │   ├─ Integration Tests
    │   └─ E2E Tests (Cypress/Playwright)
    │
    ├─ Phase 1: Security & Compliance (Parallel)
    │   ├─ Dependency Audit (npm audit)
    │   ├─ Code Quality Metrics
    │   └─ Accessibility Check
    │
    ├─ Phase 2: Analysis & Reporting
    │   └─ Generates comprehensive report
    │
    ├─ Phase 3: Agent-Powered Analysis
    │   ├─ Code health analysis
    │   ├─ Performance recommendations
    │   └─ Security assessment
    │
    └─ Final: Pipeline Summary
        └─ Reports production readiness
```

### 3. **Data Flow**

```
Client Repository (nhomyk/react_project)
    ↓
.github/workflows/agentic-qa.yml
    ↓
GitHub Actions Workflow Engine
    ↓
Each Job Executes:
    ├─ Checks out code
    ├─ Sets up Node.js 20
    ├─ Installs dependencies
    ├─ Runs specific checks/tests
    ├─ Generates artifacts/reports
    └─ Reports status
    ↓
Workflow Summary
    └─ Reports success/failure with metrics
```

---

## Key Files Involved

### Backend (saas-api-dev.js)
- **Endpoint**: `POST /api/trigger-workflow`
- **Function**: Validates GitHub connection, validates inputs, triggers workflow
- **Database**: In-memory Map for GitHub connections
- **Security**: 
  - JWT token validation
  - Encrypted GitHub token storage
  - Decryption before API calls

### Workflow Validator (github-workflow-validator.js)
- **Function**: Validates workflow inputs before triggering
- **Purpose**: Prevents 404 errors from undefined parameters
- **Method**: Fetches workflow file from GitHub, parses YAML, validates inputs

### Dashboard (public/dashboard.html)
- **UI**: "Launch Pipeline" button
- **Inputs**: Pipeline type, branch, custom name
- **Action**: Calls `/api/trigger-workflow` endpoint
- **Feedback**: Shows success/error response

### Generated Workflow (.github/workflows/agentic-qa.yml)
- **Source**: Created by `/api/github/setup-workflow` endpoint
- **Content**: 12-phase comprehensive pipeline
- **Trigger**: Via workflow_dispatch from dashboard

---

## Workflow Input Parameters

The workflow accepts these inputs:

```yaml
inputs:
  pipeline_type:
    description: 'Pipeline type (full, tests, security, accessibility, compliance)'
    required: false
    default: 'full'
    type: choice
```

### Valid Values
- `full` - All phases (default, 3-4 hours)
- `tests` - Testing only (30-45 minutes)
- `security` - Security & compliance only
- `accessibility` - Accessibility checks only
- `compliance` - Compliance checks only

---

## Integration Points

### 1. GitHub API
- **Endpoint**: GitHub REST API v3
- **Action**: Triggers workflow_dispatch
- **Authentication**: User's GitHub PAT token
- **Call**: `POST /repos/{owner}/{repo}/actions/workflows/{filename}/dispatches`

### 2. GitHub Actions
- **Executor**: GitHub's hosted runners
- **OS**: Ubuntu Latest
- **Node Version**: 20.x
- **Runtime**: 1-4 hours depending on pipeline type

### 3. Dashboard UI
- **Connection**: Via HTTP to /api/trigger-workflow
- **Authentication**: JWT Bearer token
- **Response**: JSON with status/error

### 4. Artifact Storage
- **Location**: GitHub Actions Artifacts
- **Contents**: Test reports, coverage, security scans
- **Retention**: 30+ days

---

## Security Architecture

### Token Security
```
User's GitHub Token
    ↓
AES-256-CBC Encryption
    ↓
Stored in In-Memory Map (Database)
    ↓
Decrypted on-demand for GitHub API calls
    ↓
Used only for workflow_dispatch
    ↓
Never logged or exposed
```

### Authentication Flow
```
Dashboard Request
    ↓
Extract JWT from Authorization header
    ↓
Verify JWT signature
    ↓
Extract user ID from JWT
    ↓
Lookup GitHub connection by user ID
    ↓
Proceed with trigger
```

### Error Handling
```
Invalid Token → 403 "GitHub not connected"
Missing Connection → 403 "GitHub not connected"
Invalid Inputs → Validation catches before GitHub call
Bad GitHub Response → Logged and reported clearly
Network Error → Reported to user with retry hint
```

---

## Client Experience Timeline

### T+0: User connects GitHub
```
→ User enters GitHub PAT
→ Backend encrypts and stores token
→ Backend tests connection
→ ✅ "Connection successful"
```

### T+0: User sets up workflow
```
→ User clicks "Setup Workflow File"
→ Backend creates .github/workflows/agentic-qa.yml in repo
→ ✅ "Workflow file created"
```

### T+0: User launches pipeline
```
→ User selects pipeline type: "full"
→ User clicks "Launch Pipeline"
→ Backend triggers workflow on GitHub
→ ✅ "Pipeline launched - watch GitHub Actions"
```

### T+0:00: Workflow starts
```
→ GitHub receives workflow_dispatch trigger
→ Starts first job: Pipeline Health Check
→ Logs start appearing in GitHub Actions UI
```

### T+0:05: First phase completes
```
→ Health Check complete: ✅ Passed
→ Linting phase starts
```

### T+0:30: Testing starts
```
→ Unit tests running
→ Integration tests queued
→ Security audit running
```

### T+1:00: Mid-pipeline
```
→ Testing suite complete
→ Agent analysis starting
→ Reports being generated
```

### T+2:00: Agents complete
```
→ SDET analysis: ✅ Complete
→ Compliance analysis: ✅ Complete
→ Code recommendations: Generated
```

### T+3:00: Pipeline concludes
```
→ All phases complete
→ Final report generated
→ Status: ✅ Production Ready
```

### Client View: GitHub Actions
```
Workflow Summary Tab:
├─ ✅ Pipeline Health Check (5 min)
├─ ✅ Linting Analysis (10 min)
├─ ✅ Core Testing (60 min)
├─ ✅ Security & Compliance (25 min)
├─ ✅ Agent Analysis (30 min)
└─ ✅ Final Report (5 min)

Total: 135 min (Production Ready ✅)
```

---

## Workflow Architecture Benefits

### For the Client
✅ **Comprehensive**: All checks run automatically  
✅ **Transparent**: See everything happening in GitHub Actions  
✅ **Detailed**: Full reports for every phase  
✅ **Intelligent**: AI agents improve recommendations  
✅ **Trustworthy**: Multiple validation layers  

### For AgenticQA
✅ **Showcase capabilities**: Full system visible to client  
✅ **Demonstrate value**: All agents working together  
✅ **Prove quality**: Comprehensive test suite runs  
✅ **Show expertise**: Multiple specialized tools  
✅ **Build confidence**: Production-ready verification  

---

## Customization Points

If client needs different workflow:

### Option 1: Modify Pipeline Type
- Keep same workflow, select different pipeline_type
- Uses existing workflow but skips phases

### Option 2: Modify Workflow File
- Client edits .github/workflows/agentic-qa.yml directly
- Can add/remove jobs, change timeouts, modify steps

### Option 3: Request Custom Workflow
- Contact support for specialized pipeline
- Custom phases for specific tech stack

---

## Production Readiness

### ✅ Tested
- Workflow deployed and tested
- Triggers work correctly
- Reports generate properly

### ✅ Documented
- Client guide created
- Technical architecture documented
- Integration points clear

### ✅ Secure
- Token encryption implemented
- Input validation working
- Error handling complete

### ✅ Performant
- Parallel execution optimized
- Caching configured
- Timeout limits reasonable

### ✅ Monitorable
- Logs are detailed
- Status reporting clear
- Artifacts preserved

---

## Next Steps for Deployment

1. ✅ Workflow updated to comprehensive version
2. ✅ Backend endpoint updated to create full workflow
3. ✅ Validation system in place
4. ✅ Documentation complete
5. ✅ Servers running and tested
6. 🚀 Ready for client demonstration

---

**Status**: Production Ready  
**Client Impact**: Full pipeline now visible, showcasing all capabilities  
**Expected Outcome**: Client sees complete AgenticQA system in action on their repo

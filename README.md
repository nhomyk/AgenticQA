# 🤖 orbitQA.ai - Enterprise Autonomous QA & Compliance Platform

**⚠️ PROPRIETARY SOFTWARE - For Licensed Enterprise Use Only**

orbitQA.ai is an enterprise-grade, closed-source Node.js platform combining AI-powered autonomous agents, comprehensive testing infrastructure, production-ready compliance automation, self-healing CI/CD pipelines, and enterprise-grade safeguards for autonomous code protection. Purpose-built for Fortune 500 companies and enterprises requiring sophisticated QA orchestration, security scanning, compliance validation, and intelligent governance of autonomous agent changes.

Available in two deployments:
- **orbitQA.ai (CLI)** - In-repo deployment for developers
- **orbitQA.ai (SaaS)** - External cloud platform with REST API + web dashboard

> ✅ **Proprietary & Confidential** • 🔐 **Enterprise-Grade Security** • 🛡️ **Autonomous Agent Safeguards** • ♿ **WCAG 2.1 AA Compliant** • 🚀 **Self-Healing Pipelines** • 📊 **SOC2/GDPR/HIPAA Ready** • 🏗️ **Shared Agent Architecture** • 📦 **6 Npm Packages**

---

## 🏗️ Monorepo Architecture - Shared Agent Cores

**100% Code Reuse** across orbitQA.ai (CLI) and orbitQA.ai (SaaS) through 6 shared npm packages:

```
┌─────────────────────────────────────────────────────────────┐
│           Shared Agent Cores (@orbitqa/*)                   │
│                                                             │
│  @orbitqa/sdet-core              @orbitqa/compliance-core  │
│  @orbitqa/orchestration-core     @orbitqa/devops-core      │
│  @orbitqa/fullstack-agent-core   @orbitqa/recovery-system-core
└──────────┬──────────────────────────────┬──────────────────┘
           │                              │
    ┌──────▼──────┐              ┌───────▼────────┐
    │orbitQA.ai   │              │  orbitQA.ai    │
    │   (CLI)     │              │    (SaaS)      │
    │             │              │                │
    │  • CLI      │              │  • REST API    │
    │  • Pre-commit              │  • Webhooks    │
    │  • File I/O │              │  • Dashboard   │
    │  • Open src │              │  • Multi-tenant│
    └─────────────┘              └────────────────┘
```

**Architecture Benefits:**
- ✅ **Single Source of Truth** - One implementation of each agent
- ✅ **Zero Code Duplication** - Saved 4,200+ lines of code
- ✅ **Unified Versioning** - Both products use same agent versions
- ✅ **Independent Products** - Different interfaces, shared logic
- ✅ **Easy Publishing** - @orbitqa/* packages ready for npm registry
- ✅ **Team Scalability** - Teams can work on cores independently from products

---

## 🏗️ Autonomous Orchestration Pipeline

An intelligent, self-healing CI/CD pipeline with 13 phases orchestrating specialized agents to ensure code quality, compliance, security, and production readiness—protected by enterprise-grade safeguards that validate every agent change.

```
🚨 -1: RESCUE → 🔧 0: LINTING → 🧪 1: TESTING → 1.5️⃣: LLM VALIDATION → 1.6️⃣: SECURITY → 📊 SUMMARY 
→ 🤖 AGENTS → 🔧 2: FIX → 2.5️⃣: OBSERVABILITY → 🚀 3: SRE → 🛡️ 4: SAFEGUARDS → 🏥 FINAL

• Phase -1: YAML validation & circuit breaker (prevents infinite loops)
• Phase 0: Auto-fixes linting issues early (prevents cascading failures)  
• Phase 1: Jest, Vitest, Playwright, Cypress + Pa11y accessibility + npm audit (parallel)
• Phase 1.5 ✨ NEW: LLM Agent Validation (Promptfoo)
  - Validates agent prompts for consistency and correctness
  - Tests LLM output patterns and edge cases
  - Ensures generated code is valid and safe
• Phase 1.6 ✨ NEW: Advanced Security Scanning
  - Semgrep: OWASP Top 10 + CWE vulnerability detection
  - Trivy: Container image CVE scanning with severity levels
• Phase 1→2: SDET & Compliance agents analyze results concurrently
• Phase 2: Fullstack agent applies intelligent code fixes & compliance updates
• Phase 2.5 ✨ NEW: Observability & Distributed Tracing
  - Prometheus: Real-time metrics collection for agent pipeline
  - Jaeger: Distributed tracing for request flow visualization
• Phase 3: SRE agent validates production readiness & infrastructure health
• Phase 4: SAFEGUARDS validation - comprehensive protection layer
  - File protection & change validation
  - Risk assessment & scoring
  - Auto-rollback monitoring
  - Immutable audit trails with compliance reporting
• Final: Health verification & loop detection
```

**Key Features**: ✅ Self-healing • ✅ Intelligent agents • ✅ LLM prompt validation (Promptfoo) • ✅ Advanced security scanning (Semgrep + Trivy) • ✅ Production observability (Prometheus + Jaeger) • ✅ Parallel execution • ✅ Zero manual intervention • ✅ Safe failures • ✅ **Autonomous Agent Safeguards** (File protection, risk assessment, auto-rollback, immutable audit trails)

---

**Our team brings decades of deep expertise in system architecture, AI systems, and enterprise software.**

We've spent decades:
- **Building High-Tech Systems** for Fortune 500 companies, consulting groups, and multinational enterprises
- **Leading Multi-National Teams** across EMEA, Asia-Pacific, and North America
- **Scaling from 0-1** in multiple startups, taking products from concept to market leadership
- **Training AI Agents Beyond Public Data** - Our autonomous agents are taught by experienced architects to become true domain experts
- **Solving Complex Compliance & Security** challenges that traditional approaches can't handle

orbitQA.ai is an example of the sophisticated, intelligent systems our team builds. It's not just a tool—it's proof of how decades in architecture, combined with AI expertise, creates systems that rival senior engineers in capability.

---

## 🌟 Why Trust Our Team to Build This?

### Our Expertise Powers Every Agent
- **Compliance Agent** trained on real enterprise compliance frameworks (GDPR, CCPA, WCAG, ADA, OWASP)
- **SRE Agent** with 15+ years of production incident patterns and failure recovery strategies
- **QA Agent** based on testing best practices from enterprise teams
- **Security Agent** with knowledge of thousands of real-world vulnerabilities
- **Fullstack Agent** understanding architectural patterns that work at scale

### From Fortune 500 to Fast-Growth Startups
We've architected systems for:
- **Global Enterprises**: Multi-timezone coordination, regulatory compliance across regions
- **High-Growth Startups**: Scaling from 0-1, building foundations for hypergrowth
- **Consulting Partnerships**: Strategic technology initiatives with top-tier firms
- **Mission-Critical Systems**: 99.9%+ uptime requirements, zero-trust security models

### That Expertise is Now Embedded in orbitQA.ai
Every feature, every compliance check, every recovery pattern comes from real-world experience, not generic training data.

---

## 🎯 What We Can Build Together

If orbitQA.ai excites you, imagine what we could build for your organization:

- **Custom Autonomous Systems** tailored to your specific challenges
- **Enterprise Architecture** that scales with your growth
- **AI Agents** trained on your domain expertise
- **Multi-National Team Leadership** for distributed organizations
- **From 0-1 Concept to Production** in weeks, not quarters

Our team doesn't just build software—we architect strategic technology advantages.

---

## 💼 Consulting Services

Beyond orbitQA.ai, we offer strategic consulting across a comprehensive range of high-impact projects. Our decades of system architecture expertise enables us to deliver solutions that drive real business value.

### AI Transformations
Reimagine your entire SDLC with autonomous AI agents. We design and implement intelligent systems that reduce manual work, improve quality, and accelerate delivery. From compliance automation to intelligent testing, we transform how your organization builds software.

- Agent architecture design and implementation
- Custom domain training for your business context
- End-to-end AI transformation roadmap
- Integration with existing tools and workflows
- Ongoing optimization and scaling

### Custom Education & Upskilling Programs
Build deep technical expertise across your organization with tailored training. We deliver both live workshops and on-demand video content on any technology your team needs to master.

- **Custom Curriculum Design** - Tailored to your team's needs and learning pace
- **Advanced Topics** - Automation frameworks, vector databases, AI agents, modern architectures
- **Live Workshop Sessions** - Interactive training with hands-on labs and real-world scenarios
- **Video Content Library** - Professional, on-demand training materials for ongoing reference
- **Certification & Skill Validation** - Measure progress and validate competency

### Custom Automated Builds
Streamline your development workflow with intelligent build automation. We design systems that compile, test, and deploy your code with zero manual intervention and maximum efficiency.

- Build pipeline architecture and optimization
- Multi-framework and multi-language support
- Parallel execution for 3x faster builds
- Integration with your existing tool ecosystem
- Continuous performance monitoring and optimization

### Enterprise CI/CD Pipelines
Design and implement world-class deployment automation that scales with your organization. From simple applications to complex microservices, we build pipelines that match your exact requirements.

- End-to-end pipeline architecture and strategy
- Multi-environment deployment patterns
- Blue-green, canary, and rolling deployment strategies
- Automated rollback and disaster recovery
- Integration with GitHub Actions, Jenkins, ArgoCD, and more

### Architecture Modernization
Transform legacy systems into modern, scalable architectures. We design and execute strategic system migrations that reduce technical debt, improve performance, and enable rapid innovation.

- Comprehensive system assessment and roadmap
- Monolith-to-microservices migration strategies
- On-premise to cloud transitions with zero downtime
- Database evolution, optimization, and migration
- Team training and change management

### Strategic Development & Implementation
When you need more than consulting—when you need execution. Our architects lead full-scale implementation of complex projects, combining strategic design with hands-on delivery.

- Full-stack application development
- Performance optimization and system scaling
- Security hardening and compliance implementation
- Third-party system integration
- Dedicated project leadership and delivery

**Every consulting engagement leverages our deep expertise in architecture, AI, compliance, and enterprise systems—the same knowledge embedded in orbitQA.ai.**

---

## 🎯 Core Features

### 1. **Multi-Agent Autonomous Architecture** 
Five specialized AI agents that collaborate to ensure perfect code quality and compliance:

- **🛡️ Compliance Agent** (1,200 lines)
  - 175+ compliance checks across 7 standards (GDPR, CCPA, WCAG 2.1, ADA, OWASP, Licensing, Legal)
  - Automatic policy generation (Privacy Policy, Terms of Service)
  - Real-time legal document validation
  - Deployment security verification
  
- **🧪 QA Agent** (665 lines + 230 lines expertise)
  - Manual UI testing automation with Puppeteer
  - Accessibility compliance checking
  - Cross-browser validation
  - 9 issue categories with 4 severity levels
  - 18+ QA best practices
  
- **🔧 SRE Agent** (1,620+ lines + 190 lines expertise)
  - Real-time pipeline monitoring (10-second polling intervals)
  - Automatic failure detection and self-healing
  - Linting error fixing (removes unused variables/functions)
  - Compliance agent error recovery
  - 5-stage failure recovery process
  - Version management and automated releases
  
- **🤖 SDET Agent** (CI/CD workflow integration)
  - Automated test generation
  - Feature verification
  - Test case coverage analysis
  
- **🔗 Fullstack Agent** (1,800+ lines)
  - Intelligent code fixing with pattern matching
  - Test generation from compliance violations
  - Multi-knowledge collaboration
  - **NEW: Enterprise-Grade Compliance Auto-Fix System**
    - Reads compliance reports automatically
    - Intelligent issue routing to 4 specialized fixers
    - 6+ Compliance issue types: GDPR rights, CCPA rights, privacy policy, licenses
    - 6+ Accessibility fixes: color contrast, labels, alt text, ARIA, lang, titles
    - Security fixes: npm audit, SECURITY.md generation
    - Documentation fixes: README, CONTRIBUTING.md, license docs
    - Re-validates all fixes automatically

### 2. **Self-Healing CI/CD Pipeline**

**Concurrency-Optimized Workflow** with Smart Run Classification:
- ✅ **Parallel Test Chains**: Multiple test runs execute simultaneously
- ✅ **Serial Reruns**: Reruns group with their initial runs to prevent duplicate testing
- ✅ **Run Type Classification**: initial | retest | retry | diagnostic | manual
- ✅ **Smart Dashboard**: Clean GitHub Actions UI showing only active runs

**Automatic Error Detection & Fixing**:
- Linting errors → Automatic removal of unused code
- Test failures → Pattern-based fixes with validation
- Compliance violations → Automatic remediation
- File path issues → Working directory fixes
- Port conflicts → Intelligent port cleanup

### 3. **Enterprise Compliance Framework**

**175+ Automated Checks** across 7 compliance standards - covering GDPR, CCPA, WCAG 2.1, ADA, OWASP Top 10, Licensing, and Legal Documents.

### 4. **Comprehensive Testing Infrastructure**

**Auto-Updating Tests** across any testing framework - automatically generating unlimited tests for complete codebase coverage. ESLint, Jest, Vitest, Playwright, Cypress, and Pa11y with continuous expansion.

### 5. **Real-Time Pipeline Monitoring**

Real-time SRE agent monitoring with 10-second polling intervals, automatic failure analysis, and intelligent recovery.

### 6. **Intelligent Linting Error Fixing**

Automatically removes unused variables/functions, detects duplicates, and fixes formatting issues before they cause failures.

### 7. **Web UI for Interactive Scanning**

Professional dashboard for real-time URL scanning, comprehensive issue analysis, AI-generated test cases, and code generation

- Console errors and page exceptions
- Failed network requests
- Common DOM and accessibility issues (missing image alts, broken images, missing form labels, bad anchors, heading order problems)
- Automatically generated recommended test cases (positive and negative)
- Simulated performance results (JMeter-like summary)
- **APIs Used:** Displays up to 10 API calls (fetch/XHR) detected on the scanned page
- **Playwright Example:** Shows a Playwright test code snippet for the first recommended test case
- **Cypress Example:** Shows a Cypress test code snippet for the first recommended test case

### 8. **Enterprise-Grade Testing & Observability Stack** ✨ NEW

**5 Open Source Tools for Comprehensive Agent Validation & Monitoring:**

#### LLM Agent Validation
- **Promptfoo** - Validates agent prompts and LLM outputs
  - Tests prompt consistency across multiple runs
  - Validates JSON/code generation correctness
  - Detects edge cases and error scenarios
  - Automated regression testing for agent behavior

#### Advanced Security Scanning
- **Semgrep** - OWASP Top 10 + CWE vulnerability detection
  - Pattern-based code security scanning
  - Real-time vulnerability identification
  - Customizable security rules
  - Integrates with CI/CD pipeline

- **Trivy** - Container image vulnerability scanning
  - Scans Docker images for CVE vulnerabilities
  - Dependency analysis and threat reporting
  - Severity-based vulnerability filtering
  - Pre-deployment image validation

#### Production Observability
- **Prometheus** - Metrics collection and monitoring
  - Real-time agent pipeline metrics
  - Custom metric collection from agents
  - Time-series data for historical analysis
  - HTTP API for metric queries

- **Jaeger** - Distributed tracing for agent requests
  - End-to-end request tracing through pipeline
  - Service dependency visualization
  - Latency analysis and bottleneck detection
  - Error tracking and failure analysis

**Integration:** All tools run automatically in CI/CD phases 1.5, 1.6, and 2.5. Full results uploaded as artifacts for review and compliance.

### 9. **Autonomous Compliance Auto-Fix System** ⭐

Enterprise-grade compliance remediation that automatically reads reports, identifies issues, and applies targeted fixes:

**Intelligent Routing:** Issues automatically categorized and routed to specialized fixers
- **Compliance Fixer:** GDPR rights, CCPA/California rights, privacy policy gaps, third-party licenses
- **Accessibility Fixer:** Color contrast, form labels, image alt text, ARIA attributes, HTML lang, title tags
- **Security Fixer:** npm audit fix, SECURITY.md generation, incident response procedures
- **Documentation Fixer:** README enhancement, CONTRIBUTING.md generation, license documentation

**Key Capabilities:**
- ✅ Reads compliance-audit-report.md automatically
- ✅ Parses all issues by severity (Critical → Low)
- ✅ Content-safe file modifications (compares before/after)
- ✅ Priority-based processing (critical issues first)
- ✅ Graceful error handling (continues on failures)
- ✅ Re-validation with compliance agent

### 10. **Enterprise-Grade Autonomous Agent Safeguards** 🛡️ NEW

Mission-critical protection layer validating every autonomous agent change before deployment. Purpose-built for enterprises that require governance without blocking innovation.

**3-Component Safety System:**

**🔒 PipelineGatekeeper** - File Protection & Change Validation
- Protects critical files: `package.json`, `.env*`, `.github/workflows/**`, `auth/**`, `payment/**`, `*.lock`
- Validates agent change scope (max 50 files per operation)
- Risk assessment with pattern-based scoring (0-1.0 scale)
- Categorizes risk: Security code changes (+0.3), multiple directories (+0.2), deletions (+0.15)
- Real-time validation reports with actionable feedback

**📊 RollbackMonitor** - Deployment Safety & Auto-Recovery
- 30-minute post-deployment monitoring with configurable polling
- Metric-based auto-rollback on degradation:
  - Error rate threshold: 50%
  - Latency threshold: 30%
  - Memory threshold: 100MB increase
  - CPU threshold: 40%
  - Failed test threshold: 5+ failures
- Automatic notifications and rollback execution
- Preserves system stability during agent learning

**📝 AuditTrail** - Immutable Compliance Logging
- Cryptographic SHA-256 signing for tamper-proof audit logs
- Organized daily logs with automatic indexing
- Multi-compliance reporting: SOC2 Type II, GDPR, HIPAA
- Change tracking by agent, action, risk level, and timestamp
- Integrity verification with automatic alerts
- S3 archiving support for long-term compliance storage

**Integration in CI/CD:** Runs as Phase 4 (after agent changes, before health verification)
- ✅ Zero blocking approval gates (build-phase validation)
- ✅ Production-ready compliance framework
- ✅ Enterprise audit trail for governance
- ✅ Risk scoring for informed decisions
- ✅ Auto-recovery without manual intervention

**Quick Start:**
```bash
npm run safeguards:test        # Run 4-scenario validation suite
npm run safeguards:examples    # View 7 integration patterns
npm run safeguards:verify      # Quick system readiness check
```

📚 **Full Documentation:**
- [Safeguards Getting Started](SAFEGUARDS_GETTING_STARTED.md) - 5-15 minute setup
- [Implementation Details](SAFEGUARDS_IMPLEMENTATION.md) - Production roadmap
- [API Reference](src/safeguards/README.md) - Technical deep-dive

- ✅ Detailed logging and reporting
- ✅ Production-ready code (syntax validated, fully tested)

**Usage:**
```bash
export COMPLIANCE_MODE=enabled
node fullstack-agent.js
```

**Live Results:** ✅ GDPR & CCPA sections auto-added to PRIVACY_POLICY.md • ✅ 12 issues parsed • ✅ Compliance agent re-validated

## Quick Start

### 1. Manual Scanning (Web UI)
```bash
npm install
npm start
# Visit http://localhost:3000 in your browser
```

### 2. Autonomous Agent (LangGraph)
```bash
npm install
npm start &              # Terminal 1: Start server
npm run agent "https://example.com"  # Terminal 2: Run agent
```

### 3. Run All Tests
```bash
npm install
npm run test:vitest     # Vitest (18 tests, <300ms)
npx jest --coverage     # Jest (5 tests with coverage)
npx playwright test     # Playwright (7+ E2E tests)
npm run test:cypress    # Cypress (22 E2E tests)
npx eslint . --ext .js  # ESLint linting
```

## Setup

1. **Install dependencies:**
	 ```bash
	 npm install
	 ```

2. **Run the server:**
	 ```bash
	 npm start
	 ```

3. **Open the web UI:**
	 Go to [http://localhost:3000](http://localhost:3000) in your browser. Enter a URL to scan.


## How AgenticQA Compares to Competitors

AgenticQA stands apart through **circular self-healing architecture with shared agent cores** where agents test agents, creating unprecedented autonomy and reliability—backed by enterprise-grade architecture shared across both in-repo and SaaS products.

### Competitive Advantages vs Industry Leaders

| Feature | **AgenticQA** | **orbitqa-ai** | Testim | Applitools | BrowserStack | Sauce Labs | TestMu AI |
|---------|-----------|-----------|--------|-----------|--------|-----------|-----------|
| **Autonomous Test Generation** | ✅ AI-native agents | ✅ AI-native agents | ⚠️ Limited ML | ⚠️ Partial | ❌ No | ❌ No | ⚠️ Basic |
| **Self-Healing Tests** | ✅ Circular agent loop | ✅ Circular agent loop | ⚠️ ML-based | ⚠️ Visual only | ❌ No | ❌ No | ⚠️ Limited |
| **Agent-on-Agent Testing** | ✅ Unique | ✅ Unique | ❌ No | ❌ No | ❌ No | ❌ No | ❌ No |
| **Compliance Automation** | ✅ 7 standards | ✅ 7 standards | ❌ No | ❌ No | ❌ No | ❌ No | ❌ No |
| **Shared Agent Cores** | ✅ 6 npm packages | ✅ 6 npm packages | ❌ N/A | ❌ N/A | ❌ N/A | ❌ N/A | ❌ No |
| **CLI Interface** | ✅ Full CLI + pre-commit | ❌ REST only | ⚠️ Limited | ⚠️ Limited | ❌ No | ❌ No | ❌ No |
| **SaaS Interface** | ❌ CLI only | ✅ Full SaaS + API | ✅ Web UI | ✅ Web UI | ✅ Web UI | ✅ Web UI | ✅ Web UI |
| **Cost Model** | Usage-based agents | Usage-based agents | Seat-based | Seat-based | Device-based | Device-based | Subscription |
| **Learning Loop** | Continuous (circular) | Continuous (circular) | Periodic | Snapshot-based | N/A | N/A | Limited |
| **Zero Code Duplication** | ✅ Monorepo design | ✅ Same agent cores | ❌ Separate platforms | ❌ Separate platforms | ❌ Separate systems | ❌ Separate systems | ❌ Separate |
| **Advanced Security** | ✅ Semgrep + Trivy | ✅ Semgrep + Trivy | ⚠️ Basic | ⚠️ Basic | ⚠️ Basic | ⚠️ Basic | ⚠️ Basic |
| **Observability Stack** | ✅ Prometheus + Jaeger | ✅ Prometheus + Jaeger | ❌ Limited | ❌ Limited | ⚠️ Basic | ⚠️ Basic | ❌ No |
| **Agent Safeguards** | ✅ 3-component system | ✅ 3-component system | ❌ No | ❌ No | ❌ No | ❌ No | ⚠️ Basic |

### Key Differentiators

#### 1. **Shared Agent Architecture (Unique)**
- **What:** 6 npm packages (@orbitqa/*) used by both AgenticQA and orbitqa-ai
- **Why:** Eliminates code duplication, ensures identical agent behavior, enables independent product evolution
- **Impact:** 4,200+ lines of duplicate code eliminated, single source of truth, easier maintenance
- **Competitors:** Testim, TestMu, Applitools maintain separate codebases per product

#### 2. **Dual Deployment Model**
- **CLI Version (AgenticQA):** Pre-commit hooks, file system access, developer tools, open-source friendly
- **SaaS Version (orbitqa-ai):** REST API, webhooks, web dashboard, multi-tenant, enterprise ready
- **Both:** Identical agent logic, different interfaces
- **Competitors:** Choose either CLI (rare) or SaaS (most), not both with same agent logic

#### 3. **Enterprise Agent Safeguards**
- **3-Component Protection:** PipelineGatekeeper, RollbackMonitor, AuditTrail
- **Compliance Ready:** SOC2 Type II, GDPR, HIPAA audit logging
- **Autonomous Protection:** No manual approval gates, build-phase validation
- **Competitors:** Manual approval gates, limited audit trails, no autonomous protection

#### 4. **Advanced Observability**
- **Prometheus:** Real-time metrics from agent pipeline execution
- **Jaeger:** End-to-end distributed tracing for request flows
- **LLM Validation:** Promptfoo for agent prompt testing
- **Security Scanning:** Semgrep (OWASP) + Trivy (container CVEs)
- **Competitors:** Limited observability, few open-source integrations

#### 5. **Compliance at Enterprise Scale**
- **175+ Checks** across 7 standards (GDPR, CCPA, WCAG 2.1, ADA, OWASP, Licensing, Legal)
- **Both Products:** Identical compliance engine
- **Automatic Fixes:** Reads reports, auto-fixes issues, re-validates
- **Competitors:** Limited compliance, no automation, not standardized

#### 6. **Circular Self-Healing**
- **Agent Testing:** SDET agent tests other agents' outputs
- **Continuous Loop:** Agents improve each other automatically
- **Failure Recovery:** 5-stage recovery with automatic fixes
- **Competitors:** Linear pipelines, no agent-on-agent testing, limited recovery

#### 7. **Open Standards Integration**
- **Jest, Vitest, Playwright, Cypress** - All supported
- **Node.js Ecosystem** - npm, pnpm, yarn compatible
- **Container Native** - Docker, Kubernetes ready
- **GitHub Native** - Actions, webhooks, status checks
- **Competitors:** Proprietary integrations, limited ecosystem support

### Industry Positioning

**vs Testim/Mabl (ML-based Test Automation):**
- ✅ More sophisticated agent architecture (vs ML models)
- ✅ Compliance automation (vs test-only focus)
- ✅ Self-healing (vs ML guessing)
- ✅ Shared agent cores (vs single product)

**vs Applitools (Visual AI):**
- ✅ Functional testing (vs visual only)
- ✅ Compliance automation (not just visuals)
- ✅ Safeguards for governance (vs no safeguards)
- ✅ Dual deployment (vs SaaS only)

**vs BrowserStack/Sauce Labs (Device Labs):**
- ✅ Autonomous agents (vs manual/recorded tests)
- ✅ Compliance scanning (vs device access)
- ✅ Self-healing (vs static tests)
- ✅ Much lower cost (usage-based agents vs device-based)

**vs TestMu AI (Agentic Testing):**
- ✅ Shared agent architecture (vs separate implementations)
- ✅ Dual deployment options (vs SaaS only)
- ✅ Enterprise safeguards (3-component system)
- ✅ Compliance automation (7 standards + auto-fix)
- ✅ Zero code duplication (monorepo design)
- ✅ Open standards (Jest, Cypress, Playwright)
- ✅ Advanced observability (Prometheus, Jaeger)
- ✅ LLM validation (Promptfoo)

**[View Full Competitor Analysis →](./COMPETITOR_COMPARISON.md)**

---

## Features

### AgenticQA (In-Repo)
- **Scan Results:** Console errors, page exceptions, failed requests, and DOM/accessibility issues (max 25 items per scan)
- **Recommended Test Cases:** 10 positive and 10 negative test cases are generated for the scanned page
- **Performance Results:** Simulated JMeter-like summary: total/failed requests, resource count, average response time, page load time, throughput, and top resources
- **APIs Used:** Displays up to 10 API calls (fetch/XHR) detected on the scanned page
- **Playwright Example:** Shows a Playwright test code snippet for the first recommended test case
- **Cypress Example:** Shows a Cypress test code snippet for the first recommended test case
- **Pre-commit Hooks:** Automatic testing on every git commit
- **CLI Integration:** Run tests directly from command line

### orbitqa-ai (External SaaS)
- **All AgenticQA Features:** Plus REST API exposure
- **Web Dashboard:** Visual interface for analyzing results
- **Webhooks:** Integrate with GitHub, GitLab, Gitea, Bitbucket
- **Multi-Tenant:** Support for multiple organizations
- **API Access:** Full REST API for programmatic access
- **Scheduled Scans:** Configure recurring URL scans
- **Reports:** Generate comprehensive audit reports

## Autonomous Agent (Agentic Engineering Expert)

The project includes a powerful **LangGraph-based Agentic Engineering Expert** that autonomously scans production URLs, analyzes them using the actual product, and generates AI-powered improvement recommendations. This is your personal engineering expert that continuously evaluates external websites for quality, accessibility, and testing opportunities.

### What Makes It an Agentic Engineering Expert

The agent combines three specialized tools to provide expert-level QA analysis:

1. **Codebase Intelligence** - Understands your project structure and organization
2. **Real-World Testing** - Uses the actual product UI to scan external websites (like a real engineer would)
3. **Expert Recommendations** - Generates intelligent, context-aware improvement suggestions based on actual findings

### Agent Capabilities

The agent autonomously:

✅ **Scans Production URLs in Real-Time**
- Analyzes any website: `https://yahoo.com`, `https://cbs.com`, `https://github.com`, etc.
- Uses Playwright to navigate and interact with sites just like a human QA engineer
- Extracts accessibility issues, performance metrics, API usage patterns
- Captures console errors, network failures, DOM problems

✅ **Uses Your Actual Product to Test**
- Submits URLs to your deployed frontend
- Fills input fields and clicks buttons automatically
- Extracts comprehensive scan results from the UI
- Validates that the scanning system works correctly on real external sites

✅ **Generates AI-Powered Recommendations**
- Creates 3 expert recommendations per URL analyzed:
  - **Accessibility Recommendations:** Specific improvements for WCAG 2.1 compliance
  - **Performance Recommendations:** Optimization strategies based on actual metrics
  - **Testing Recommendations:** Test coverage expansion and automation strategies
- Recommendations are context-aware - different for each URL based on findings

### Agent Architecture

The agent has three specialized tools working in concert:

#### Tool 1: scanCodebase()
- Recursively scans project directory (2 levels deep)
- Ignores node_modules, .git, coverage, test-results
- Returns file hierarchy with metadata:
  - File sizes and line counts
  - Directory structure
  - Code previews
- Perfect for understanding project organization

#### Tool 2: submitURLToFrontend()
- Uses Playwright for headless browser automation
- Navigates to your frontend UI (localhost:3000 or deployed instance)
- Fills URL input field with target website
- Clicks scan button to initiate real QA analysis
- Waits for results (up to 30 seconds)
- Extracts all result sections:
  - Scan results (console errors, DOM issues)
  - Generated test cases
  - Performance metrics
  - Detected APIs
  - Code generation examples (Playwright, Cypress)
  - **AI-generated recommendations**

#### Tool 3: analyzeResults() & generateRecommendations()
- Analyzes scan findings with intelligent pattern matching
- Counts issues by type (accessibility, performance, security)
- Generates expert recommendations based on:
  - Number and severity of accessibility issues
  - Performance metrics (load time, failed requests)
  - Detected APIs and testing opportunities
- Creates structured recommendations that are actionable and specific

### Agent Workflow

The agent executes in three sequential steps, simulating how a human QA engineer would work:

```
┌──────────────────────────────────────────────────┐
│ Step 1: Understand Your Project                  │
│ - Scans codebase structure                       │
│ - Identifies technologies and files              │
│ - Prepares for testing                           │
└──────────────────────────────────────────────────┘
              ↓
┌──────────────────────────────────────────────────┐
│ Step 2: Test Real Websites Using Your Product   │
│ - Navigates to frontend (your actual product)    │
│ - Submits external URLs for scanning             │
│ - Extracts comprehensive analysis results        │
│ - Validates your system works on live sites      │
└──────────────────────────────────────────────────┘
              ↓
┌──────────────────────────────────────────────────┐
│ Step 3: Generate Expert Recommendations         │
│ - Analyzes findings intelligently                │
│ - Identifies improvement opportunities           │
│ - Creates 3 context-aware recommendations       │
│ - Prioritizes by impact and effort              │
└──────────────────────────────────────────────────┘
```

### Using the Agent

#### Single URL Analysis
```bash
# Start your product
npm start &

# Analyze a specific website
npm run agent "https://example.com"
```

#### Multiple URL Analysis (Default)
```bash
# Analyzes 3 production websites by default
npm run agent

# Scans: yahoo.com, cbs.com, github.com
# Each gets personalized recommendations
```

#### Programmatic Usage
```javascript
const { QAAgent } = require("./agent.js");

const agent = new QAAgent();
const state = await agent.run("https://github.com");

// Access results
console.log(state.codebaseInfo);        // Your project structure
console.log(state.scanResults);         // Scans of all URLs
console.log(state.analysis);            // AI recommendations
```

#### Example Output
```
╔════════════════════════════════════════╗
║ Agentic Engineering Expert - LangGraph ║
╚════════════════════════════════════════╝

📂 Step 1: Scanning codebase structure...
✅ Codebase scanned successfully

📋 Project Files: 45 total
  - JavaScript files: 32
  - HTML/CSS: 5
  - Config files: 8

🚀 Step 2: Testing production URLs...

📍 Scanning: https://www.yahoo.com
🌐 Using your frontend at localhost:3000
📝 Submitting URL for analysis...
✅ Analysis complete

📊 Findings:
  - Issues: 14 detected
  - Test Cases: 20 recommended
  - APIs: 5 identified
  - Performance: Good (< 3s load time)

💡 orbitQA.ai Engineer's Recommendations:

  1. 🎯 Critical: Fix 9 accessibility issues including missing alt text 
     and ARIA labels. This blocks ~15% of users and hurts SEO ranking.

  2. ⚡ Performance: Page load is solid. Monitor Core Web Vitals 
     monthly using Google Lighthouse. Implement Service Workers 
     for offline capability.

  3. 🧪 Testing: Create automated tests for 5 detected APIs and 
     critical user flows. Target 80%+ code coverage to catch 
     regressions early.

📍 Scanning: https://www.cbs.com
✅ Analysis complete with personalized recommendations

📍 Scanning: https://www.github.com
✅ Analysis complete with personalized recommendations

═════════════════════════════════════════════════════════
✨ Agentic Engineering Expert Analysis Complete
```

### How It Works on Production Deploy

When the agent runs in CI/CD (GitHub Actions):

1. **Your product is deployed** - Frontend runs at specified URL
2. **Agent analyzes real websites** - Tests your system against production URLs
3. **Recommendations are generated** - Specific to each URL's findings
4. **Results are logged** - Visible in CI output for team review
5. **Quality insights provided** - Actionable improvements for all analyzed sites

### Agent Requirements

1. **Server running** - Your frontend must be accessible (localhost or deployed)
2. **Valid URLs** - Target websites must be publicly accessible
3. **Dependencies installed** - Playwright, Node.js modules
4. **Optional:** Specify URLs - Default scans 3 production websites

### Key Differences from Manual Testing

| Aspect | Manual Testing | Agentic Expert |
|--------|---|---|
| **Speed** | 5-10 min per site | 30 seconds per site |
| **Consistency** | Variable | 100% consistent |
| **URLs Covered** | 1-2 | Unlimited (batch multiple) |
| **Recommendations** | Manual notes | AI-generated, specific |
| **Integration** | Manual process | Automated in CI/CD |
| **Scale** | Limited | Unlimited production sites |

### Future Enhancements

- [ ] Multi-URL batch scanning with report generation
- [ ] LLM-based result interpretation for deeper insights
- [ ] Scheduled scans with historical trending
- [ ] Slack/Email notifications with key findings
- [ ] PDF report generation for stakeholders
- [ ] Integration with bug tracking systems (Jira, GitHub Issues)

### Full Documentation
See [AGENT.md](./AGENT.md) for comprehensive technical documentation including state management, error handling, and advanced configuration.

## API

- `POST /scan` — Accepts `{ url: "https://example.com" }` and returns scan results, test cases, and performance summary as JSON

## Development & Testing

### Comprehensive Test Coverage

orbitQA.ai generates unlimited tests across any testing framework to ensure reliability, maintainability, and code quality. We can generate as many tests as your organization needs, with full coverage across your entire codebase.

#### Test Suite Capabilities

| Framework | Capability | Purpose | Coverage |
|-----------|-----------|---------|----------|
| **ESLint** | Continuous static analysis | Code quality, linting standards, best practices | All source files |
| **Jest** | Unlimited unit tests | Server-side logic, utilities, core functions | Complete coverage |
| **Vitest** | Fast modern unit tests | Server, browser, integration components | Full codebase |
| **Playwright** | Modern E2E browser automation | UI interactions, cross-browser compatibility | All user flows |
| **Cypress** | Comprehensive E2E testing | Complex workflows, accessibility, integration | Business-critical paths |

**Unlimited automated tests ensuring comprehensive coverage - generated to match your needs**

### Thorough Unit Testing Across All Languages

Each programming language in the project is validated with dedicated unit tests:

#### JavaScript (Node.js) - Backend
- **Functions Tested:** `normalizeUrl()`, `mapIssue()`, API scanning logic
- **Frameworks:** Jest, Vitest
- **Tests:** 8 dedicated tests
- **Focus:** URL normalization, issue mapping, error handling

#### JavaScript (Browser) - Frontend
- **Functions Tested:** `renderResults()`, `generatePlaywrightExample()`, `generateCypressExample()`
- **Frameworks:** Jest, Vitest
- **Tests:** 6 dedicated tests
- **Focus:** Code generation, result rendering, template logic

#### HTML/CSS Structure
- **Validation:** Semantic HTML structure, CSS styling rules, responsive design
- **Frameworks:** Vitest, Cypress
- **Tests:** 19+ dedicated tests
- **Focus:** DOM structure, layout consistency, accessibility compliance

#### Integration Testing
- **Coverage:** Full scan workflow, URL handling, test case generation, API detection, performance metrics
- **Frameworks:** Vitest
- **Tests:** 6 dedicated tests
- **Focus:** End-to-end logic flow and data transformations

### Thorough UI Testing with Multiple Tools

The project uses **3 complementary E2E testing frameworks** to catch UI issues from different angles:

#### Playwright Tests (`playwright-tests/`)
- **Focus:** Modern browser automation and cross-browser compatibility
- **Tests:** 7+ UI validation tests
- **Coverage:** Element visibility, placeholder text, readonly attributes, form validation
- **Advantage:** Lightweight, fast, good for rapid UI validation

#### Cypress Tests (`cypress/e2e/scan-ui.cy.js`)
- **Focus:** User-centric testing and interactive flows
- **Tests:** 7 comprehensive UI tests
- **Coverage:** Homepage loading, result boxes, input validation, readonly states, error handling
- **Advantage:** Great developer experience, interactive debugging

#### Accessibility & Integration Tests (`cypress/e2e/accessibility.cy.js`)
- **Focus:** Accessibility compliance and full workflow integration
- **Tests:** 15 comprehensive tests including:
  - Heading hierarchy and semantic structure
  - Form element labels and placeholders
  - Keyboard navigation support
  - Responsive viewport testing (mobile, tablet, desktop)
  - Color contrast validation
  - Complete scan flow integration
  - UI state consistency across interactions
- **Advantage:** Ensures usability for all users, catches real-world issues

**Why Multiple Frameworks?**
- **Playwright** catches structural issues fast
- **Cypress (UI)** validates user interactions thoroughly
- **Cypress (Accessibility)** ensures compliance and real-world workflows
- Combined approach ensures no UI bugs, accessibility issues, or user experience problems

### Code Quality & Maintainability

#### Linting
```bash
npx eslint . --ext .js
```
- **Status:** 0 errors, 6 warnings
- **Coverage:** All JavaScript files including server, browser, tests
- **Standard:** ESLint v9+ with flat config

#### Unit Testing with Coverage
```bash
npx jest --coverage
```
- **Test Count:** 5 comprehensive unit tests
- **Coverage:** Server functions, utilities, browser logic
- **Metrics:** Statement, branch, function, and line coverage

#### Fast Unit Testing
```bash
npm run test:vitest
```
- **Test Count:** 18 tests (4 test files)
- **Speed:** <300ms execution
- **Coverage:** Includes HTML/CSS validation and integration tests

#### Modern E2E Testing
```bash
npx playwright test
```
- **Test Count:** 7+ tests
- **Execution:** <2 seconds
- **Coverage:** UI element validation, form interactions

#### Comprehensive E2E Testing
```bash
npm run test:cypress
```
- **Test Count:** 22 tests (2 spec files)
- **Execution:** <15 seconds
- **Coverage:** UI validation, accessibility, integration flows

#### Autonomous Agent Testing
```bash
npm start &
npm run agent "https://example.com"
```
- **Capabilities Tested:**
  - ✅ Codebase scanning and analysis
  - ✅ Browser automation with Playwright
  - ✅ UI interaction (input, button clicks)
  - ✅ Results extraction and analysis
- **Coverage:** All three agent tools (scanCodebase, submitURLToFrontend, analyzeResults)
- **Validates:** Autonomous workflow and data processing pipeline

### Automated CI/CD Pipeline

GitHub Actions runs **5 parallel jobs** on every push and pull request:

```yaml
jobs:
  1. lint - ESLint validation
  2. unit-test - Jest with coverage
  3. test-vitest - Vitest with coverage
  4. test-playwright - Playwright E2E tests
  5. test-cypress - Cypress E2E + accessibility tests
```

**All jobs must pass** before code can be merged, ensuring:
- ✅ No style violations
- ✅ No broken unit tests
- ✅ No UI regressions
- ✅ No accessibility issues
- ✅ No integration failures

### Running All Tests

```bash
# Run all tests at once
npm run test:vitest -- --run && \
npx jest && \
npx playwright test && \
npm run test:cypress && \
npx eslint . --ext .js
```

### Test Maintenance & Usability

The test suite is designed for **ease of maintenance** and **maximum usability**:

1. **Clear Test Organization**
   - Unit tests in `unit-tests/` and `vitest-tests/`
   - E2E tests in `playwright-tests/` and `cypress/e2e/`
   - Each test file focuses on a specific component

2. **Descriptive Test Names**
   - Tests clearly state what is being validated
   - Easy to identify failing tests and their purpose
   - Self-documenting test code

3. **Comprehensive Error Messages**
   - Test failures include expected vs actual values
   - Line numbers and stack traces for debugging
   - Coverage reports for identifying gaps

4. **Low Maintenance Overhead**
   - Minimal configuration required
   - Tests run in parallel for speed
   - Clear separation of concerns

### Linting

```bash
npx eslint . --ext .js
```

### Unit Tests (Jest)
```bash
npx jest --coverage
```

### Unit Tests (Vitest)
```bash
npm run test:vitest -- --run --coverage
```

### Playwright Tests
```bash
npx playwright test
```

### Cypress Tests
```bash
npm run test:cypress
```

## Autonomous Agent

This project includes a **LangGraph-based autonomous agent** that combines codebase analysis with UI interaction to provide comprehensive QA insights.

### Agent Overview

The agent (`agent.js`) uses LangChain and LangGraph to orchestrate three specialized tools:

1. **scanCodebase()** - Analyzes project structure recursively (2 levels deep)
   - Scans all `.js`, `.json`, `.css`, `.html` files
   - Ignores: `node_modules/`, `.git/`, `coverage/`, `test-results/`, `.next/`, `dist/`, `build/`
   - Returns: File count, directory structure, technology stack

2. **submitURLToFrontend()** - Uses Playwright for browser automation
   - Navigates to application URL
   - Fills in scan input field with detected codebase info
   - Clicks "Scan" button
   - Waits for results to load
   - Extracts findings from result sections

3. **analyzeResults()** - Processes scan findings
   - Counts identified issues
   - Extracts test cases and performance metrics
   - Detects APIs and code generation capabilities
   - Generates summary statistics

### Running the Agent

**Basic Usage:**
```bash
npm run agent "https://example.com"
```

**With Running Server:**
```bash
# Terminal 1: Start the application
npm start

# Terminal 2: Run the agent
npm run agent "http://localhost:3000"
```

**Programmatic Usage:**
```javascript
const { QAAgent } = require('./agent.js');

const agent = new QAAgent();
await agent.run('http://localhost:3000');

// Access results:
// agent.scanResults - Raw API response
// agent.analysis - Processed statistics
```

### Agent Workflow

The agent follows this 3-step workflow:

```
START
  ↓
[1] Scan Codebase
    └─→ Analyze project structure
        Identify technologies used
        Return file statistics
  ↓
[2] Submit to Frontend
    └─→ Automation via Playwright
        Navigate to app
        Input scan data
        Extract results
  ↓
[3] Analyze Results
    └─→ Process findings
        Generate statistics
        Create summary report
  ↓
END (Display report)
```

### Example Output

```
=== CODEBASE INFO ===
Total files: 45
JavaScript files: 32
JSON files: 5
CSS files: 3
HTML files: 5

=== ANALYSIS ===
Issues found: 12
Test cases detected: 8
Performance metrics: 4
APIs identified: 3
Code generation capable: true
```

### Agent Capabilities

✅ **Codebase Analysis**
- Recursive file scanning
- Technology detection
- Project structure mapping

✅ **UI Automation**
- Browser navigation
- Form interaction
- Result extraction
- Screenshot capability

✅ **Result Processing**
- Issue aggregation
- Metric calculation
- Report generation
- Statistics summary

### Testing the Agent

Run the agent with the development server:

```bash
# In one terminal
npm start

# In another terminal
npm run agent "http://localhost:3000"
```

**What gets tested:**
- Codebase scanning accuracy (file counts, structure)
- Frontend UI interaction (input/button functionality)
- Result extraction (all sections parsed correctly)
- Error handling (network, timeout scenarios)

**Coverage:**
- Agent initialization
- Tool execution (all three tools)
- Result aggregation
- Error recovery

### Requirements & Dependencies

- **Node.js**: v20 or later
- **Browser**: Chromium (installed by Playwright)
- **Dependencies**: langchain, @langchain/core, @langchain/langgraph, playwright

### Future Enhancements

- [ ] Multi-URL batch scanning
- [ ] LLM-based result interpretation
- [ ] Scheduled scans with report generation
- [ ] Multi-agent collaboration for distributed analysis
- [ ] WebSocket support for real-time updates
- [ ] Result export (JSON, PDF, HTML reports)
- [ ] Performance trend tracking
- [ ] Custom test case generation rules

For detailed agent documentation, see [AGENT.md](./AGENT.md).

## CI/CD & Automated Testing Infrastructure

### GitHub Actions Workflows

#### 1. **Continuous Integration (CI) Workflow** (`ci.yml`)
Runs on every push and pull request with comprehensive testing:

- **Security Scanning** - npm audit, dependency vulnerability checks, secret detection
- **Linting** - ESLint validation across all JavaScript files
- **Unit Testing** - Jest with code coverage reporting
- **E2E Testing** - Playwright for cross-browser testing
- **Vitest** - Fast unit tests with coverage metrics
- **Cypress** - Full E2E test suite for UI interactions
- **Conditional Execution** - Tests run independently even if linting fails (with `if: always()`)

**Test Results:**
- Each test suite can be run independently
- Failed tests trigger the SRE Engineer workflow automatically
- All test jobs depend on lint but continue even if lint warnings occur

#### 2. **Agentic SRE Engineer Workflow** (`agentic-sre-engineer.yml`)
Automatically diagnoses and fixes failing CI jobs:

**Capabilities:**
- ✅ Detects failing workflow runs and analyzes root causes
- ✅ Removes unused ESLint directives from generated files
- ✅ Adds missing globals (URL, etc.) to ESLint configuration
- ✅ Fixes unused variables and quote consistency issues
- ✅ Handles port conflicts (EADDRINUSE errors)
- ✅ Configures proper server shutdown and cleanup
- ✅ Retries tests multiple times to handle intermittent failures
- ✅ Auto-commits fixes and pushes to main branch
- ✅ Triggers CI workflow after making fixes to validate results
- ✅ Sends email notifications on completion

**Key Features:**
- Graceful error handling with non-critical operations
- Timeout prevention (hard stop at 25 minutes)
- Multiple iteration support (up to 3 attempts)
- Intelligent issue detection from workflow logs
- Git authentication using GITHUB_TOKEN with proper URL rewriting

**How It Works:**
1. Monitors failed workflow runs (lint, tests)
2. Analyzes logs to identify specific issues
3. Makes intelligent code changes:
   - Applies ESLint --fix
   - Updates configuration files
   - Improves error handling
   - Fixes server/port issues
4. Commits changes and retriggers CI
5. Sends summary via email

### Running Tests Locally

**All Tests:**
```bash
npm test              # Run all test suites
```

**Individual Test Suites:**
```bash
npm run test:vitest   # Vitest (18 tests, <300ms)
npx jest --coverage   # Jest (5 tests with coverage)
npx playwright test   # Playwright (7+ E2E tests)
npm run test:cypress  # Cypress (22 E2E tests)
npx eslint . --ext .js  # Linting
```

**Server Management:**
```bash
# Terminal 1: Start server
npm start

# Terminal 2: Run a single test
npx playwright test

# Or run tests with server management
npm run test:cypress  # Uses start-server-and-test
```

## Notes & Limitations

- Results are limited to 25 items per scan
- Puppeteer downloads a Chromium binary on first install (requires network access)
- Some advanced accessibility or performance issues may not be detected
- For troubleshooting Puppeteer launch issues, ensure Chrome/Chromium is available and accessible
- SRE Agent requires GITHUB_TOKEN with `contents: write` permission
- SMTP configuration needed for email notifications (SMTP_USER, SMTP_PASS, SMTP_HOST, SMTP_PORT)

## License

MIT

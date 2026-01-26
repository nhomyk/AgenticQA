# AgenticQA - Enterprise Autonomous QA Platform

> **AI-powered autonomous QA orchestration with intelligent agents, RAG-enhanced learning, Weaviate vector database, and continuous improvement from historical test data.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-%3E%3D3.8.0-blue)]()
[![Node.js](https://img.shields.io/badge/Node.js-%3E%3D14.0.0-brightgreen)]()

**📦 Quick Start:**
- **Python SDK**: `pip install agenticqa` - Use agents in your Python code
- **TypeScript SDK**: `npm install agenticqa` - Integrate with JavaScript/React apps  
- **REST API**: HTTP endpoints for distributed testing
- **CLI**: Command-line tools for local development and CI/CD pipelines

[📖 Complete Documentation](./docs/) | [🚀 Quick Start Guide](./QUICKSTART.md) | [🐍 Python Examples](./examples/) | [🎯 Architecture](./docs/ARCHITECTURE.md)

## 🎯 What is AgenticQA?

AgenticQA is an enterprise-grade autonomous QA platform powered by intelligent agents that **learn from every test execution**. It replaces flaky manual testing with a self-improving system that automatically:

- ✅ **Learns from history** - RAG system stores and analyzes all test results, performance metrics, and coverage data in Weaviate
- ✅ **Makes intelligent decisions** - Agents query historical patterns to predict failures and optimize testing
- ✅ **Detects patterns** - Identifies flaky tests, performance regressions, and compliance issues before deployment
- ✅ **Ensures compliance** - Automates SOC2, GDPR, HIPAA compliance validation
- ✅ **Optimizes continuously** - Self-improving system gets smarter with each deployment

### In Plain English

**AgenticQA is like having a team of expert quality engineers working 24/7 that never get tired and get smarter every day.** 

Four specialized agents (QA, Performance, Compliance, DevOps) work together to automatically test your code and ensure it's fast, secure, and reliable. The system **remembers everything** - test results, performance metrics, security checks, and compliance validations. Each deployment adds to the knowledge base, enabling the agents to make smarter decisions on the next deployment.

## 🏗️ Architecture Highlights

### RAG-Enhanced Decision Making

```
Every Test Run
    ↓
Results Captured (JUnit XML, JSON, pytest output)
    ↓
Stored in Weaviate Vector Database
    ├─ Test execution history
    ├─ Performance metrics with baselines
    ├─ Coverage reports with trends
    └─ Compliance check results
    ↓
Agents Query Historical Data
    ├─ QA Agent: "Find similar test failures"
    ├─ Performance Agent: "Detect regressions"
    ├─ Compliance Agent: "Learn from failures"
    └─ DevOps Agent: "Identify patterns"
    ↓
Smarter Decisions on Next Deployment
```

### Cloud-Ready Deployment

```
Local Development (Docker)    Production (Weaviate Cloud)
    ↓                                ↓
docker-compose up          Single environment variable
Local testing              Automatic cloud failover
Full feature parity        Enterprise SLA & backups
```

## 🚀 Key Features

### 🤖 Four Specialized Agents

#### QA Agent
Intelligent test analysis powered by historical patterns:
- Analyzes test results and failure trends
- Finds similar failures and suggests fixes
- Detects high-risk test patterns
- Generates coverage improvement suggestions
- **New:** Learns from all historical test failures in Weaviate

#### Performance Agent
Real-time performance monitoring with trend analysis:
- Tracks execution latency and resource usage
- Identifies performance degradation trends  
- Detects regressions using historical baselines
- Suggests optimization strategies
- **New:** Analyzes performance history to detect patterns

#### Compliance Agent
Automated compliance validation:
- Validates against SOC2, GDPR, HIPAA requirements
- Checks data handling and security practices
- Provides remediation recommendations
- **New:** Learns from compliance failures to prevent recurrence

#### DevOps Agent
Deployment safety and reliability:
- Pre-deployment validation checks
- Safe rollback mechanisms
- Deployment pattern analysis
- Issue prediction and prevention
- **New:** Learns from deployment history to improve reliability

### 💾 Weaviate Vector Database

**Production-scale vector storage for agent learning:**

- ✅ **Persistent Storage** - All test data persists across deployments
- ✅ **Scalable** - Handles millions of test executions
- ✅ **Cloud Ready** - Deploy to Weaviate Cloud with single environment variable
- ✅ **Local Development** - Docker Compose for offline development
- ✅ **Open Source** - No vendor lock-in, enterprise-grade reliability

**Collections:**
- `test_execution` - Test results with pass/fail/skip status
- `performance_metric` - Performance measurements with baselines
- `coverage_report` - Code coverage with trends
- `compliance_check` - Compliance validation results

### 🔄 Continuous Learning System

**Test Result Ingestion Pipeline:**

1. **Automatic Capture** - GitHub Actions automatically captures test results (JUnit XML, JSON, pytest output)
2. **Intelligent Parsing** - TestResultParser handles multiple formats
3. **Cloud Storage** - Results ingested into Weaviate Cloud automatically
4. **Agent Learning** - Agents query results for pattern recognition
5. **Feedback Loop** - Each deployment improves next deployment

**Supported Formats:**
- JUnit XML (pytest, maven, gradle)
- JSON format (custom, cucumber)
- Pytest console output
- Performance metrics with baselines
- Coverage reports with deltas

### 🧪 Test Coverage & Quality

- ✅ **12/12 RAG Tests** - 100% pass rate for retrieval-augmented generation
- ✅ **15+ Ingestion Tests** - Comprehensive test result parsing and storage
- ✅ **CI/CD Integration** - Automatic testing on every push/PR
- ✅ **Multi-Python Support** - Python 3.9, 3.10, 3.11 tested
- ✅ **Coverage Reports** - Uploaded to Codecov

## 📦 Installation & Setup

### Local Development

```bash
# Clone repository
git clone https://github.com/nhomyk/AgenticQA.git
cd AgenticQA

# Install Python package
pip install -e .

# Start local Weaviate
docker-compose -f docker-compose.weaviate.yml up -d

# Run tests
pytest tests/test_rag_retrieval.py -v

# Use in Python
from agenticqa.rag import create_rag_system
rag = create_rag_system()  # Uses local Weaviate by default
```

### Cloud Production

```bash
# Set environment variables
export AGENTICQA_RAG_MODE=cloud
export WEAVIATE_HOST=your-cluster.weaviate.network
export WEAVIATE_API_KEY=your-api-key

# Use in Python - no code changes needed
from agenticqa.rag import create_rag_system
rag = create_rag_system()  # Automatically uses Weaviate Cloud
```

**Setup Steps:**
1. Create free Weaviate Cloud cluster at https://console.weaviate.cloud/
2. Copy cluster URL and API key
3. Set environment variables (use `.env.cloud.example` as template)
4. Agents automatically use cloud instance - no code changes

## 🔗 Integration with CI/CD

### GitHub Actions

```yaml
# Automatic test result capture and ingestion
name: tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pytest tests/ --junit-xml=results/junit.xml
      - uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: results/

  ingest-results:
    needs: test
    runs-on: ubuntu-latest
    env:
      WEAVIATE_HOST: ${{ secrets.WEAVIATE_HOST }}
      WEAVIATE_API_KEY: ${{ secrets.WEAVIATE_API_KEY }}
    steps:
      - run: python scripts/ingest_test_results.py
```

Test results automatically ingested to Weaviate for agent learning.

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [QUICKSTART.md](./QUICKSTART.md) | Get up and running in 5 minutes |
| [ARCHITECTURE.md](./docs/ARCHITECTURE.md) | System design and data flow |
| [WEAVIATE_SETUP.md](./WEAVIATE_SETUP.md) | Vector database configuration |
| [CLOUD_DEPLOYMENT.md](./CLOUD_DEPLOYMENT.md) | Production cloud setup |
| [RAG_IMPLEMENTATION.md](./RAG_IMPLEMENTATION.md) | RAG system details |
| [.github/TESTING.md](./.github/TESTING.md) | Test organization and running |

## 🎯 Use Cases

### Development Teams
- Automated test discovery and execution
- Flaky test detection and stabilization
- Coverage gap identification
- Performance regression detection

### QA Teams
- Intelligent test recommendations
- Compliance validation automation
- Risk-based test prioritization
- Historical pattern analysis

### DevOps Teams
- Safe deployment validation
- Automatic rollback mechanisms
- Performance monitoring
- Trend analysis and prediction

### Compliance Teams
- Automated SOC2 validation
- GDPR compliance checking
- HIPAA security verification
- Audit trail generation

## 🚀 Performance

- **Test Execution**: 0.14s (RAG suite with mocks)
- **Weaviate Ingestion**: <100ms per batch
- **Pattern Matching**: <50ms for similar failure lookup
- **Agent Decision**: <200ms with historical context

## 🛠️ Technology Stack

**Backend:**
- Python 3.8+ with async support
- Weaviate vector database (open source, BSL license)
- FastAPI for REST endpoints
- Pytest for testing framework

**Frontend:**
- React 18+ with TypeScript
- Tailwind CSS for styling
- Real-time WebSocket updates
- Interactive dashboards

**Infrastructure:**
- Docker & Docker Compose for local development
- Kubernetes-ready for enterprise
- GitHub Actions for CI/CD
- Supports AWS, GCP, Azure, on-premise

## 📊 Recent Improvements

### January 2026 Release
- ✨ **Weaviate Integration** - Enterprise vector database for test data
- ✨ **RAG Learning System** - Agents learn from historical test results
- ✨ **Test Result Ingestion** - Automatic GitHub Actions integration
- ✨ **Cloud Deployment** - Single environment variable cloud setup
- ✨ **Performance Analysis** - Regression detection and trend analysis
- ✨ **CI/CD Pipeline** - Comprehensive GitHub Actions workflows
- ✨ **Test Coverage** - 100% pass rate on RAG and ingestion tests

## 🤝 Contributing

Contributions welcome! Please see [CONTRIBUTING.md](./CONTRIBUTING.md).

## 📄 License

MIT License - see [LICENSE](./LICENSE) file for details.

## 🎯 Roadmap

- [ ] UI dashboard for test history visualization
- [ ] Advanced ML models for failure prediction
- [ ] Integration with popular CI/CD platforms (GitLab, Jenkins)
- [ ] Real-time collaboration features
- [ ] Custom agent creation framework

## 💬 Support

- **Issues**: GitHub Issues
- **Documentation**: See [docs/](./docs/) folder
- **Examples**: See [examples/](./examples/) folder
- **Quick Help**: Run `agenticqa --help`

---

**Made with ❤️ for QA teams who want to ship faster with higher confidence**

# AgenticQA Analytics Dashboard

Real-time visualization and analytics for AI agent collaboration patterns.

![Dashboard Preview](https://img.shields.io/badge/streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-008CC1?style=for-the-badge&logo=neo4j&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd /Users/nicholashomyk/mono/AgenticQA
pip install -r requirements-dashboard.txt
```

### 2. Start Neo4j

```bash
docker-compose -f docker-compose.weaviate.yml up -d neo4j
```

### 3. Launch Dashboard

```bash
streamlit run dashboard/app.py
```

The dashboard will open in your browser at `http://localhost:8501`

---

## 📊 Features

### 🏠 Overview Page
- **System Metrics**: Total agents, delegations, and executions
- **Top Agents**: Most delegated-to agents with success rates
- **Quick Stats**: Real-time performance indicators

### 🕸️ Network Visualization
- **Interactive Graph**: Agent collaboration network
- **Color-Coded Edges**: Success rate visualization
  - 🟢 Green: High success (>80%)
  - 🟡 Yellow: Medium success (50-80%)
  - 🔴 Red: Low success (<50%)
- **Hover Details**: Delegation counts, success rates, durations

### ⚡ Performance Analysis
- **Bottleneck Detection**: Identify slow agents
- **Success Rate Trends**: Track performance over time
- **Duration Analysis**: P95, average, and max durations

### 🔗 Delegation Chains
- **Chain Distribution**: Histogram of delegation depths
- **Longest Chains**: Multi-hop delegation analysis
- **Pattern Discovery**: Identify common collaboration patterns

### 🧠 GraphRAG Recommendations
- **AI-Powered Suggestions**: Who to delegate to for specific tasks
- **Historical Analysis**: Based on past success patterns
- **Confidence Scores**: Data-driven recommendations

### 🔴 Live Activity
- **Real-Time Workflow**: View current and recent delegations as they happen
- **Activity Timeline**: Interactive timeline of recent delegations
- **Status Tracking**: Monitor success/failure rates in real-time
- **Hourly Trends**: Delegation activity over time

### 🔄 Pipeline Flow
- **Architecture Visualization**: See how data flows through AgenticQA
- **RAG Pipeline**: Vector embeddings → Weaviate → Semantic search
- **Delegation Pipeline**: GraphRAG → Neo4j → Agent collaboration
- **Hybrid Metrics**: Performance stats across both storage systems
- **Data Freshness**: Monitor agent activity and last active times

### 🏗️ Ontology
- **Design vs. Reality**: Compare intended workflow with actual behavior
- **Agent Classification**: Identify orchestrators, workers, and balanced agents
- **Delegation Heatmap**: Cross-type delegation patterns visualization
- **Correlation Analysis**: See if agents are used as designed
- **Anomaly Detection**: Find self-delegations, deep chains, slow paths
- **Coverage Metrics**: How many possible paths are actually being used
- **IP Considerations**: Guidance on what's safe to display publicly vs. internally

---

## 🎨 Dashboard Screenshots

### Network View
Visualize agent collaboration as an interactive network graph.

### Performance Metrics
Track bottlenecks and optimization opportunities in real-time.

### GraphRAG Recommendations
Get AI-powered delegation suggestions based on historical patterns.

---

## 🔧 Advanced Analytics

The dashboard includes powerful analytics queries:

### 1. **Predictive Failure Detection**
Assesses risk of delegation failure based on historical patterns.

```python
risk = store.predict_delegation_failure_risk(
    from_agent="SDET_Agent",
    to_agent="SRE_Agent",
    task_type="generate_tests"
)
# Returns: risk_level, failure_probability, recommendations
```

### 2. **Optimal Path Finder**
Finds the best delegation path to reach a capability.

```python
path = store.find_optimal_delegation_path(
    from_agent="SDET_Agent",
    target_capability="deploy",
    max_hops=3
)
# Returns: optimal path, hops, duration, efficiency score
```

### 3. **Cost Optimization**
Identifies expensive delegations and suggests optimizations.

```python
cost_analysis = store.calculate_cost_optimization(
    time_window_hours=24,
    cost_per_second=0.001
)
# Returns: total cost, potential savings, ROI percentage
```

### 4. **Trend Analysis**
Tracks delegation patterns over time.

```python
trends = store.get_delegation_trends(
    days=7,
    granularity="day"
)
# Returns: time series of delegation metrics
```

---

## 📱 Usage Examples

### Basic Usage

1. **View System Overview**: Default landing page with key metrics
2. **Explore Network**: Click "Network" to see agent collaboration graph
3. **Analyze Performance**: Check for bottlenecks and slow delegations
4. **Get Recommendations**: Use GraphRAG for delegation suggestions

### Advanced Usage

#### Auto-Refresh Mode
Enable auto-refresh in sidebar to update dashboard every 30 seconds.

#### Filter by Time Period
Use the time window selector to focus on recent data.

#### Export Data
Click on any chart to download as PNG or CSV.

---

## 🎯 Use Cases

### For Development Teams
- **Monitor agent health**: Track success rates and performance
- **Identify bottlenecks**: Find and fix slow delegations
- **Optimize costs**: Reduce expensive operations

### For Platform Teams
- **System observability**: Real-time dashboard for agent collaboration
- **Trend analysis**: Track improvements over time
- **Capacity planning**: Understand delegation patterns

### For Demonstrations
- **Live demos**: Show real-time agent collaboration
- **Impressive visuals**: Network graphs and metrics
- **Data-driven insights**: GraphRAG recommendations

---

## ⚙️ Configuration

### Environment Variables

```bash
# Neo4j connection (optional)
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="agenticqa123"

# Dashboard settings
export STREAMLIT_SERVER_PORT=8501
export STREAMLIT_SERVER_ADDRESS=localhost
```

### Streamlit Config

Create `.streamlit/config.toml`:

```toml
[server]
port = 8501
address = "localhost"

[theme]
primaryColor = "#1f77b4"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
font = "sans serif"
```

---

## 🐛 Troubleshooting

### Dashboard won't start

```bash
# Check if Neo4j is running
docker ps | grep neo4j

# Restart Neo4j
docker-compose -f docker-compose.weaviate.yml restart neo4j

# Check logs
docker logs agenticqa-neo4j
```

### "Cannot connect to Neo4j"

1. Verify Neo4j is running on port 7687
2. Check credentials in environment variables
3. Test connection: `python -c "from agenticqa.graph import DelegationGraphStore; s = DelegationGraphStore(); s.connect()"`

### Empty dashboard

The dashboard needs historical data. Run some agents first:

```bash
# Run example analytics to populate database
python examples/neo4j_analytics.py

# Or run tests
pytest tests/test_neo4j_delegation.py -v
```

### Port already in use

Change the port:

```bash
streamlit run dashboard/app.py --server.port 8502
```

---

## 🔒 Security Considerations

- **Local only**: Dashboard binds to localhost by default
- **No authentication**: Add auth if exposing publicly
- **Read-only**: Dashboard only reads from Neo4j
- **No secrets**: Don't commit credentials to git

---

## 🚀 Deployment

### Production Deployment

For production deployment, consider:

1. **Add authentication**: Streamlit supports OAuth
2. **Use HTTPS**: Configure reverse proxy (nginx)
3. **Secure Neo4j**: Enable auth, use encrypted connections
4. **Environment variables**: Never hardcode credentials
5. **Monitoring**: Add logging and error tracking

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements-dashboard.txt .
RUN pip install -r requirements-dashboard.txt

COPY dashboard/ dashboard/
COPY src/ src/

EXPOSE 8501

CMD ["streamlit", "run", "dashboard/app.py"]
```

---

## 🔧 Improving Agent Performance

The dashboard helps you identify and fix delegation issues. See the comprehensive guide:

**📖 [Agent Improvement Guide](../docs/AGENT_IMPROVEMENT_GUIDE.md)**

### Quick Fixes for Low Success Rates

If you see low success rates (like Performance_Agent → DevOps_Agent):

1. **Check Ontology Tab**: Identify if it violates expected patterns
2. **Use GraphRAG**: Get AI recommendations for better delegation targets
3. **Add Guardrails**: Prevent bad delegations before they happen
   ```python
   from agenticqa.delegation.guardrails import DelegationGuardrails

   validation = DelegationGuardrails.validate_delegation(
       from_agent="Performance_Agent",
       to_agent="DevOps_Agent",
       task_type="load_test"
   )

   if not validation["valid"]:
       # Use suggested alternative
       to_agent = validation["alternatives"][0]
   ```

4. **Monitor**: Use Live Activity tab to watch improvements in real-time

For detailed strategies, see the [full improvement guide](../docs/AGENT_IMPROVEMENT_GUIDE.md).

---

## 📚 API Reference

### DelegationGraphStore Advanced Methods

```python
# Predict failure risk
risk = store.predict_delegation_failure_risk(
    from_agent="SDET_Agent",
    to_agent="SRE_Agent",
    task_type="generate_tests"
)

# Find optimal path
path = store.find_optimal_delegation_path(
    from_agent="SDET_Agent",
    target_capability="deploy",
    max_hops=3
)

# Calculate costs
costs = store.calculate_cost_optimization(
    time_window_hours=24,
    cost_per_second=0.001
)

# Get trends
trends = store.get_delegation_trends(
    days=7,
    granularity="day"
)
```

---

## 🎓 For Shelf Interview

### Demo Script (5 Minutes)

1. **Show Dashboard** (1 min)
   - Launch: `streamlit run dashboard/app.py`
   - Overview: "Real-time analytics for 7 AI agents"

2. **Network Visualization** (2 min)
   - Click "Network" tab
   - "This shows agent collaboration patterns"
   - Hover over edges: "Success rates, durations"
   - "Color coding shows performance"

3. **Advanced Analytics** (1 min)
   - Performance tab: "Bottleneck detection"
   - "P95 latencies, success rate trends"

4. **GraphRAG** (1 min)
   - GraphRAG tab
   - "AI-powered delegation recommendations"
   - "Based on Neo4j graph patterns + Weaviate semantic search"

### Key Talking Points

- "Built with Streamlit, Plotly, and Neo4j"
- "Real-time network visualization of agent collaboration"
- "Advanced analytics: failure prediction, path optimization, cost analysis"
- "GraphRAG combining semantic (Weaviate) and structural (Neo4j) intelligence"

### Questions to Expect

**Q: How does the dashboard handle real-time updates?**
A: Streamlit rerun mechanism with optional 30-second auto-refresh

**Q: What's the performance with large datasets?**
A: Neo4j indexes ensure sub-second queries even with millions of delegations

**Q: Can this be deployed for production monitoring?**
A: Yes, with auth, HTTPS, and Docker deployment (showed example)

---

## 🌟 Features Summary

✅ Real-time agent collaboration network
✅ Interactive visualizations (Plotly)
✅ Performance metrics and bottleneck detection
✅ GraphRAG delegation recommendations
✅ Predictive failure analysis
✅ Optimal path finding
✅ Cost optimization suggestions
✅ Trend analysis over time
✅ Auto-refresh capability
✅ Production-ready (with proper deployment)

---

## 📞 Support

- **Documentation**: [docs/NEO4J_QUICKSTART.md](../docs/NEO4J_QUICKSTART.md)
- **Schema Reference**: [docs/NEO4J_SCHEMA.md](../docs/NEO4J_SCHEMA.md)
- **GitHub**: https://github.com/nhomyk/AgenticQA

---

**Built with ❤️ for demonstrating production-grade graph analytics**

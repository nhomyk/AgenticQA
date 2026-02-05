"""
AgenticQA Analytics Dashboard

Real-time visualization of agent collaboration, delegation patterns, and performance metrics.

Run: streamlit run dashboard/app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agenticqa.graph import DelegationGraphStore

# Page config
st.set_page_config(
    page_title="AgenticQA Analytics",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .success {
        color: #28a745;
    }
    .warning {
        color: #ffc107;
    }
    .danger {
        color: #dc3545;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_graph_store():
    """Get cached Neo4j connection"""
    try:
        store = DelegationGraphStore()
        store.connect()
        return store
    except Exception as e:
        st.error(f"Failed to connect to Neo4j: {e}")
        st.info("Make sure Neo4j is running: `docker-compose -f docker-compose.weaviate.yml up -d neo4j`")
        return None


def render_header():
    """Render dashboard header"""
    st.markdown('<h1 class="main-header">🤖 AgenticQA Analytics Dashboard</h1>', unsafe_allow_html=True)
    st.markdown("---")


def render_overview_metrics(store: DelegationGraphStore):
    """Render overview metrics cards"""
    st.subheader("📊 System Overview")

    stats = store.get_database_stats()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="Total Agents",
            value=stats.get("total_agents", 0),
            delta=None,
            help="Number of registered AI agents"
        )

    with col2:
        st.metric(
            label="Total Delegations",
            value=stats.get("total_delegations", 0),
            delta=None,
            help="All-time delegation count"
        )

    with col3:
        st.metric(
            label="Total Executions",
            value=stats.get("total_executions", 0),
            delta=None,
            help="All-time execution count"
        )


def render_collaboration_network(store: DelegationGraphStore):
    """Render agent collaboration network graph"""
    st.subheader("🕸️ Agent Collaboration Network")

    # Get delegation data
    results = store.get_delegation_success_rate_by_pair(limit=50)

    if not results:
        st.info("No delegation data available yet. Run some agents to populate the graph!")
        return

    # Build network graph
    nodes = set()
    edges = []

    for row in results:
        from_agent = row["from_agent"]
        to_agent = row["to_agent"]
        weight = row["total"]
        success_rate = row["success_rate"]

        nodes.add(from_agent)
        nodes.add(to_agent)

        edges.append({
            "source": from_agent,
            "target": to_agent,
            "weight": weight,
            "success_rate": success_rate,
            "avg_duration": row.get("avg_duration_ms", 0)
        })

    # Create network visualization
    node_list = list(nodes)
    node_x = []
    node_y = []
    node_text = []

    # Simple circular layout
    import math
    n = len(node_list)
    for i, node in enumerate(node_list):
        angle = 2 * math.pi * i / n
        node_x.append(math.cos(angle))
        node_y.append(math.sin(angle))
        node_text.append(node)

    # Create edges
    edge_trace = []
    for edge in edges:
        src_idx = node_list.index(edge["source"])
        tgt_idx = node_list.index(edge["target"])

        # Color based on success rate
        color = "#28a745" if edge["success_rate"] > 0.8 else "#ffc107" if edge["success_rate"] > 0.5 else "#dc3545"

        edge_trace.append(go.Scatter(
            x=[node_x[src_idx], node_x[tgt_idx], None],
            y=[node_y[src_idx], node_y[tgt_idx], None],
            mode='lines',
            line=dict(width=edge["weight"], color=color),
            hoverinfo='text',
            text=f"{edge['source']} → {edge['target']}<br>Delegations: {edge['weight']}<br>Success: {edge['success_rate']*100:.1f}%<br>Avg: {edge['avg_duration']:.0f}ms",
            showlegend=False
        ))

    # Create nodes
    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode='markers+text',
        marker=dict(
            size=30,
            color='#1f77b4',
            line=dict(width=2, color='white')
        ),
        text=node_text,
        textposition="top center",
        hoverinfo='text',
        hovertext=node_text,
        showlegend=False
    )

    # Create figure
    fig = go.Figure(data=edge_trace + [node_trace])
    fig.update_layout(
        showlegend=False,
        hovermode='closest',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=600,
        plot_bgcolor='rgba(0,0,0,0)'
    )

    st.plotly_chart(fig, use_container_width=True)

    # Legend
    st.caption("🟢 High success (>80%) | 🟡 Medium success (50-80%) | 🔴 Low success (<50%)")


def render_top_agents(store: DelegationGraphStore):
    """Render top delegated-to agents"""
    st.subheader("🏆 Most Delegated-To Agents")

    results = store.get_most_delegated_agents(limit=10)

    if not results:
        st.info("No delegation data available.")
        return

    df = pd.DataFrame(results)
    df["success_rate"] = (df["successes"] / df["delegation_count"] * 100).round(1)
    df["avg_duration_ms"] = df["avg_duration_ms"].fillna(0).round(0)

    # Bar chart
    fig = px.bar(
        df,
        x="agent",
        y="delegation_count",
        color="success_rate",
        color_continuous_scale="RdYlGn",
        title="Delegation Count by Agent",
        labels={"delegation_count": "Delegations", "agent": "Agent", "success_rate": "Success %"},
        hover_data={"avg_duration_ms": ":.0f"}
    )

    st.plotly_chart(fig, use_container_width=True)

    # Data table
    st.dataframe(
        df[["agent", "delegation_count", "success_rate", "avg_duration_ms"]].rename(columns={
            "agent": "Agent",
            "delegation_count": "Delegations",
            "success_rate": "Success Rate (%)",
            "avg_duration_ms": "Avg Duration (ms)"
        }),
        use_container_width=True,
        hide_index=True
    )


def render_performance_metrics(store: DelegationGraphStore):
    """Render performance metrics and bottlenecks"""
    st.subheader("⚡ Performance Analysis")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Bottleneck Detection")
        bottlenecks = store.find_bottleneck_agents(slow_threshold_ms=1000.0, min_count=2)

        if bottlenecks:
            df = pd.DataFrame(bottlenecks)
            df["avg_duration"] = df["avg_duration"].round(0)
            df["p95_duration"] = df["p95_duration"].fillna(0).round(0)

            fig = px.bar(
                df,
                x="agent",
                y="avg_duration",
                color="slow_delegations",
                title="Slow Delegations by Agent",
                labels={"avg_duration": "Avg Duration (ms)", "agent": "Agent", "slow_delegations": "Count"},
                color_continuous_scale="Reds"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("✅ No bottlenecks detected!")

    with col2:
        st.markdown("#### Success Rate Trends")
        success_rates = store.get_delegation_success_rate_by_pair(limit=10)

        if success_rates:
            df = pd.DataFrame(success_rates)
            df["pair"] = df["from_agent"] + " → " + df["to_agent"]
            df["success_rate_pct"] = (df["success_rate"] * 100).round(1)

            fig = px.bar(
                df,
                x="pair",
                y="success_rate_pct",
                color="success_rate_pct",
                color_continuous_scale="RdYlGn",
                range_color=[0, 100],
                title="Success Rate by Agent Pair",
                labels={"success_rate_pct": "Success Rate (%)", "pair": "Agent Pair"}
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)


def render_delegation_chains(store: DelegationGraphStore):
    """Render delegation chain analysis"""
    st.subheader("🔗 Delegation Chains")

    chains = store.find_delegation_chains(min_length=2, limit=20)

    if not chains:
        st.info("No multi-hop delegation chains found.")
        return

    df = pd.DataFrame(chains)
    df["total_duration_ms"] = df["total_duration_ms"].fillna(0).round(0)

    # Distribution chart
    fig = px.histogram(
        df,
        x="chain_length",
        title="Distribution of Delegation Chain Lengths",
        labels={"chain_length": "Chain Length", "count": "Frequency"},
        nbins=10
    )
    st.plotly_chart(fig, use_container_width=True)

    # Top chains table
    st.markdown("#### Longest Delegation Chains")
    display_df = df.nlargest(10, "chain_length")[["origin", "destination", "chain_length", "total_duration_ms"]]
    st.dataframe(
        display_df.rename(columns={
            "origin": "Origin",
            "destination": "Destination",
            "chain_length": "Hops",
            "total_duration_ms": "Total Duration (ms)"
        }),
        use_container_width=True,
        hide_index=True
    )


def render_graphrag_recommendations(store: DelegationGraphStore):
    """Render GraphRAG delegation recommendations"""
    st.subheader("🧠 GraphRAG Recommendations")

    st.markdown("**Get AI-powered delegation recommendations based on historical patterns**")

    # Hybrid RAG Architecture Diagram
    st.markdown("---")
    st.markdown("### 🏗️ Hybrid RAG Architecture")

    # Create interactive architecture diagram using Plotly
    fig = go.Figure()

    # Define component positions
    components = {
        # Input layer
        "query": {"x": 0.5, "y": 1.0, "width": 0.2, "height": 0.08, "color": "#FFD700", "text": "Agent Query<br>(Task Type)"},

        # GraphRAG orchestrator
        "graphrag": {"x": 0.5, "y": 0.80, "width": 0.25, "height": 0.08, "color": "#9370DB", "text": "HybridGraphRAG<br>Orchestrator"},

        # Dual storage layer
        "weaviate": {"x": 0.25, "y": 0.55, "width": 0.2, "height": 0.15, "color": "#4CAF50", "text": "Weaviate<br>Vector Store<br><br>• 384-dim embeddings<br>• Semantic similarity<br>• Test examples"},
        "neo4j": {"x": 0.75, "y": 0.55, "width": 0.2, "height": 0.15, "color": "#008CC1", "text": "Neo4j<br>Graph Store<br><br>• Agent relationships<br>• Success patterns<br>• Delegation history"},

        # Processing layer
        "semantic": {"x": 0.25, "y": 0.30, "width": 0.18, "height": 0.08, "color": "#81C784", "text": "Semantic Match<br>(Cosine Similarity)"},
        "graph": {"x": 0.75, "y": 0.30, "width": 0.18, "height": 0.08, "color": "#29B6F6", "text": "Graph Traversal<br>(Cypher Query)"},

        # Synthesis layer
        "synthesis": {"x": 0.5, "y": 0.10, "width": 0.25, "height": 0.08, "color": "#FF6F61", "text": "Result Synthesis<br>(Weighted Ranking)"},

        # Output
        "output": {"x": 0.5, "y": -0.05, "width": 0.22, "height": 0.08, "color": "#FFD700", "text": "Recommended<br>Agent"}
    }

    # Draw boxes
    for name, comp in components.items():
        fig.add_shape(
            type="rect",
            x0=comp["x"] - comp["width"]/2,
            y0=comp["y"] - comp["height"]/2,
            x1=comp["x"] + comp["width"]/2,
            y1=comp["y"] + comp["height"]/2,
            line=dict(color="white", width=2),
            fillcolor=comp["color"],
            opacity=0.8
        )

        # Add text labels
        fig.add_annotation(
            x=comp["x"],
            y=comp["y"],
            text=comp["text"],
            showarrow=False,
            font=dict(size=10, color="white", family="Arial Black"),
            align="center"
        )

    # Draw arrows (connections)
    arrows = [
        # Query to GraphRAG
        {"from": "query", "to": "graphrag", "color": "#FFD700"},

        # GraphRAG to both stores
        {"from": "graphrag", "to": "weaviate", "color": "#4CAF50"},
        {"from": "graphrag", "to": "neo4j", "color": "#008CC1"},

        # Stores to processors
        {"from": "weaviate", "to": "semantic", "color": "#4CAF50"},
        {"from": "neo4j", "to": "graph", "color": "#008CC1"},

        # Processors to synthesis
        {"from": "semantic", "to": "synthesis", "color": "#81C784"},
        {"from": "graph", "to": "synthesis", "color": "#29B6F6"},

        # Synthesis to output
        {"from": "synthesis", "to": "output", "color": "#FF6F61"}
    ]

    for arrow in arrows:
        from_comp = components[arrow["from"]]
        to_comp = components[arrow["to"]]

        fig.add_annotation(
            x=to_comp["x"],
            y=to_comp["y"] + to_comp["height"]/2,
            ax=from_comp["x"],
            ay=from_comp["y"] - from_comp["height"]/2,
            xref="x", yref="y",
            axref="x", ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowsize=1.5,
            arrowwidth=3,
            arrowcolor=arrow["color"],
            opacity=0.7
        )

    # Add data flow annotations
    fig.add_annotation(x=0.15, y=0.65, text="Vector<br>Embeddings", showarrow=False,
                      font=dict(size=9, color="#4CAF50"), bgcolor="rgba(76, 175, 80, 0.2)")
    fig.add_annotation(x=0.85, y=0.65, text="Graph<br>Patterns", showarrow=False,
                      font=dict(size=9, color="#008CC1"), bgcolor="rgba(0, 140, 193, 0.2)")

    # Configure layout
    fig.update_layout(
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.1, 1.1]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.15, 1.1]),
        plot_bgcolor='rgba(14, 17, 23, 0.95)',
        paper_bgcolor='rgba(14, 17, 23, 0.95)',
        height=600,
        margin=dict(l=20, r=20, t=40, b=20),
        title={
            'text': "Hybrid RAG: Combining Vector Search + Graph Analytics",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 16, 'color': 'white'}
        }
    )

    st.plotly_chart(fig, use_container_width=True)

    # Explanation
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**🎯 Why Hybrid?**")
        st.markdown("""
        - **Weaviate**: Finds semantically similar tasks ("generate tests" ≈ "create test cases")
        - **Neo4j**: Finds historically successful delegation paths
        - **Combined**: Best match considering both meaning AND proven success
        """)

    with col2:
        st.markdown("**⚡ Performance Benefits**")
        st.markdown("""
        - 📈 Higher accuracy than vector-only search
        - 🎯 Context-aware recommendations
        - 🔄 Self-improving (learns from each delegation)
        """)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        from_agent = st.selectbox(
            "From Agent:",
            ["SDET_Agent", "Fullstack_Agent", "Compliance_Agent", "SRE_Agent", "DevOps_Agent", "QA_Agent", "Performance_Agent"]
        )

    with col2:
        task_type = st.text_input("Task Type:", value="generate_tests")

    if st.button("Get Recommendation"):
        recommendation = store.recommend_delegation_target(
            from_agent=from_agent,
            task_type=task_type,
            acceptable_duration_ms=5000.0,
            min_success_count=2
        )

        if recommendation:
            st.success(f"✅ Recommended: **{recommendation['recommended_agent']}**")

            col1, col2, col3 = st.columns(3)
            col1.metric("Success Count", recommendation['success_count'])
            col2.metric("Avg Duration", f"{recommendation['avg_duration']:.0f} ms")
            col3.metric("Priority Score", f"{recommendation['priority_score']:.2f}")

            st.info(f"Based on {recommendation['success_count']} successful historical delegations")
        else:
            st.warning("No recommendation available. Need more historical data for this task type.")


def render_live_activity(store: DelegationGraphStore):
    """Render live activity and current workflow"""
    st.subheader("🔴 Live Activity & Current Workflow")

    # Get recent delegations
    with store.session() as session:
        result = session.run("""
            MATCH (from:Agent)-[d:DELEGATES_TO]->(to:Agent)
            RETURN from.name as from_agent,
                   to.name as to_agent,
                   d.status as status,
                   d.duration_ms as duration_ms,
                   d.timestamp as timestamp,
                   d.task as task,
                   d.error_message as error_message
            ORDER BY d.timestamp DESC
            LIMIT 50
        """)

        recent_delegations = []
        for record in result:
            # Convert Neo4j DateTime to Python datetime
            timestamp = record["timestamp"]
            if hasattr(timestamp, 'to_native'):
                timestamp = timestamp.to_native()

            recent_delegations.append({
                "from_agent": record["from_agent"],
                "to_agent": record["to_agent"],
                "status": record["status"],
                "duration_ms": record["duration_ms"],
                "timestamp": timestamp,
                "task": record["task"],
                "error_message": record["error_message"]
            })

    if not recent_delegations:
        st.info("No recent activity. Run some agents to populate this view!")
        return

    # Activity timeline
    st.markdown("#### Recent Delegations")

    df = pd.DataFrame(recent_delegations)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Create timeline visualization
    df["status_color"] = df["status"].map({
        "success": "🟢",
        "failed": "🔴",
        "pending": "🟡",
        "timeout": "⚫"
    })

    # Display as interactive table
    display_df = df[["timestamp", "status_color", "from_agent", "to_agent", "duration_ms"]].copy()
    display_df.columns = ["Time", "Status", "From", "To", "Duration (ms)"]
    st.dataframe(display_df, use_container_width=True, height=400)

    # Activity metrics
    col1, col2, col3, col4 = st.columns(4)

    success_count = len(df[df["status"] == "success"])
    failed_count = len(df[df["status"] == "failed"])
    total = len(df)
    success_rate = (success_count / total * 100) if total > 0 else 0

    col1.metric("Total Activity", total)
    col2.metric("Success", success_count)
    col3.metric("Failed", failed_count)
    col4.metric("Success Rate", f"{success_rate:.1f}%")

    # Activity over time
    st.markdown("#### Activity Timeline")
    df_timeline = df.groupby(df["timestamp"].dt.floor("H"))["status"].count().reset_index()
    df_timeline.columns = ["Hour", "Count"]

    fig = px.line(df_timeline, x="Hour", y="Count",
                  title="Delegations per Hour",
                  labels={"Count": "Number of Delegations", "Hour": "Time"})
    st.plotly_chart(fig, use_container_width=True)


def render_ontology(store: DelegationGraphStore):
    """Render workflow ontology and compare with actual collaboration"""
    st.subheader("🏗️ Workflow Ontology & Design vs. Reality")

    st.markdown("""
    This page shows the **designed ontology** (what the system is supposed to do)
    vs. the **actual collaboration patterns** (what's really happening).
    """)

    # Ontology Definition
    st.markdown("---")
    st.markdown("### 📐 Designed Ontology")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Agent Types (Roles)")
        st.markdown("""
        - **SDET_Agent** (QA): Test generation, validation
        - **SRE_Agent** (DevOps): Deployment, monitoring, rollback
        - **Fullstack_Agent** (Dev): Feature implementation, code review
        - **Compliance_Agent** (Security): Security scans, audits
        - **DevOps_Agent** (DevOps): CI/CD, infrastructure
        - **QA_Agent** (QA): Manual testing, validation
        - **Performance_Agent** (QA): Load testing, benchmarks
        """)

    with col2:
        st.markdown("#### Task Types (Capabilities)")

        # Get actual task types from database
        with store.session() as session:
            result = session.run("""
                MATCH ()-[d:DELEGATES_TO]->()
                WHERE d.task IS NOT NULL
                RETURN DISTINCT d.task as task
                LIMIT 50
            """)

            task_types = set()
            for record in result:
                try:
                    import json
                    task_data = json.loads(record["task"]) if isinstance(record["task"], str) else record["task"]
                    if isinstance(task_data, dict):
                        task_types.add(task_data.get("type", "unknown"))
                except:
                    pass

        if task_types:
            for task_type in sorted(task_types):
                st.markdown(f"- `{task_type}`")
        else:
            st.info("No task data available yet")

    # Designed vs Actual Comparison
    st.markdown("---")
    st.markdown("### 🔍 Design vs. Reality Analysis")

    # Get actual agent types and their activity
    with store.session() as session:
        result = session.run("""
            MATCH (a:Agent)
            RETURN a.name as agent,
                   a.type as type,
                   a.total_delegations_made as made,
                   a.total_delegations_received as received
            ORDER BY a.total_delegations_made DESC
        """)

        agents_data = []
        for record in result:
            agents_data.append({
                "Agent": record["agent"],
                "Type": record["type"] or "unknown",
                "Delegations Made": record["made"] or 0,
                "Delegations Received": record["received"] or 0,
                "Net Activity": (record["made"] or 0) - (record["received"] or 0)
            })

    if agents_data:
        df = pd.DataFrame(agents_data)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Agent Activity Profile")
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Classify agents by behavior
            st.markdown("**Agent Classification:**")
            orchestrators = df[df["Net Activity"] > 5]["Agent"].tolist()
            workers = df[df["Net Activity"] < -5]["Agent"].tolist()
            balanced = df[(df["Net Activity"] >= -5) & (df["Net Activity"] <= 5)]["Agent"].tolist()

            if orchestrators:
                st.success(f"🎯 **Orchestrators** (delegate more): {', '.join(orchestrators)}")
            if workers:
                st.info(f"⚙️ **Workers** (receive more): {', '.join(workers)}")
            if balanced:
                st.warning(f"⚖️ **Balanced**: {', '.join(balanced)}")

        with col2:
            st.markdown("#### Delegation Heatmap by Type")

            # Get delegation patterns by agent type
            with store.session() as session:
                result = session.run("""
                    MATCH (from:Agent)-[d:DELEGATES_TO]->(to:Agent)
                    RETURN from.type as from_type,
                           to.type as to_type,
                           count(d) as count
                """)

                heatmap_data = []
                for record in result:
                    heatmap_data.append({
                        "From Type": record["from_type"] or "unknown",
                        "To Type": record["to_type"] or "unknown",
                        "Count": record["count"]
                    })

            if heatmap_data:
                df_heatmap = pd.DataFrame(heatmap_data)
                pivot = df_heatmap.pivot(index="From Type", columns="To Type", values="Count").fillna(0)

                fig = px.imshow(pivot,
                               labels=dict(x="To Agent Type", y="From Agent Type", color="Delegations"),
                               title="Cross-Type Delegation Patterns",
                               color_continuous_scale="Blues")
                st.plotly_chart(fig, use_container_width=True)

    # Correlation Analysis
    st.markdown("---")
    st.markdown("### 📊 Correlation: Design vs. Actual Behavior")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Expected Patterns (Ontology)")
        st.markdown("""
        **Designed workflows:**
        - SDET → Fullstack (test generation)
        - SDET → SRE (deployment validation)
        - Fullstack → QA (code validation)
        - DevOps → SRE (deployment execution)
        - Compliance → SDET (security scans)
        - Performance → DevOps (load testing)
        """)

    with col2:
        st.markdown("#### Actual Patterns (Reality)")

        # Get top delegation pairs
        with store.session() as session:
            result = session.run("""
                MATCH (from:Agent)-[d:DELEGATES_TO]->(to:Agent)
                RETURN from.name as from_agent,
                       to.name as to_agent,
                       count(d) as count,
                       avg(d.duration_ms) as avg_duration
                ORDER BY count DESC
                LIMIT 10
            """)

            st.markdown("**Top 10 actual delegation paths:**")
            for i, record in enumerate(result, 1):
                st.markdown(f"{i}. **{record['from_agent']}** → **{record['to_agent']}** ({record['count']} times, avg {record['avg_duration']:.0f}ms)")

    # Anomaly Detection
    st.markdown("---")
    st.markdown("### ⚠️ Anomalies & Insights")

    insights = []

    # Check for unexpected patterns
    with store.session() as session:
        # Find agents delegating to themselves
        result = session.run("""
            MATCH (a:Agent)-[d:DELEGATES_TO]->(a)
            RETURN a.name as agent, count(d) as count
        """)
        self_delegations = list(result)

        # Find very deep chains
        result = session.run("""
            MATCH ()-[d:DELEGATES_TO]->()
            WHERE d.depth > 3
            RETURN d.depth as depth, count(*) as count
            ORDER BY depth DESC
            LIMIT 5
        """)
        deep_chains = list(result)

        # Find high-latency delegations
        result = session.run("""
            MATCH (from:Agent)-[d:DELEGATES_TO]->(to:Agent)
            WHERE d.duration_ms > 4000
            RETURN from.name as from_agent,
                   to.name as to_agent,
                   avg(d.duration_ms) as avg_duration,
                   count(d) as count
            ORDER BY avg_duration DESC
            LIMIT 5
        """)
        slow_delegations = list(result)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Design Violations")

        if self_delegations:
            st.warning("⚠️ **Self-delegations detected** (not in ontology):")
            for rec in self_delegations:
                st.markdown(f"- {rec['agent']}: {rec['count']} times")
        else:
            st.success("✅ No self-delegations")

        if deep_chains:
            st.warning("⚠️ **Deep delegation chains** (may indicate inefficiency):")
            for rec in deep_chains:
                st.markdown(f"- Depth {rec['depth']}: {rec['count']} occurrences")
        else:
            st.success("✅ All chains are shallow (< 4 hops)")

    with col2:
        st.markdown("#### Performance Insights")

        if slow_delegations:
            st.info("🐌 **Slowest delegation paths:**")
            for rec in slow_delegations:
                st.markdown(f"- {rec['from_agent']} → {rec['to_agent']}: {rec['avg_duration']:.0f}ms avg ({rec['count']} times)")
        else:
            st.success("✅ All delegations are fast")

    # Ontology Completeness
    st.markdown("---")
    st.markdown("### 📈 Ontology Coverage")

    col1, col2, col3 = st.columns(3)

    # Calculate coverage metrics
    total_possible_edges = len(agents_data) * (len(agents_data) - 1)  # All possible directed edges

    with store.session() as session:
        result = session.run("""
            MATCH (from:Agent)-[d:DELEGATES_TO]->(to:Agent)
            RETURN count(DISTINCT from.name + '->' + to.name) as actual_edges
        """)
        actual_edges = result.single()["actual_edges"]

    coverage = (actual_edges / total_possible_edges * 100) if total_possible_edges > 0 else 0

    col1.metric("Possible Paths", total_possible_edges)
    col2.metric("Active Paths", actual_edges)
    col3.metric("Coverage", f"{coverage:.1f}%")

    # IP Considerations
    st.markdown("---")
    st.markdown("### 🔒 IP & Visibility Considerations")

    st.info("""
    **For AgenticQA (Open Source):**
    - ✅ Ontology is public (part of documentation)
    - ✅ Task types are generic and shareable
    - ✅ Safe to display in demos and documentation

    **For Enterprise Systems:**
    - ⚠️ May contain proprietary workflows
    - ⚠️ Custom task types could reveal business logic
    - ⚠️ Consider access controls for ontology viewer
    - ✅ Useful for internal teams (engineering, product, support)
    """)


def render_pipeline_flow(store: DelegationGraphStore):
    """Render data flow pipeline visualization"""
    st.subheader("🔄 Pipeline Data Flow")

    st.markdown("""
    This view shows how data flows through AgenticQA's hybrid architecture combining
    vector search (Weaviate) and graph analytics (Neo4j).
    """)

    # Pipeline architecture diagram
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### RAG Pipeline Flow")
        st.markdown("""
        ```
        📝 Test Requirements
              ↓
        🔤 Sentence Transformer
              ↓
        🧮 Vector Embeddings (384-dim)
              ↓
        💾 Weaviate Vector Store
              ↓
        🔍 Semantic Similarity Search
              ↓
        📊 Retrieved Test Examples
              ↓
        🤖 LLM Generation
              ↓
        ✅ Generated Tests
        ```
        """)

    with col2:
        st.markdown("#### Delegation Pipeline Flow")
        st.markdown("""
        ```
        🎯 Agent Task
              ↓
        🔍 Find Best Delegate (GraphRAG)
              ├─ Neo4j: Historical Success
              └─ Weaviate: Semantic Match
              ↓
        📨 Delegate to Target Agent
              ↓
        ⚙️  Execute Task
              ↓
        📊 Record to Neo4j
              ├─ Success/Failure
              ├─ Duration
              └─ Chain Depth
              ↓
        🔄 Update Agent Metrics
        ```
        """)

    st.markdown("---")

    # Data flow metrics
    st.markdown("#### Hybrid Storage Metrics")

    stats = store.get_database_stats()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Neo4j Graph Store**")
        st.metric("Agents (Nodes)", stats.get("total_agents", 0))
        st.metric("Delegations (Edges)", stats.get("total_delegations", 0))
        st.caption("Tracks collaboration patterns, success rates, delegation chains")

    with col2:
        st.markdown("**Weaviate Vector Store**")
        st.info("Vector embeddings for semantic search")
        st.caption("Stores test embeddings, enables similarity search, RAG retrieval")

    with col3:
        st.markdown("**Hybrid GraphRAG**")
        st.success("Best of both worlds")
        st.caption("Combines graph structure + semantic meaning for intelligent recommendations")

    # Pipeline performance
    st.markdown("#### Pipeline Performance")

    with store.session() as session:
        result = session.run("""
            MATCH ()-[d:DELEGATES_TO]->()
            WHERE d.duration_ms IS NOT NULL
            RETURN
                avg(d.duration_ms) as avg_duration,
                percentileCont(d.duration_ms, 0.50) as p50_duration,
                percentileCont(d.duration_ms, 0.95) as p95_duration,
                max(d.duration_ms) as max_duration
        """)

        perf = result.single()
        if perf:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Avg Duration", f"{perf['avg_duration']:.0f} ms")
            col2.metric("P50 Duration", f"{perf['p50_duration']:.0f} ms")
            col3.metric("P95 Duration", f"{perf['p95_duration']:.0f} ms")
            col4.metric("Max Duration", f"{perf['max_duration']:.0f} ms")

    # Data freshness
    st.markdown("#### Data Freshness")
    with store.session() as session:
        result = session.run("""
            MATCH (a:Agent)
            RETURN a.name as agent,
                   a.last_active as last_active,
                   a.total_delegations_made as delegations_made,
                   a.total_delegations_received as delegations_received
            ORDER BY a.last_active DESC
        """)

        agents_activity = []
        for record in result:
            agents_activity.append({
                "Agent": record["agent"],
                "Last Active": record["last_active"],
                "Delegations Made": record["delegations_made"] or 0,
                "Delegations Received": record["delegations_received"] or 0
            })

        if agents_activity:
            df = pd.DataFrame(agents_activity)
            st.dataframe(df, use_container_width=True, hide_index=True)


def main():
    """Main dashboard"""
    render_header()

    # Sidebar
    with st.sidebar:
        st.title("📊 Navigation")
        st.markdown("---")

        page = st.radio(
            "Select View:",
            ["Overview", "Network", "Performance", "Chains", "GraphRAG", "Live Activity", "Pipeline Flow", "Ontology"],
            index=0
        )

        st.markdown("---")
        st.markdown("### ⚙️ Settings")

        auto_refresh = st.checkbox("Auto-refresh (30s)", value=False)

        if st.button("🔄 Refresh Data"):
            st.cache_resource.clear()
            st.rerun()

        st.markdown("---")
        st.markdown("### 📚 Resources")
        st.markdown("[Neo4j Browser](http://localhost:7474)")
        st.markdown("[Documentation](https://github.com/nhomyk/AgenticQA)")

        # Auto-refresh
        if auto_refresh:
            import time
            time.sleep(30)
            st.rerun()

    # Get store
    store = get_graph_store()

    if not store:
        st.error("Cannot connect to Neo4j. Please start the database.")
        return

    # Render selected page
    if page == "Overview":
        render_overview_metrics(store)
        st.markdown("---")
        render_top_agents(store)

    elif page == "Network":
        render_collaboration_network(store)

    elif page == "Performance":
        render_performance_metrics(store)

    elif page == "Chains":
        render_delegation_chains(store)

    elif page == "GraphRAG":
        render_graphrag_recommendations(store)

    elif page == "Live Activity":
        render_live_activity(store)

    elif page == "Pipeline Flow":
        render_pipeline_flow(store)

    elif page == "Ontology":
        render_ontology(store)

    # Footer
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | AgenticQA Analytics Dashboard v1.0")


if __name__ == "__main__":
    main()

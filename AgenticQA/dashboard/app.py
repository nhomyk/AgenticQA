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
            fig.update_xaxis(tickangle=45)
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


def main():
    """Main dashboard"""
    render_header()

    # Sidebar
    with st.sidebar:
        st.title("📊 Navigation")
        st.markdown("---")

        page = st.radio(
            "Select View:",
            ["Overview", "Network", "Performance", "Chains", "GraphRAG"],
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

    # Footer
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | AgenticQA Analytics Dashboard v1.0")


if __name__ == "__main__":
    main()

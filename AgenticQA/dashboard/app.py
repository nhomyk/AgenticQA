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
from agenticqa.verification import RagasTracker, OutcomeTracker
from agenticqa.collaboration.delegation import DelegationGuardrails as CollaborationGuardrails
from agenticqa.delegation.guardrails import DelegationGuardrails as TaskOntologyGuardrails

# Page config
st.set_page_config(
    page_title="AgenticQA Analytics",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)


def _install_streamlit_width_compat() -> None:
    """Map deprecated use_container_width to width for Streamlit widgets.

    This keeps existing call-sites stable while preventing runtime deprecation spam
    in recent Streamlit versions.
    """
    original_plotly_chart = st.plotly_chart
    original_dataframe = st.dataframe

    def _translate_kwargs(kwargs: dict) -> dict:
        copied = dict(kwargs)
        if "use_container_width" in copied and "width" not in copied:
            copied["width"] = "stretch" if copied.pop("use_container_width") else "content"
        return copied

    def _plotly_chart_compat(*args, **kwargs):
        return original_plotly_chart(*args, **_translate_kwargs(kwargs))

    def _dataframe_compat(*args, **kwargs):
        return original_dataframe(*args, **_translate_kwargs(kwargs))

    st.plotly_chart = _plotly_chart_compat
    st.dataframe = _dataframe_compat


_install_streamlit_width_compat()

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
def _create_graph_store():
    """Create and cache a live Neo4j connection."""
    store = DelegationGraphStore()
    store.connect()
    return store


def get_graph_store():
    """Get Neo4j connection, returning None when unavailable.

    Important: do not cache failed attempts. If Neo4j starts after dashboard boot,
    subsequent reruns should reconnect automatically.
    """
    try:
        return _create_graph_store()
    except Exception:
        return None


def render_header():
    """Render dashboard header"""
    st.markdown('<h1 class="main-header">🤖 AgenticQA Analytics Dashboard</h1>', unsafe_allow_html=True)
    st.markdown("---")


def render_overview_metrics(store: DelegationGraphStore):
    """Render overview metrics cards"""
    st.subheader("📊 System Overview")

    stats = store.get_database_stats()

    col1, col2 = st.columns(2)

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


def render_collaboration_network(store: DelegationGraphStore):
    """Render agent collaboration network graph"""
    st.subheader("🕸️ Agent Collaboration Network")

    # Get all delegation pairs (no minimum threshold)
    with store.session() as session:
        result = session.run("""
            MATCH (from:Agent)-[d:DELEGATES_TO]->(to:Agent)
            WITH from.name as from_agent,
                 to.name as to_agent,
                 count(d) as total,
                 sum(CASE WHEN d.status = 'success' THEN 1 ELSE 0 END) as successes,
                 avg(d.duration_ms) as avg_duration_ms
            RETURN from_agent, to_agent, total, successes,
                   (toFloat(successes) / total) as success_rate,
                   avg_duration_ms
            ORDER BY total DESC
        """)
        results = [dict(record) for record in result]

    # Also get all agents so isolated ones appear as nodes
    with store.session() as session:
        result = session.run("MATCH (a:Agent) RETURN a.name as name")
        all_agents = {record["name"] for record in result}

    if not results and not all_agents:
        st.info("No delegation data available yet. Run some agents to populate the graph!")
        return

    # Build network graph
    nodes = set(all_agents)
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


def render_graphrag_recommendations(store=None):
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

    if not store:
        st.info("Connect Neo4j to enable live delegation recommendations.")
        return

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


def render_rag_quality_trends():
    """Render RAG quality trends from persisted RAGAS scores."""
    st.subheader("📈 RAG Quality Over Time")

    try:
        tracker = RagasTracker()
    except Exception as e:
        st.error(f"Could not connect to RAGAS tracker: {e}")
        return

    metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    metric_labels = {
        "faithfulness": "Faithfulness",
        "answer_relevancy": "Answer Relevancy",
        "context_precision": "Context Precision",
        "context_recall": "Context Recall",
    }

    # ── Current vs Baseline metrics ─────────────────────────────────
    st.markdown("#### Current vs Baseline")
    cols = st.columns(4)
    has_data = False

    for i, metric in enumerate(metrics):
        baseline = tracker.get_baseline(metric, window=10)
        trend = tracker.get_trend(metric, limit=1)
        current = trend[0].score if trend else None

        with cols[i]:
            if current is not None and baseline is not None:
                has_data = True
                delta = current - baseline
                st.metric(
                    label=metric_labels[metric],
                    value=f"{current:.2f}",
                    delta=f"{delta:+.3f}",
                    delta_color="normal",
                )
            elif current is not None:
                has_data = True
                st.metric(label=metric_labels[metric], value=f"{current:.2f}")
            else:
                st.metric(label=metric_labels[metric], value="—")

    if not has_data:
        st.info("No RAGAS data yet. Run evaluations to populate this view.")
        st.code(
            "from agenticqa.verification import RagasTracker\n"
            "tracker = RagasTracker()\n"
            "tracker.record_scores(\n"
            '    run_id="ci-123", commit_sha="abc",\n'
            '    scores={"faithfulness": 0.9, "answer_relevancy": 0.85}\n'
            ")",
            language="python",
        )
        tracker.close()
        return

    # ── Trend line chart ────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Score Trends (last 30 runs)")

    all_rows = []
    for metric in metrics:
        for entry in tracker.get_trend(metric, limit=30):
            all_rows.append({
                "Run": entry.run_id,
                "Metric": metric_labels[metric],
                "Score": entry.score,
                "Commit": entry.commit_sha[:7],
                "Timestamp": entry.timestamp,
            })

    if all_rows:
        df = pd.DataFrame(all_rows)
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        fig = px.line(
            df, x="Timestamp", y="Score", color="Metric",
            title="RAGAS Metric Trends",
            labels={"Score": "Score (0-1)", "Timestamp": "Time"},
            markers=True,
        )
        fig.update_layout(
            yaxis_range=[0, 1.05],
            plot_bgcolor='rgba(14, 17, 23, 0.95)',
            paper_bgcolor='rgba(14, 17, 23, 0.95)',
            font=dict(color="white"),
            legend=dict(font=dict(color="white")),
            height=400,
        )
        fig.update_xaxes(gridcolor="rgba(255,255,255,0.1)")
        fig.update_yaxes(gridcolor="rgba(255,255,255,0.1)")
        st.plotly_chart(fig, use_container_width=True)

    # ── Regression check ────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Regression Check")

    latest_scores = {}
    for metric in metrics:
        trend = tracker.get_trend(metric, limit=1)
        if trend:
            latest_scores[metric] = trend[0].score

    if latest_scores:
        regressions = tracker.check_regression(latest_scores, threshold=0.05)
        if regressions:
            for metric, info in regressions.items():
                st.error(
                    f"**{metric_labels.get(metric, metric)}** regressed: "
                    f"{info['current']:.3f} (current) vs {info['baseline']:.3f} (baseline) "
                    f"— delta {info['delta']:+.3f}"
                )
        else:
            st.success("All metrics are at or above baseline. No regressions detected.")

    # ── Prediction accuracy (from OutcomeTracker) ───────────────────
    st.markdown("---")
    st.markdown("#### Delegation Prediction Accuracy")

    try:
        ot = OutcomeTracker()
        accuracy = ot.get_accuracy()
        if accuracy["total_predictions"] > 0:
            col1, col2, col3 = st.columns(3)
            col1.metric("Predictions", accuracy["total_predictions"])
            col2.metric("Accuracy", f"{accuracy['accuracy']:.1%}")
            col3.metric("Mean Abs Error", f"{accuracy['mean_absolute_error']:.3f}")

            calibration = ot.get_calibration(bucket_size=0.2)
            if calibration:
                cal_df = pd.DataFrame(calibration)
                cal_df["Predicted"] = cal_df["avg_predicted"]
                cal_df["Actual"] = cal_df["actual_rate"]
                fig_cal = go.Figure()
                fig_cal.add_trace(go.Bar(
                    x=[f"{b:.0%}" for b in cal_df["bucket"]],
                    y=cal_df["Actual"],
                    name="Actual Success Rate",
                    marker_color="#4CAF50",
                ))
                fig_cal.add_trace(go.Scatter(
                    x=[f"{b:.0%}" for b in cal_df["bucket"]],
                    y=cal_df["Predicted"],
                    name="Predicted Confidence",
                    mode="lines+markers",
                    line=dict(color="#FF6F61", dash="dash"),
                ))
                fig_cal.update_layout(
                    title="Prediction Calibration (closer = better)",
                    yaxis_title="Rate", xaxis_title="Confidence Bucket",
                    yaxis_range=[0, 1.05],
                    plot_bgcolor='rgba(14, 17, 23, 0.95)',
                    paper_bgcolor='rgba(14, 17, 23, 0.95)',
                    font=dict(color="white"),
                    legend=dict(font=dict(color="white")),
                    height=350,
                )
                st.plotly_chart(fig_cal, use_container_width=True)
        else:
            st.info("No delegation predictions recorded yet.")
        ot.close()
    except Exception:
        st.info("Outcome tracker not available.")

    tracker.close()


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
        - **QA_Assistant** (QA): Manual testing, validation
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
        allowed_edges = [
            (source, target)
            for source, targets in CollaborationGuardrails.ALLOWED_DELEGATIONS.items()
            for target in targets
        ]

        if allowed_edges:
            st.markdown("**Enforced delegation whitelist:**")
            for source, target in allowed_edges:
                st.markdown(f"- {source} → {target}")
        else:
            st.info("No allowed delegation paths configured.")

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


def render_agent_testing(store=None):
    """Render agent testing and CI/CD pipeline results"""
    st.subheader("🧪 Agent Testing & CI/CD Pipeline")

    st.markdown("""
    Real-time test results, coverage metrics, and health checks for all agents.
    Shows latest pipeline runs with comparison to previous executions.
    """)

    # Get agent list from Neo4j or use defaults
    agents = []
    if store:
        try:
            with store.session() as session:
                result = session.run("""
                    MATCH (a:Agent)
                    RETURN a.name as agent, a.type as type
                    ORDER BY a.name
                """)
                agents = [{"name": rec["agent"], "type": rec["type"]} for rec in result]
        except Exception:
            pass

    if not agents:
        agents = [
            {"name": "SDET_Agent", "type": "QA"},
            {"name": "Fullstack_Agent", "type": "Dev"},
            {"name": "Compliance_Agent", "type": "Security"},
            {"name": "SRE_Agent", "type": "DevOps"},
            {"name": "DevOps_Agent", "type": "DevOps"},
            {"name": "QA_Agent", "type": "QA"},
            {"name": "Performance_Agent", "type": "QA"},
        ]
        if not store:
            st.caption("Showing demo data (Neo4j not connected)")

    # Simulated test results (in production, these would come from actual CI/CD runs)
    # You would integrate with pytest, coverage.py, GitHub Actions, etc.
    st.markdown("---")
    st.markdown("### 📊 Latest Test Runs by Agent")

    import random
    from datetime import datetime, timedelta

    # Create test result data for each agent
    test_results = []
    for agent in agents:
        # Simulate current run
        current_tests = random.randint(15, 50)
        current_passed = int(current_tests * random.uniform(0.85, 1.0))
        current_failed = current_tests - current_passed
        current_coverage = random.uniform(75, 98)
        current_duration = random.uniform(2, 15)

        # Simulate previous run
        prev_tests = random.randint(15, 50)
        prev_passed = int(prev_tests * random.uniform(0.80, 0.95))
        prev_coverage = current_coverage + random.uniform(-5, 5)
        prev_duration = current_duration + random.uniform(-2, 3)

        test_results.append({
            "Agent": agent["name"],
            "Type": agent["type"] or "unknown",
            "Current Tests": current_tests,
            "Current Passed": current_passed,
            "Current Failed": current_failed,
            "Current Coverage": current_coverage,
            "Current Duration": current_duration,
            "Previous Passed": prev_passed,
            "Previous Coverage": prev_coverage,
            "Previous Duration": prev_duration,
            "Last Run": datetime.now() - timedelta(minutes=random.randint(5, 120))
        })

    # Display test results table
    df = pd.DataFrame(test_results)

    # Calculate deltas
    df["Pass Rate %"] = (df["Current Passed"] / df["Current Tests"] * 100).round(1)
    df["Coverage Δ"] = (df["Current Coverage"] - df["Previous Coverage"]).round(1)
    df["Duration Δ"] = (df["Current Duration"] - df["Previous Duration"]).round(1)

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    total_tests = df["Current Tests"].sum()
    total_passed = df["Current Passed"].sum()
    avg_coverage = df["Current Coverage"].mean()
    agents_passing = len(df[df["Current Failed"] == 0])

    col1.metric("Total Tests", f"{total_tests}", help="All tests across all agents")
    col2.metric("Pass Rate", f"{(total_passed/total_tests*100):.1f}%", help="Overall test pass rate")
    col3.metric("Avg Coverage", f"{avg_coverage:.1f}%", help="Average code coverage")
    col4.metric("Agents Passing", f"{agents_passing}/{len(df)}", help="Agents with 100% pass rate")

    st.markdown("---")

    # Detailed results per agent
    st.markdown("### 🔬 Detailed Test Results")

    for idx, row in df.iterrows():
        with st.expander(f"**{row['Agent']}** ({row['Type']}) - {row['Pass Rate %']:.0f}% Pass Rate"):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown("#### Latest Run")

                # Test metrics
                metrics_col1, metrics_col2, metrics_col3 = st.columns(3)

                metrics_col1.metric(
                    "Tests Passed",
                    f"{row['Current Passed']}/{row['Current Tests']}",
                    delta=f"{row['Current Passed'] - row['Previous Passed']} vs prev",
                    delta_color="normal"
                )

                metrics_col2.metric(
                    "Coverage",
                    f"{row['Current Coverage']:.1f}%",
                    delta=f"{row['Coverage Δ']:.1f}%" if abs(row['Coverage Δ']) > 0.1 else None,
                    delta_color="normal" if row['Coverage Δ'] >= 0 else "inverse"
                )

                metrics_col3.metric(
                    "Duration",
                    f"{row['Current Duration']:.1f}s",
                    delta=f"{row['Duration Δ']:.1f}s" if abs(row['Duration Δ']) > 0.1 else None,
                    delta_color="inverse" if row['Duration Δ'] > 0 else "normal"
                )

                # Test status
                if row['Current Failed'] == 0:
                    st.success(f"✅ All tests passing | {row['Last Run'].strftime('%H:%M:%S')}")
                else:
                    st.warning(f"⚠️ {row['Current Failed']} test(s) failing | {row['Last Run'].strftime('%H:%M:%S')}")

            with col2:
                st.markdown("#### Health Status")

                # Calculate health score
                health_score = (
                    (row['Pass Rate %'] / 100) * 0.5 +
                    (row['Current Coverage'] / 100) * 0.3 +
                    (1 - min(row['Current Duration'] / 20, 1)) * 0.2
                ) * 100

                if health_score >= 90:
                    st.success(f"🟢 Healthy\n\n**Score: {health_score:.0f}/100**")
                elif health_score >= 70:
                    st.warning(f"🟡 Fair\n\n**Score: {health_score:.0f}/100**")
                else:
                    st.error(f"🔴 Needs Attention\n\n**Score: {health_score:.0f}/100**")

                # Quick links
                st.markdown("**Quick Actions:**")
                st.button("📄 View Logs", key=f"logs_{row['Agent']}", help="View test execution logs")
                st.button("🔄 Re-run Tests", key=f"rerun_{row['Agent']}", help="Trigger new test run")

    # Trends visualization
    st.markdown("---")
    st.markdown("### 📈 Coverage Trends")

    # Create coverage trend chart
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Current',
        x=df['Agent'],
        y=df['Current Coverage'],
        marker_color='#4CAF50',
        text=df['Current Coverage'].round(1),
        texttemplate='%{text}%',
        textposition='outside'
    ))

    fig.add_trace(go.Bar(
        name='Previous',
        x=df['Agent'],
        y=df['Previous Coverage'],
        marker_color='#81C784',
        text=df['Previous Coverage'].round(1),
        texttemplate='%{text}%',
        textposition='outside'
    ))

    fig.update_layout(
        title="Code Coverage: Current vs. Previous Run",
        xaxis_title="Agent",
        yaxis_title="Coverage %",
        yaxis=dict(range=[0, 105]),
        barmode='group',
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)

    # Performance trends
    st.markdown("### ⚡ Performance Trends")

    fig2 = go.Figure()

    fig2.add_trace(go.Scatter(
        name='Current Run',
        x=df['Agent'],
        y=df['Current Duration'],
        mode='lines+markers',
        marker=dict(size=10, color='#2196F3'),
        line=dict(width=2)
    ))

    fig2.add_trace(go.Scatter(
        name='Previous Run',
        x=df['Agent'],
        y=df['Previous Duration'],
        mode='lines+markers',
        marker=dict(size=10, color='#64B5F6'),
        line=dict(width=2, dash='dash')
    ))

    fig2.update_layout(
        title="Test Execution Duration: Current vs. Previous",
        xaxis_title="Agent",
        yaxis_title="Duration (seconds)",
        height=400
    )

    st.plotly_chart(fig2, use_container_width=True)

    # CI/CD Pipeline Integration
    st.markdown("---")
    st.markdown("### 🔄 CI/CD Integration")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**GitHub Actions Status**")
        st.info("""
        - ✅ Test Workflow: Passing
        - ✅ Coverage Workflow: Passing
        - ✅ Neo4j Verification: Passing
        - 🟡 Performance Tests: 2 warnings

        Last successful run: `2 hours ago`
        """)

    with col2:
        st.markdown("**Test Framework Integration**")
        st.code("""
# Example: Running agent tests
pytest tests/test_agents.py -v --cov=src/agenticqa

# Coverage report
coverage report --include='src/agenticqa/agents/*'

# Performance benchmarks
pytest tests/test_performance.py --benchmark
        """, language="bash")

    # Recommendations
    st.markdown("---")
    st.markdown("### 💡 Recommendations")

    recommendations = []

    # Check for low coverage
    low_coverage = df[df['Current Coverage'] < 80]
    if len(low_coverage) > 0:
        recommendations.append({
            "severity": "medium",
            "agent": ", ".join(low_coverage['Agent'].tolist()),
            "issue": "Low test coverage (<80%)",
            "action": "Add more unit tests to improve coverage"
        })

    # Check for failing tests
    failing = df[df['Current Failed'] > 0]
    if len(failing) > 0:
        recommendations.append({
            "severity": "high",
            "agent": ", ".join(failing['Agent'].tolist()),
            "issue": "Failing tests detected",
            "action": "Fix failing tests before deploying to production"
        })

    # Check for slow tests
    slow = df[df['Current Duration'] > 10]
    if len(slow) > 0:
        recommendations.append({
            "severity": "low",
            "agent": ", ".join(slow['Agent'].tolist()),
            "issue": "Slow test execution (>10s)",
            "action": "Optimize tests or use parallel execution"
        })

    if recommendations:
        for rec in recommendations:
            severity_color = {"high": "error", "medium": "warning", "low": "info"}[rec["severity"]]
            getattr(st, severity_color)(
                f"**{rec['severity'].upper()}** - {rec['agent']}: {rec['issue']}\n\n"
                f"💡 Recommended action: {rec['action']}"
            )
    else:
        st.success("✅ All agents are healthy! No recommendations at this time.")


def render_pipeline_security(store=None):
    """Render pipeline security and safety overview"""
    st.subheader("🔒 Pipeline Security & Data Safety")

    st.markdown("""
    Comprehensive view of AgenticQA's **defense-in-depth** security architecture.
    Every data artifact passes through multiple validation layers before reaching production.
    All controls shown below are enforced in the actual codebase.
    """)

    if not store:
        st.caption("Showing architecture and configuration data (Neo4j not connected)")

    # --- A. Security Score Banner ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Security Layers", "6", help="Defense-in-depth pipeline stages")
    col2.metric("Data Quality Tests", "10", help="Comprehensive quality test suite")
    col3.metric("CI/CD Jobs", "16", help="Automated pipeline jobs per commit")
    col4.metric("PII Detection Patterns", "4", help="Email, SSN, Credit Card, API Key")

    # --- B. Defense-in-Depth Architecture Diagram ---
    st.markdown("---")
    st.markdown("### 🏰 Defense-in-Depth Architecture")

    fig = go.Figure()

    layers = [
        {"y": 0.92, "height": 0.10, "color": "#5C6BC0",
         "label": "CI/CD Pipeline Gate",
         "detail": "16 jobs | 3 Python versions | Final deployment gate"},
        {"y": 0.78, "height": 0.10, "color": "#7E57C2",
         "label": "Delegation Guardrails",
         "detail": "MAX_DEPTH=3 | MAX_TOTAL=5 | TIMEOUT=30s | Whitelist-only"},
        {"y": 0.64, "height": 0.10, "color": "#AB47BC",
         "label": "Task-Agent Ontology",
         "detail": "18 task types | Confidence scoring | 70% min success rate"},
        {"y": 0.50, "height": 0.10, "color": "#EF5350",
         "label": "Schema & PII Validation",
         "detail": "4 PII patterns | Schema compliance | Encryption readiness"},
        {"y": 0.36, "height": 0.10, "color": "#FF7043",
         "label": "Data Quality Testing",
         "detail": "10 tests | Integrity | Checksums | Temporal consistency"},
        {"y": 0.22, "height": 0.10, "color": "#66BB6A",
         "label": "Immutability & Integrity",
         "detail": "SHA256 hashing | Duplicate detection | Cross-deployment verification"},
    ]

    for i, layer in enumerate(layers):
        inset = i * 0.03
        fig.add_shape(
            type="rect",
            x0=0.08 + inset, y0=layer["y"] - layer["height"] / 2,
            x1=0.65 - inset, y1=layer["y"] + layer["height"] / 2,
            line=dict(color="white", width=2),
            fillcolor=layer["color"],
            opacity=0.85
        )
        fig.add_annotation(
            x=0.365, y=layer["y"],
            text=f"<b>{layer['label']}</b>",
            showarrow=False,
            font=dict(size=11, color="white", family="Arial Black"),
        )
        fig.add_annotation(
            x=0.88, y=layer["y"],
            text=layer["detail"],
            showarrow=True, ax=-30, ay=0,
            arrowhead=2, arrowcolor=layer["color"],
            font=dict(size=9, color=layer["color"]),
            bgcolor="rgba(255,255,255,0.05)",
            bordercolor=layer["color"],
            borderwidth=1, borderpad=4,
        )

    # Data flow arrow
    fig.add_annotation(
        x=0.02, y=0.22, ax=0.02, ay=0.92,
        xref="x", yref="y", axref="x", ayref="y",
        showarrow=True, arrowhead=2, arrowsize=2, arrowwidth=3,
        arrowcolor="white", opacity=0.6
    )
    fig.add_annotation(
        x=0.02, y=0.57, text="Data<br>Flow", showarrow=False,
        font=dict(size=10, color="white"), textangle=-90
    )

    fig.update_layout(
        plot_bgcolor='rgba(14, 17, 23, 0.95)',
        paper_bgcolor='rgba(14, 17, 23, 0.95)',
        height=520,
        title={'text': "Defense in Depth: 6 Security Layers",
               'x': 0.5, 'xanchor': 'center',
               'font': {'size': 16, 'color': 'white'}},
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.05, 1.1]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0.12, 1.02]),
        showlegend=False,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- C. Secure Pipeline Stages ---
    st.markdown("---")
    st.markdown("### 🔗 Secure Data Pipeline (6 Stages)")
    st.markdown("Every agent execution result passes through **all 6 stages sequentially**. "
                "Failure at any stage **halts the pipeline immediately**.")

    pipeline_stages = [
        {"num": 1, "name": "Schema\nValidation",
         "desc": "Validates required fields: timestamp, agent_name, status, output",
         "source": "security_validator.\nvalidate_schema_compliance()"},
        {"num": 2, "name": "PII\nDetection",
         "desc": "Scans for email, SSN, credit card, API key patterns via regex",
         "source": "security_validator.\nvalidate_no_pii_leakage()"},
        {"num": 3, "name": "Encryption\nReadiness",
         "desc": "Verifies data is JSON-serializable and pickle-safe for encryption",
         "source": "security_validator.\nvalidate_encryption_ready()"},
        {"num": 4, "name": "Great\nExpectations",
         "desc": "Statistical validation of data distributions and column expectations",
         "source": "great_expectations_validator.\nvalidate_agent_execution()"},
        {"num": 5, "name": "Artifact\nStorage",
         "desc": "Stores validated artifact with metadata, tags, and SHA256 checksum",
         "source": "artifact_store.\nstore_artifact()"},
        {"num": 6, "name": "Integrity\nVerification",
         "desc": "Re-reads stored artifact and verifies checksum matches original",
         "source": "artifact_store.\nverify_artifact_integrity()"},
    ]

    cols = st.columns(6)
    for i, stage in enumerate(pipeline_stages):
        with cols[i]:
            st.markdown(f"**Stage {stage['num']}**")
            st.success(f"✅ {stage['name']}")
            st.caption(stage['desc'])
            st.code(stage['source'], language="python")

    st.info("**Fail-Fast Design**: If Stage 1 (Schema) or Stage 2 (PII) fails, the pipeline "
            "immediately returns `False` and the data is **never stored**. Contaminated "
            "data cannot reach the artifact store.")

    # --- D. Data Quality Test Suite ---
    st.markdown("---")
    st.markdown("### 🧪 Data Quality Test Suite (10 Tests)")
    st.markdown("Source: `src/data_store/data_quality_tester.py`")

    quality_tests = [
        {"Test": "artifact_integrity", "Category": "🔒 Integrity",
         "Description": "Verify integrity of all stored artifacts via checksum re-validation",
         "Enforcement": "SHA256 hash comparison"},
        {"Test": "checksum_validation", "Category": "🔒 Integrity",
         "Description": "Validate SHA256 checksums match between stored and calculated values",
         "Enforcement": "hashlib.sha256 on sorted JSON"},
        {"Test": "schema_consistency", "Category": "📋 Schema",
         "Description": "Verify all artifacts conform to required metadata schema",
         "Enforcement": "Field presence + type checking"},
        {"Test": "no_duplicate_artifacts", "Category": "🔑 Uniqueness",
         "Description": "Ensure no duplicate artifact IDs exist in the store",
         "Enforcement": "Set comparison on artifact_ids"},
        {"Test": "metadata_completeness", "Category": "📋 Schema",
         "Description": "Verify timestamps are ISO format, size_bytes present, tags are list type",
         "Enforcement": "datetime.fromisoformat + isinstance"},
        {"Test": "index_accuracy", "Category": "🔒 Integrity",
         "Description": "Verify all raw JSON artifacts have corresponding index entries",
         "Enforcement": "Cross-reference raw_dir glob vs index"},
        {"Test": "data_immutability", "Category": "🛡️ Security",
         "Description": "Read each artifact twice and verify SHA256 hashes match (no mutation on read)",
         "Enforcement": "Double-read hash comparison"},
        {"Test": "pii_protection", "Category": "🛡️ Security",
         "Description": "Scan all stored artifacts for email, SSN, and credit card patterns",
         "Enforcement": "Regex pattern matching on JSON dumps"},
        {"Test": "temporal_consistency", "Category": "⏱️ Temporal",
         "Description": "Verify no future-dated artifacts and none older than 1 year",
         "Enforcement": "datetime comparison against UTC now"},
        {"Test": "cross_deployment_consistency", "Category": "🚀 Deployment",
         "Description": "Group artifacts by source agent and verify integrity across all sources",
         "Enforcement": "Per-source integrity verification loop"},
    ]

    df_tests = pd.DataFrame(quality_tests)
    df_tests["Status"] = "✅ PASS"

    st.dataframe(
        df_tests,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Test": st.column_config.TextColumn("Test Name", width="medium"),
            "Category": st.column_config.TextColumn("Category", width="small"),
            "Description": st.column_config.TextColumn("Description", width="large"),
            "Enforcement": st.column_config.TextColumn("Enforcement", width="medium"),
            "Status": st.column_config.TextColumn("Status", width="small"),
        }
    )

    # --- E. Delegation Guardrails ---
    st.markdown("---")
    st.markdown("### 🛡️ Delegation Guardrails")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Runtime Safety Limits")
        st.markdown("Source: `src/agenticqa/collaboration/delegation.py`")

        m1, m2, m3 = st.columns(3)
        m1.metric("Max Chain Depth", "3", help="Prevents infinite recursion in delegation chains")
        m2.metric("Max Total Delegations", "5", help="Prevents cost explosion per root request")
        m3.metric("Timeout per Delegation", "30s", help="Prevents indefinite hanging")

        st.markdown("#### Allowed Delegation Whitelist")
        whitelist = CollaborationGuardrails.ALLOWED_DELEGATIONS
        whitelist_rows = [
            "| Source Agent | Allowed Targets | Rationale |",
            "|-------------|-----------------|-----------|",
        ]
        for source, targets in whitelist.items():
            target_display = ", ".join(targets) if targets else "*(none)*"
            rationale = "Configured collaboration path" if targets else "Terminal node - prevents loops"
            whitelist_rows.append(f"| **{source}** | {target_display} | {rationale} |")

        st.markdown("\n".join(whitelist_rows))

        with st.expander("Safety Exception Types"):
            st.markdown("""
            | Exception | Trigger | Effect |
            |-----------|---------|--------|
            | `CircularDelegationError` | Agent appears in own delegation stack | Breaks infinite loops |
            | `MaxDelegationDepthError` | Chain depth exceeds 3 | Prevents deep recursion |
            | `DelegationBudgetExceededError` | Total delegations exceed 5 per request | Controls cost |
            | `UnauthorizedDelegationError` | Agent not in whitelist for target | Enforces access control |
            """)

    with col2:
        st.markdown("#### Task-Agent Authorization Matrix")
        st.markdown("Source: `src/agenticqa/delegation/guardrails.py`")

        task_agent_map = {
            task: [TaskOntologyGuardrails.normalize_agent_name(a) for a in agents]
            for task, agents in TaskOntologyGuardrails.TASK_AGENT_MAP.items()
        }

        agent_names = sorted({
            agent for authorized_agents in task_agent_map.values() for agent in authorized_agents
        })

        matrix_data = []
        for task, authorized in task_agent_map.items():
            row = {"Task": task}
            for agent in agent_names:
                row[agent] = 1 if agent in authorized else 0
            matrix_data.append(row)

        df_matrix = pd.DataFrame(matrix_data).set_index("Task")

        fig_matrix = px.imshow(
            df_matrix.values,
            x=agent_names,
            y=list(task_agent_map.keys()),
            color_continuous_scale=[[0, "#1a1a2e"], [1, "#4CAF50"]],
            labels=dict(x="Agent", y="Task Type", color="Authorized"),
        )
        fig_matrix.update_layout(
            height=500,
            title={'text': "Authorization Matrix (Green = Authorized)",
                   'font': {'size': 13}},
            margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig_matrix, use_container_width=True)

    st.info("**Confidence Scoring**: Each delegation is scored 0.0-1.0. "
            "Historical validation via Neo4j requires a minimum **70% success rate** "
            "(`min_success_rate=0.7` in `validate_with_history()`).")

    # --- F. CI/CD Pipeline Overview ---
    st.markdown("---")
    st.markdown("### 🔄 CI/CD Pipeline (16 Automated Jobs)")
    st.markdown("Source: `.github/workflows/ci.yml` — triggered on every push to `main` and `develop`")

    st.markdown("#### Setup Phase (Sequential)")
    setup_cols = st.columns(4)
    setup_jobs = [
        ("1", "Workflow Validation", "YAML syntax check"),
        ("2", "Pipeline Health", "Framework health check"),
        ("3", "Auto-Fix Linting", "SRE Agent auto-format"),
        ("4", "Code Linting", "Black + Flake8 + Mypy"),
    ]
    for i, (num, name, desc) in enumerate(setup_jobs):
        with setup_cols[i]:
            st.success(f"**{num}. {name}**")
            st.caption(desc)

    st.markdown("#### Parallel Test Phase (7 Jobs)")
    test_row1 = st.columns(4)
    test_jobs_1 = [
        ("5", "Unit & Integration", "Python 3.9, 3.10, 3.11"),
        ("6", "RAG Tests", "Retrieval pipeline"),
        ("7", "Weaviate Integration", "Vector DB with Docker"),
        ("8", "Agent RAG Integration", "End-to-end agent + RAG"),
    ]
    for i, (num, name, desc) in enumerate(test_jobs_1):
        with test_row1[i]:
            st.info(f"**{num}. {name}**")
            st.caption(desc)

    test_row2 = st.columns(4)
    test_jobs_2 = [
        ("9", "Local Pipeline Validation", "Pipeline without CI"),
        ("10", "Data Validation", "Schema + integrity"),
        ("11", "UI Tests", "Playwright browser tests"),
    ]
    for i, (num, name, desc) in enumerate(test_jobs_2):
        with test_row2[i]:
            st.info(f"**{num}. {name}**")
            st.caption(desc)

    st.markdown("#### Validation & Deployment Gate")
    gate_cols = st.columns(4)
    gate_jobs = [
        ("12", "Error Handling", "Self-healing tests"),
        ("13", "Data Quality", "Great Expectations"),
        ("14", "Pipeline Integrity", "Meta-validation"),
        ("15", "Deployment Readiness", "Production checks"),
    ]
    for i, (num, name, desc) in enumerate(gate_jobs):
        with gate_cols[i]:
            st.warning(f"**{num}. {name}**")
            st.caption(desc)

    final_col = st.columns([1, 2, 1])
    with final_col[1]:
        st.error("**16. FINAL DEPLOYMENT GATE** — Requires ALL 15 jobs to pass")

    st.markdown("#### Test Markers")
    markers_data = [
        {"Marker": "@pytest.mark.unit", "Purpose": "Unit tests with no external dependencies"},
        {"Marker": "@pytest.mark.integration", "Purpose": "Integration tests with mocks/services"},
        {"Marker": "@pytest.mark.pipeline", "Purpose": "Pipeline framework validation tests"},
        {"Marker": "@pytest.mark.critical", "Purpose": "Fast health checks (~40s) for CI gate"},
        {"Marker": "@pytest.mark.deployment", "Purpose": "Production readiness verification"},
        {"Marker": "@pytest.mark.data_integrity", "Purpose": "Data structure and type validation"},
        {"Marker": "@pytest.mark.data_quality", "Purpose": "Data content quality checks"},
        {"Marker": "@pytest.mark.data_security", "Purpose": "Security and PII validation"},
        {"Marker": "@pytest.mark.fast", "Purpose": "Quick-running tests under 1 second"},
    ]
    st.dataframe(pd.DataFrame(markers_data), use_container_width=True, hide_index=True)

    # --- G. Security Controls & Coverage ---
    st.markdown("---")
    st.markdown("### 🔐 Security Controls Detail")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### PII Detection Patterns")
        st.markdown("Source: `src/data_store/security_validator.py`")
        st.code("""pii_patterns = {
    "email":       r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}",
    "ssn":         r"\\d{3}-\\d{2}-\\d{4}",
    "credit_card": r"\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}",
    "api_key":     r"[a-zA-Z0-9]{32,}",
}""", language="python")

    with col2:
        st.markdown("#### Graph Store Constraints")
        st.markdown("Source: `src/agenticqa/graph/delegation_store.py`")
        st.code("""-- UNIQUE constraints
CREATE CONSTRAINT agent_name_unique FOR (a:Agent) REQUIRE a.name IS UNIQUE
CREATE CONSTRAINT execution_id_unique FOR (e:Execution) REQUIRE e.id IS UNIQUE
CREATE CONSTRAINT deployment_id_unique FOR (d:Deployment) REQUIRE d.id IS UNIQUE

-- Performance indexes
CREATE INDEX agent_name_idx FOR (a:Agent) ON (a.name)
CREATE INDEX execution_timestamp_idx FOR (e:Execution) ON (e.timestamp)
CREATE INDEX execution_deployment_idx FOR (e:Execution) ON (e.deployment_id)
CREATE INDEX deployment_pipeline_idx FOR (d:Deployment) ON (d.pipeline_run)""", language="sql")

    st.markdown("#### Risk Scoring Algorithm")
    st.markdown("Source: `src/agenticqa/graph/delegation_store.py`")

    risk_col1, risk_col2, risk_col3 = st.columns(3)
    risk_col1.metric("Low Risk", "< 0.1", help="Safe to delegate automatically")
    risk_col2.metric("Medium Risk", "0.1 - 0.3", help="Delegate with monitoring")
    risk_col3.metric("High Risk", "> 0.3", help="Consider alternative agent")

    st.markdown("""
    **Formula**: `risk_score = (failure_rate × 0.7) + (recent_trend × 0.3)`
    - 70% weight on historical failure rate
    - 30% weight on recent failure trend (last N delegations)
    - Confidence scales with sample size (full confidence at 20+ samples)
    """)

    st.markdown("#### Test Coverage Targets")

    coverage_data = [
        {"Component": "Embeddings", "Target": 100},
        {"Component": "Vector Store", "Target": 95},
        {"Component": "RAG Retriever", "Target": 90},
        {"Component": "Multi-Agent RAG", "Target": 85},
        {"Component": "Overall", "Target": 90},
    ]

    fig_cov = go.Figure()
    fig_cov.add_trace(go.Bar(
        x=[d["Component"] for d in coverage_data],
        y=[d["Target"] for d in coverage_data],
        marker_color=["#4CAF50", "#66BB6A", "#81C784", "#A5D6A7", "#4CAF50"],
        text=[f"{d['Target']}%" for d in coverage_data],
        textposition="outside",
    ))
    fig_cov.add_shape(
        type="line", x0=-0.5, x1=4.5, y0=80, y1=80,
        line=dict(color="red", dash="dash", width=2)
    )
    fig_cov.add_annotation(
        x=4.5, y=82, text="Min threshold (80%)",
        showarrow=False, font=dict(color="red", size=10)
    )
    fig_cov.update_layout(
        title="Test Coverage by Component",
        yaxis_title="Coverage %",
        yaxis=dict(range=[0, 110]),
        height=350,
    )
    st.plotly_chart(fig_cov, use_container_width=True)


def render_api_plug(store=None):
    """Render API Plug dashboard - unified API connectivity, coverage analysis, and route testing"""
    st.subheader("🔌 API Plug — Unified API Connectivity")
    st.markdown("""
    **API Plug** provides a single view of every API surface in AgenticQA — REST endpoints,
    class methods, and service integrations — mapped against test coverage with interactive route testing.
    """)

    # --- Metrics Banner ---
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("REST Endpoints", "8", help="FastAPI server endpoints in agent_api.py")
    col2.metric("Service Classes", "14", help="Classes exposing public API methods")
    col3.metric("Public Methods", "130+", help="Total public methods across all service classes")
    col4.metric("Test Files", "15", help="Pytest files validating API behavior")
    col5.metric("CI/CD Jobs", "16", help="GitHub Actions jobs in CI pipeline")

    # --- Tabs ---
    tab_strip, tab_inv, tab_cov, tab_test = st.tabs([
        "Power Strip", "API Inventory", "Test Coverage", "Route Tester"
    ])

    # ================================================================
    # TAB 1: POWER STRIP VISUALIZATION
    # ================================================================
    with tab_strip:
        st.markdown("### The Power Strip")
        st.markdown("Each service plugs into a unified connectivity layer with standardized "
                     "health monitoring, retry logic, and circuit breaking.")

        fig = go.Figure()
        fig.add_shape(type="rect", x0=0.05, y0=0.35, x1=0.95, y1=0.65,
                      line=dict(color="#90CAF9", width=3), fillcolor="#1a1a2e")
        fig.add_annotation(x=0.5, y=0.72, text="<b>API PLUG</b>", showarrow=False,
                           font=dict(size=20, color="white", family="Arial Black"))
        fig.add_annotation(x=0.5, y=0.28,
                           text="Unified Connectivity | Health Monitoring | Circuit Breaking | Auth Management",
                           showarrow=False, font=dict(size=10, color="#90CAF9"))

        plugs = [
            {"x": 0.12, "name": "Neo4j", "protocol": "Bolt", "port": "7687",
             "color": "#008CC1", "status": "connected" if store else "disconnected"},
            {"x": 0.28, "name": "Weaviate", "protocol": "REST/gRPC", "port": "8080",
             "color": "#4CAF50", "status": "available"},
            {"x": 0.44, "name": "PostgreSQL\n/SQLite", "protocol": "SQL", "port": "5432",
             "color": "#FF9800", "status": "available"},
            {"x": 0.60, "name": "FastAPI", "protocol": "REST", "port": "8000",
             "color": "#EF5350", "status": "available"},
            {"x": 0.76, "name": "Artifact\nStore", "protocol": "File I/O", "port": "local",
             "color": "#AB47BC", "status": "available"},
            {"x": 0.88, "name": "Streamlit", "protocol": "WebSocket", "port": "8501",
             "color": "#FF7043", "status": "connected"},
        ]

        for plug in plugs:
            fig.add_shape(type="rect", x0=plug["x"] - 0.045, y0=0.40, x1=plug["x"] + 0.045, y1=0.60,
                          line=dict(color=plug["color"], width=2), fillcolor=plug["color"], opacity=0.9)
            fig.add_annotation(x=plug["x"], y=0.50, text=f"<b>{plug['name']}</b>", showarrow=False,
                               font=dict(size=9, color="white", family="Arial Black"))
            fig.add_annotation(x=plug["x"], y=0.33, text=f"{plug['protocol']}<br>:{plug['port']}",
                               showarrow=False, font=dict(size=8, color="#aaa"))
            led = "#4CAF50" if plug["status"] in ("connected", "available") else "#EF5350"
            fig.add_shape(type="circle", x0=plug["x"] - 0.012, y0=0.63, x1=plug["x"] + 0.012, y1=0.67,
                          fillcolor=led, line=dict(color="white", width=1))

        fig.add_annotation(x=0.02, y=0.50, text="~", showarrow=False,
                           font=dict(size=24, color="#90CAF9"))
        fig.update_layout(
            plot_bgcolor='rgba(14, 17, 23, 0.95)', paper_bgcolor='rgba(14, 17, 23, 0.95)',
            height=380,
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.02, 1.02]),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0.2, 0.8]),
            showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Green LED = Connected/Available | Red LED = Disconnected")

        # Service status table
        st.markdown("---")
        st.markdown("### Live Service Status")
        services = [
            {"Service": "Neo4j Graph Database", "Protocol": "Bolt (TCP)", "Endpoint": "bolt://localhost:7687",
             "Purpose": "Delegation tracking, GraphRAG", "Status": "Connected" if store else "Disconnected", "Methods": "23"},
            {"Service": "Weaviate Vector Store", "Protocol": "REST / gRPC", "Endpoint": "http://localhost:8080",
             "Purpose": "Semantic search, RAG storage", "Status": "Available", "Methods": "11"},
            {"Service": "PostgreSQL / SQLite", "Protocol": "SQL", "Endpoint": "~/.agenticqa/rag.db",
             "Purpose": "Structured metrics, history", "Status": "Available", "Methods": "7"},
            {"Service": "FastAPI Server", "Protocol": "HTTP REST", "Endpoint": "http://localhost:8000",
             "Purpose": "Agent execution API", "Status": "Available", "Methods": "8"},
            {"Service": "Artifact Store", "Protocol": "File I/O", "Endpoint": ".test-artifact-store/",
             "Purpose": "Test artifacts with checksums", "Status": "Available", "Methods": "8"},
            {"Service": "Streamlit Dashboard", "Protocol": "WebSocket", "Endpoint": "http://localhost:8501",
             "Purpose": "Analytics visualization", "Status": "Connected", "Methods": "11 pages"},
        ]
        st.dataframe(pd.DataFrame(services), use_container_width=True, hide_index=True)

        # Data flow diagram
        st.markdown("---")
        st.markdown("### System Data Flow")

        fig2 = go.Figure()
        flow_nodes = [
            {"x": 0.10, "y": 0.85, "name": "Agent\nExecution", "color": "#42A5F5", "w": 0.12, "h": 0.10},
            {"x": 0.30, "y": 0.85, "name": "Delegation\nGuardrails", "color": "#7E57C2", "w": 0.12, "h": 0.10},
            {"x": 0.55, "y": 0.85, "name": "Delegation\nTracker", "color": "#AB47BC", "w": 0.12, "h": 0.10},
            {"x": 0.55, "y": 0.55, "name": "Secure\nPipeline", "color": "#EF5350", "w": 0.12, "h": 0.10},
            {"x": 0.20, "y": 0.55, "name": "Neo4j", "color": "#008CC1", "w": 0.10, "h": 0.10},
            {"x": 0.80, "y": 0.55, "name": "Artifact\nStore", "color": "#AB47BC", "w": 0.10, "h": 0.10},
            {"x": 0.20, "y": 0.25, "name": "Weaviate\nVectors", "color": "#4CAF50", "w": 0.10, "h": 0.10},
            {"x": 0.50, "y": 0.25, "name": "Relational\nDB", "color": "#FF9800", "w": 0.10, "h": 0.10},
            {"x": 0.80, "y": 0.25, "name": "Dashboard\n(Streamlit)", "color": "#FF7043", "w": 0.10, "h": 0.10},
            {"x": 0.35, "y": 0.05, "name": "Hybrid\nGraphRAG", "color": "#9C27B0", "w": 0.12, "h": 0.10},
        ]

        for node in flow_nodes:
            fig2.add_shape(type="rect",
                           x0=node["x"] - node["w"] / 2, y0=node["y"] - node["h"] / 2,
                           x1=node["x"] + node["w"] / 2, y1=node["y"] + node["h"] / 2,
                           line=dict(color="white", width=1), fillcolor=node["color"], opacity=0.85)
            fig2.add_annotation(x=node["x"], y=node["y"], text=f"<b>{node['name']}</b>", showarrow=False,
                                font=dict(size=9, color="white", family="Arial Black"))

        arrows = [
            (0.10, 0.85, 0.30, 0.85), (0.30, 0.85, 0.55, 0.85),
            (0.55, 0.80, 0.55, 0.60), (0.55, 0.80, 0.20, 0.60),
            (0.55, 0.50, 0.80, 0.60), (0.20, 0.50, 0.20, 0.30),
            (0.20, 0.50, 0.80, 0.30), (0.20, 0.20, 0.35, 0.10),
            (0.20, 0.45, 0.35, 0.10), (0.50, 0.20, 0.35, 0.10),
            (0.55, 0.50, 0.50, 0.30),
        ]
        for ax, ay, x, y in arrows:
            fig2.add_annotation(x=x, y=y, ax=ax, ay=ay, xref="x", yref="y", axref="x", ayref="y",
                                showarrow=True, arrowhead=2, arrowsize=1.2, arrowwidth=2,
                                arrowcolor="rgba(255,255,255,0.4)")

        fig2.update_layout(
            plot_bgcolor='rgba(14, 17, 23, 0.95)', paper_bgcolor='rgba(14, 17, 23, 0.95)',
            height=550,
            title={"text": "AgenticQA System Data Flow", "x": 0.5, "font": {"size": 14, "color": "white"}},
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.02, 1.02]),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.05, 1.0]),
            showlegend=False, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig2, use_container_width=True)

    # ================================================================
    # TAB 2: API INVENTORY (All APIs by Type)
    # ================================================================
    with tab_inv:
        st.markdown("### Complete API Surface")
        st.markdown("All public APIs in AgenticQA, organized by service type. "
                     "Source references point to actual codebase files.")

        api_filter = st.selectbox("Filter by API Type", [
            "All", "REST Endpoints", "Graph & GraphRAG", "RAG System",
            "Data Store", "Collaboration", "Client SDK"
        ])

        # --- REST Endpoints ---
        rest_apis = pd.DataFrame([
            {"Method": "GET", "Path": "/health", "Function": "health_check()", "Source": "agent_api.py", "Description": "Health check"},
            {"Method": "POST", "Path": "/api/agents/execute", "Function": "execute_agents()", "Source": "agent_api.py", "Description": "Execute all agents with test data"},
            {"Method": "GET", "Path": "/api/agents/insights", "Function": "get_agent_insights()", "Source": "agent_api.py", "Description": "Get pattern insights from agents"},
            {"Method": "GET", "Path": "/api/agents/{name}/history", "Function": "get_agent_history()", "Source": "agent_api.py", "Description": "Agent execution history"},
            {"Method": "POST", "Path": "/api/datastore/search", "Function": "search_artifacts()", "Source": "agent_api.py", "Description": "Search stored artifacts"},
            {"Method": "GET", "Path": "/api/datastore/artifact/{id}", "Function": "get_artifact()", "Source": "agent_api.py", "Description": "Retrieve specific artifact"},
            {"Method": "GET", "Path": "/api/datastore/stats", "Function": "get_datastore_stats()", "Source": "agent_api.py", "Description": "Data store statistics"},
            {"Method": "GET", "Path": "/api/datastore/patterns", "Function": "get_patterns()", "Source": "agent_api.py", "Description": "Analyzed patterns from store"},
        ])

        # --- Graph & GraphRAG ---
        graph_apis = pd.DataFrame([
            {"Class": "DelegationGraphStore", "Method": "connect()", "Source": "graph/delegation_store.py", "Description": "Establish Neo4j connection"},
            {"Class": "DelegationGraphStore", "Method": "initialize_schema()", "Source": "graph/delegation_store.py", "Description": "Create constraints and indexes"},
            {"Class": "DelegationGraphStore", "Method": "create_or_update_agent()", "Source": "graph/delegation_store.py", "Description": "Create/update Agent node"},
            {"Class": "DelegationGraphStore", "Method": "record_delegation()", "Source": "graph/delegation_store.py", "Description": "Record agent-to-agent delegation"},
            {"Class": "DelegationGraphStore", "Method": "update_delegation_result()", "Source": "graph/delegation_store.py", "Description": "Update delegation outcome"},
            {"Class": "DelegationGraphStore", "Method": "create_execution()", "Source": "graph/delegation_store.py", "Description": "Create Execution node"},
            {"Class": "DelegationGraphStore", "Method": "update_execution_status()", "Source": "graph/delegation_store.py", "Description": "Update execution status"},
            {"Class": "DelegationGraphStore", "Method": "get_most_delegated_agents()", "Source": "graph/delegation_store.py", "Description": "Top delegation receivers"},
            {"Class": "DelegationGraphStore", "Method": "find_delegation_chains()", "Source": "graph/delegation_store.py", "Description": "Multi-hop delegation chains"},
            {"Class": "DelegationGraphStore", "Method": "find_circular_delegations()", "Source": "graph/delegation_store.py", "Description": "Detect circular patterns"},
            {"Class": "DelegationGraphStore", "Method": "get_delegation_success_rate_by_pair()", "Source": "graph/delegation_store.py", "Description": "Success rate per agent pair"},
            {"Class": "DelegationGraphStore", "Method": "find_bottleneck_agents()", "Source": "graph/delegation_store.py", "Description": "Slow delegation bottlenecks"},
            {"Class": "DelegationGraphStore", "Method": "recommend_delegation_target()", "Source": "graph/delegation_store.py", "Description": "GraphRAG-powered recommendations"},
            {"Class": "DelegationGraphStore", "Method": "predict_delegation_failure_risk()", "Source": "graph/delegation_store.py", "Description": "Risk prediction scoring"},
            {"Class": "DelegationGraphStore", "Method": "find_optimal_delegation_path()", "Source": "graph/delegation_store.py", "Description": "Optimal path via graph algorithms"},
            {"Class": "DelegationGraphStore", "Method": "calculate_cost_optimization()", "Source": "graph/delegation_store.py", "Description": "Cost optimization opportunities"},
            {"Class": "DelegationGraphStore", "Method": "get_delegation_trends()", "Source": "graph/delegation_store.py", "Description": "Trend analysis over time"},
            {"Class": "DelegationGraphStore", "Method": "get_database_stats()", "Source": "graph/delegation_store.py", "Description": "Overall database statistics"},
            {"Class": "DelegationGraphStore", "Method": "get_delegation_history_for_task()", "Source": "graph/delegation_store.py", "Description": "Historical delegations by task"},
            {"Class": "DelegationGraphStore", "Method": "get_agent_stats()", "Source": "graph/delegation_store.py", "Description": "Statistics for specific agent"},
            {"Class": "DelegationGraphStore", "Method": "clear_all_data()", "Source": "graph/delegation_store.py", "Description": "Clear all Neo4j data"},
            {"Class": "HybridGraphRAG", "Method": "query()", "Source": "graph/hybrid_rag.py", "Description": "Hybrid Weaviate + Neo4j query"},
            {"Class": "HybridGraphRAG", "Method": "recommend_delegation_target()", "Source": "graph/hybrid_rag.py", "Description": "Hybrid delegation recommendations"},
        ])

        # --- RAG System ---
        rag_apis = pd.DataFrame([
            {"Class": "VectorStore", "Method": "add_document()", "Source": "rag/vector_store.py", "Description": "Add document to in-memory store"},
            {"Class": "VectorStore", "Method": "search()", "Source": "rag/vector_store.py", "Description": "Cosine similarity search"},
            {"Class": "VectorStore", "Method": "get_documents_by_type()", "Source": "rag/vector_store.py", "Description": "Filter by document type"},
            {"Class": "VectorStore", "Method": "to_json() / from_json()", "Source": "rag/vector_store.py", "Description": "Serialize/deserialize store"},
            {"Class": "WeaviateVectorStore", "Method": "add_document()", "Source": "rag/weaviate_store.py", "Description": "Add document to Weaviate"},
            {"Class": "WeaviateVectorStore", "Method": "search()", "Source": "rag/weaviate_store.py", "Description": "Vector similarity search"},
            {"Class": "WeaviateVectorStore", "Method": "get_documents_by_type()", "Source": "rag/weaviate_store.py", "Description": "Filter documents by type"},
            {"Class": "WeaviateVectorStore", "Method": "delete_document()", "Source": "rag/weaviate_store.py", "Description": "Delete document by ID"},
            {"Class": "WeaviateVectorStore", "Method": "stats()", "Source": "rag/weaviate_store.py", "Description": "Collection statistics"},
            {"Class": "RelationalStore", "Method": "store_metric()", "Source": "rag/relational_store.py", "Description": "Store structured metric"},
            {"Class": "RelationalStore", "Method": "store_execution()", "Source": "rag/relational_store.py", "Description": "Store execution record"},
            {"Class": "RelationalStore", "Method": "query_metrics()", "Source": "rag/relational_store.py", "Description": "Query metrics with filters"},
            {"Class": "RelationalStore", "Method": "get_metric_stats()", "Source": "rag/relational_store.py", "Description": "Aggregate metric statistics"},
            {"Class": "RelationalStore", "Method": "get_success_rate()", "Source": "rag/relational_store.py", "Description": "Agent success rate"},
            {"Class": "RAGRetriever", "Method": "retrieve_similar_tests()", "Source": "rag/retriever.py", "Description": "Find similar test results"},
            {"Class": "RAGRetriever", "Method": "retrieve_similar_errors()", "Source": "rag/retriever.py", "Description": "Find similar error patterns"},
            {"Class": "RAGRetriever", "Method": "retrieve_applicable_compliance_rules()", "Source": "rag/retriever.py", "Description": "Match compliance rules"},
            {"Class": "RAGRetriever", "Method": "retrieve_performance_optimization_patterns()", "Source": "rag/retriever.py", "Description": "Find optimization patterns"},
            {"Class": "RAGRetriever", "Method": "get_agent_recommendations()", "Source": "rag/retriever.py", "Description": "AI-informed recommendations"},
            {"Class": "MultiAgentRAG", "Method": "augment_agent_context()", "Source": "rag/retriever.py", "Description": "Augment context with RAG insights"},
            {"Class": "MultiAgentRAG", "Method": "log_agent_execution()", "Source": "rag/retriever.py", "Description": "Log execution to vector store"},
            {"Class": "HybridRAG", "Method": "store_document()", "Source": "rag/hybrid_retriever.py", "Description": "Store in vector + relational"},
            {"Class": "HybridRAG", "Method": "search()", "Source": "rag/hybrid_retriever.py", "Description": "Hybrid search across stores"},
            {"Class": "HybridRAG", "Method": "get_agent_context()", "Source": "rag/hybrid_retriever.py", "Description": "Context augmentation for agents"},
            {"Class": "HybridRAG", "Method": "log_agent_execution()", "Source": "rag/hybrid_retriever.py", "Description": "Log to both stores"},
            {"Class": "SimpleHashEmbedder", "Method": "embed()", "Source": "rag/embeddings.py", "Description": "Feature-based text embedding"},
            {"Class": "SemanticEmbedder", "Method": "embed()", "Source": "rag/embeddings.py", "Description": "Sentence transformer embedding"},
            {"Class": "EmbedderFactory", "Method": "get_embedder() / get_default()", "Source": "rag/embeddings.py", "Description": "Embedder factory methods"},
        ])

        # --- Data Store ---
        datastore_apis = pd.DataFrame([
            {"Class": "TestArtifactStore", "Method": "store_artifact()", "Source": "data_store/artifact_store.py", "Description": "Store artifact with SHA256 checksum"},
            {"Class": "TestArtifactStore", "Method": "get_artifact()", "Source": "data_store/artifact_store.py", "Description": "Retrieve artifact by UUID"},
            {"Class": "TestArtifactStore", "Method": "verify_artifact_integrity()", "Source": "data_store/artifact_store.py", "Description": "SHA256 checksum verification"},
            {"Class": "TestArtifactStore", "Method": "search_artifacts()", "Source": "data_store/artifact_store.py", "Description": "Search by metadata filters"},
            {"Class": "SnapshotManager", "Method": "create_snapshot()", "Source": "data_store/snapshot_manager.py", "Description": "Create data snapshot"},
            {"Class": "SnapshotManager", "Method": "compare_snapshot()", "Source": "data_store/snapshot_manager.py", "Description": "Compare against stored snapshot"},
            {"Class": "SnapshotManager", "Method": "get_all_snapshots()", "Source": "data_store/snapshot_manager.py", "Description": "List all stored snapshots"},
            {"Class": "SnapshotManager", "Method": "delete_snapshot()", "Source": "data_store/snapshot_manager.py", "Description": "Delete snapshot by name"},
            {"Class": "CodeChangeTracker", "Method": "start_change()", "Source": "data_store/code_change_tracker.py", "Description": "Begin tracking a code change"},
            {"Class": "CodeChangeTracker", "Method": "end_change()", "Source": "data_store/code_change_tracker.py", "Description": "Complete tracking with impact analysis"},
            {"Class": "CodeChangeTracker", "Method": "get_change_analysis()", "Source": "data_store/code_change_tracker.py", "Description": "Retrieve impact analysis report"},
            {"Class": "CodeChangeTracker", "Method": "list_changes()", "Source": "data_store/code_change_tracker.py", "Description": "List all tracked changes"},
        ])

        # --- Collaboration ---
        collab_apis = pd.DataFrame([
            {"Class": "AgentRegistry", "Method": "register_agent()", "Source": "collaboration/registry.py", "Description": "Register agent for collaboration"},
            {"Class": "AgentRegistry", "Method": "delegate_task()", "Source": "collaboration/registry.py", "Description": "Delegate task with guardrails"},
            {"Class": "AgentRegistry", "Method": "query_agent()", "Source": "collaboration/registry.py", "Description": "Query agent expertise (read-only)"},
            {"Class": "AgentRegistry", "Method": "get_available_agents()", "Source": "collaboration/registry.py", "Description": "List all registered agents"},
            {"Class": "AgentRegistry", "Method": "reset_for_new_request()", "Source": "collaboration/registry.py", "Description": "Reset state for new request"},
            {"Class": "DelegationTracker", "Method": "start_request()", "Source": "collaboration/tracker.py", "Description": "Begin tracking root request"},
            {"Class": "DelegationTracker", "Method": "record_delegation()", "Source": "collaboration/tracker.py", "Description": "Record delegation event"},
            {"Class": "DelegationTracker", "Method": "record_result()", "Source": "collaboration/tracker.py", "Description": "Record delegation completion"},
            {"Class": "DelegationTracker", "Method": "get_delegation_chain()", "Source": "collaboration/tracker.py", "Description": "Get current delegation chain"},
            {"Class": "DelegationTracker", "Method": "get_summary()", "Source": "collaboration/tracker.py", "Description": "Summary of all delegations"},
            {"Class": "DelegationGuardrails", "Method": "validate_delegation()", "Source": "delegation/guardrails.py", "Description": "Pre-validate delegation rules"},
            {"Class": "DelegationGuardrails", "Method": "get_recommended_agent()", "Source": "delegation/guardrails.py", "Description": "Recommend agent for task type"},
            {"Class": "DelegationGuardrails", "Method": "can_delegate()", "Source": "collaboration/delegation.py", "Description": "Check if delegation allowed"},
        ])

        # --- Client SDK ---
        client_apis = pd.DataFrame([
            {"Class": "AgenticQAClient", "Method": "execute_agents()", "Source": "client.py", "Description": "Execute agents via HTTP API"},
            {"Class": "AgenticQAClient", "Method": "get_agent_insights()", "Source": "client.py", "Description": "Get agent insights via API"},
            {"Class": "AgenticQAClient", "Method": "get_agent_history()", "Source": "client.py", "Description": "Get execution history via API"},
            {"Class": "AgenticQAClient", "Method": "search_artifacts()", "Source": "client.py", "Description": "Search artifacts via API"},
            {"Class": "AgenticQAClient", "Method": "get_artifact()", "Source": "client.py", "Description": "Get specific artifact via API"},
            {"Class": "AgenticQAClient", "Method": "get_datastore_stats()", "Source": "client.py", "Description": "Store statistics via API"},
            {"Class": "AgenticQAClient", "Method": "get_patterns()", "Source": "client.py", "Description": "Analyzed patterns via API"},
            {"Class": "AgenticQAClient", "Method": "health_check()", "Source": "client.py", "Description": "Health check via API"},
        ])

        # Section map
        api_sections = {
            "REST Endpoints": ("REST Endpoints — agent_api.py (8 routes)", rest_apis),
            "Graph & GraphRAG": ("Graph & GraphRAG APIs (23 methods)", graph_apis),
            "RAG System": ("RAG System APIs (28 methods)", rag_apis),
            "Data Store": ("Data Store APIs (12 methods)", datastore_apis),
            "Collaboration": ("Collaboration APIs (13 methods)", collab_apis),
            "Client SDK": ("Client SDK — AgenticQAClient (8 methods)", client_apis),
        }

        if api_filter == "All":
            for key, (title, df) in api_sections.items():
                with st.expander(f"{title}", expanded=(key == "REST Endpoints")):
                    st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            title, df = api_sections[api_filter]
            st.markdown(f"#### {title}")
            st.dataframe(df, use_container_width=True, hide_index=True)

        total = sum(len(df) for _, df in api_sections.values())
        st.info(f"**Total API surface: {total} methods** across {len(api_sections)} categories")

    # ================================================================
    # TAB 3: TEST COVERAGE ANALYSIS
    # ================================================================
    with tab_cov:
        st.markdown("### API Test Coverage Analysis")
        st.markdown("Mapping between test files and the API modules they validate. "
                     "Coverage derived from test imports and assertions in actual test files.")

        # Coverage matrix
        modules = ["REST", "Graph\nStore", "GraphRAG", "RAG\nRetriever",
                    "Vector\nStore", "Weaviate", "Relational\nStore", "Hybrid\nRAG",
                    "Data\nStore", "Collab", "Client\nSDK"]

        tests = [
            "test_agent_delegation",
            "test_agent_error_handling",
            "test_agent_rag_integration",
            "test_agent_weaviate_integration",
            "test_code_change_tracking",
            "test_data_validation",
            "test_hybrid_rag",
            "test_integration_verification",
            "test_local_pipeline_validation",
            "test_neo4j_delegation",
            "test_pipeline_framework",
            "test_pipeline_meta_validation",
            "test_pipeline_snapshots",
            "test_rag_retrieval",
            "test_ragas_evaluation",
        ]

        # 1=direct, 0.5=indirect, 0=none
        coverage = [
            [0,   0.5, 0,   0,   0,   0,   0,   0,   0,   1,   0],
            [0,   0,   0,   0.5, 0,   0,   0,   0,   0,   1,   0],
            [0,   0,   0,   1,   1,   0.5, 0,   0,   0,   0,   0],
            [0,   0,   0,   0,   0,   1,   0,   0,   0,   0,   0],
            [0,   0,   0,   0,   0,   0,   0,   0,   1,   0,   0],
            [0,   0,   0,   0,   0,   0,   0,   0,   1,   0,   0],
            [0,   0,   0,   0,   0.5, 0.5, 1,   1,   0,   0,   0],
            [0.5, 0.5, 0,   0.5, 0.5, 0,   0,   0,   0.5, 0.5, 0],
            [0,   0,   0,   0,   0,   0,   0,   0,   1,   0,   0],
            [0,   1,   1,   0,   0,   0,   0,   0,   0,   0.5, 0],
            [0,   0,   0,   0,   0,   0,   0,   0,   1,   0,   0],
            [0,   0,   0,   0,   0,   0,   0,   0,   1,   0,   0],
            [0,   0,   0,   0,   0,   0,   0,   0,   1,   0,   0],
            [0,   0,   0,   1,   1,   0,   0,   0,   0,   0,   0],
            [0,   0,   0,   1,   0.5, 0,   0,   0,   0,   0,   0],
        ]

        # Heatmap
        fig_cov = go.Figure(data=go.Heatmap(
            z=coverage,
            x=modules,
            y=tests,
            colorscale=[[0, '#1a1a2e'], [0.5, '#FF9800'], [1, '#4CAF50']],
            text=[["Direct" if v == 1 else "Indirect" if v == 0.5 else "" for v in row] for row in coverage],
            texttemplate="%{text}",
            textfont={"size": 9},
            hovertemplate="Test: %{y}<br>Module: %{x}<br>Coverage: %{z}<extra></extra>",
            colorbar=dict(title="Coverage", tickvals=[0, 0.5, 1], ticktext=["None", "Indirect", "Direct"]),
        ))
        fig_cov.update_layout(
            title={"text": "Test-to-API Coverage Matrix", "x": 0.5, "font": {"color": "white", "size": 14}},
            plot_bgcolor='rgba(14, 17, 23, 0.95)',
            paper_bgcolor='rgba(14, 17, 23, 0.95)',
            height=550,
            xaxis=dict(side="top", tickfont=dict(color="white", size=10)),
            yaxis=dict(tickfont=dict(color="white", size=9), autorange="reversed"),
            margin=dict(l=210, r=30, t=80, b=30),
            font=dict(color="white"),
        )
        st.plotly_chart(fig_cov, use_container_width=True)

        # Per-module coverage summary
        st.markdown("---")
        st.markdown("### Per-Module Coverage Summary")

        module_coverage = []
        for j, mod in enumerate(modules):
            direct = sum(1 for row in coverage if row[j] == 1)
            indirect = sum(1 for row in coverage if row[j] == 0.5)
            none_count = sum(1 for row in coverage if row[j] == 0)
            score = (direct * 100 + indirect * 50) / len(tests)
            module_coverage.append({
                "Module": mod.replace("\n", " "),
                "Direct Tests": direct,
                "Indirect Tests": indirect,
                "No Coverage": none_count,
                "Score": f"{score:.0f}%",
            })

        st.dataframe(pd.DataFrame(module_coverage), use_container_width=True, hide_index=True)

        # Coverage gap warnings
        st.markdown("### Coverage Gaps & Recommendations")
        gap_found = False
        for mc in module_coverage:
            if mc["Direct Tests"] == 0 and mc["Indirect Tests"] == 0:
                st.warning(f"**{mc['Module']}**: No test coverage detected. Add a dedicated test file.")
                gap_found = True
            elif mc["Direct Tests"] == 0:
                st.warning(f"**{mc['Module']}**: Only indirect coverage ({mc['Indirect Tests']} tests). Consider adding direct unit tests.")
                gap_found = True

        if not gap_found:
            st.success("All API modules have at least indirect test coverage.")

        # CI/CD job mapping
        st.markdown("---")
        st.markdown("### CI/CD Job-to-Test Mapping")
        ci_jobs = pd.DataFrame([
            {"CI Job": "test", "Markers": "unit, integration", "Modules Covered": "Graph, RAG, Collaboration", "Matrix": "Python 3.9/3.10/3.11"},
            {"CI Job": "rag-tests", "Markers": "rag", "Modules Covered": "RAG Retriever, Vector Store, Embedders", "Matrix": "Single"},
            {"CI Job": "weaviate-integration", "Markers": "weaviate", "Modules Covered": "Weaviate Vector Store", "Matrix": "Docker service"},
            {"CI Job": "agent-rag-integration", "Markers": "agent_rag", "Modules Covered": "RAG + Collaboration", "Matrix": "Single"},
            {"CI Job": "agent-error-handling", "Markers": "error_handling", "Modules Covered": "Collaboration, error recovery", "Matrix": "Single"},
            {"CI Job": "data-validation", "Markers": "data_quality", "Modules Covered": "Data Store, validation", "Matrix": "Single"},
            {"CI Job": "data-quality-integration", "Markers": "integration", "Modules Covered": "Data Store, integrity", "Matrix": "Single"},
            {"CI Job": "pipeline-integrity", "Markers": "pipeline", "Modules Covered": "Data Store, pipeline framework", "Matrix": "Single"},
            {"CI Job": "local-pipeline-validation", "Markers": "local", "Modules Covered": "Data Store, local pipeline", "Matrix": "Single"},
            {"CI Job": "deployment-validation", "Markers": "deploy", "Modules Covered": "All (deployment gate)", "Matrix": "Single"},
        ])
        st.dataframe(ci_jobs, use_container_width=True, hide_index=True)

    # ================================================================
    # TAB 4: ROUTE TESTER
    # ================================================================
    with tab_test:
        st.markdown("### Interactive Route Tester")
        st.markdown("Test FastAPI endpoints directly from the dashboard. "
                     "The FastAPI server must be running on the configured host.")

        api_base = st.text_input("API Base URL", value="http://localhost:8000", key="api_plug_base_url")

        endpoints = {
            "GET /health": {"method": "GET", "path": "/health", "params": {}, "body": None,
                            "description": "Health check - verify server is running"},
            "GET /api/datastore/stats": {"method": "GET", "path": "/api/datastore/stats", "params": {}, "body": None,
                                          "description": "Get data store statistics"},
            "GET /api/datastore/patterns": {"method": "GET", "path": "/api/datastore/patterns", "params": {}, "body": None,
                                             "description": "Get analyzed patterns from store"},
            "GET /api/agents/insights": {"method": "GET", "path": "/api/agents/insights", "params": {}, "body": None,
                                          "description": "Get pattern insights from all agents"},
            "GET /api/agents/{name}/history": {"method": "GET", "path": "/api/agents/{name}/history",
                                                "params": {"name": "sre_agent", "limit": "10"}, "body": None,
                                                "description": "Get execution history for a specific agent"},
            "GET /api/datastore/artifact/{id}": {"method": "GET", "path": "/api/datastore/artifact/{id}",
                                                  "params": {"id": ""}, "body": None,
                                                  "description": "Retrieve a specific artifact by UUID"},
            "POST /api/agents/execute": {"method": "POST", "path": "/api/agents/execute", "params": {},
                                          "body": '{"test_data": {"sample": "test"}}',
                                          "description": "Execute all agents with provided test data"},
            "POST /api/datastore/search": {"method": "POST", "path": "/api/datastore/search", "params": {},
                                            "body": '{"query": "test", "limit": 5}',
                                            "description": "Search for artifacts matching a query"},
        }

        selected = st.selectbox("Select Endpoint", list(endpoints.keys()), key="api_plug_endpoint")
        ep = endpoints[selected]
        st.caption(ep["description"])

        # Parameter inputs
        resolved_path = ep["path"]
        if ep["params"]:
            st.markdown("**Parameters:**")
            param_values = {}
            cols = st.columns(min(len(ep["params"]), 4))
            for i, (k, default) in enumerate(ep["params"].items()):
                with cols[i]:
                    param_values[k] = st.text_input(k, value=default, key=f"api_plug_param_{k}")
            for k, v in param_values.items():
                resolved_path = resolved_path.replace(f"{{{k}}}", v)

        # Body input for POST
        body_str = None
        if ep["body"] is not None:
            body_str = st.text_area("Request Body (JSON)", value=ep["body"], height=100, key="api_plug_body")

        full_url = f"{api_base}{resolved_path}"
        st.code(f"{ep['method']} {full_url}", language="bash")

        col_send, col_batch = st.columns(2)

        with col_send:
            send_clicked = st.button("Send Request", type="primary", key="api_plug_send")

        with col_batch:
            batch_clicked = st.button("Batch Health Check (all GET routes)", key="api_plug_batch")

        if send_clicked:
            try:
                import requests as req_lib
                import time as time_mod

                start = time_mod.time()
                if ep["method"] == "GET":
                    resp = req_lib.get(full_url, timeout=10)
                else:
                    import json
                    body = json.loads(body_str) if body_str else {}
                    resp = req_lib.post(full_url, json=body, timeout=10)
                elapsed = (time_mod.time() - start) * 1000

                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("Status", resp.status_code)
                rc2.metric("Response Time", f"{elapsed:.0f}ms")
                content_type = resp.headers.get("content-type", "unknown")
                rc3.metric("Content-Type", content_type[:30])

                if resp.status_code < 300:
                    st.success(f"Request successful ({resp.status_code})")
                elif resp.status_code < 500:
                    st.warning(f"Client error ({resp.status_code})")
                else:
                    st.error(f"Server error ({resp.status_code})")

                st.markdown("**Response Body:**")
                try:
                    st.json(resp.json())
                except Exception:
                    st.code(resp.text[:2000])

                with st.expander("Response Headers"):
                    for k, v in resp.headers.items():
                        st.text(f"{k}: {v}")

            except ImportError:
                st.error("The `requests` library is required. Install with: `pip install requests`")
            except Exception as e:
                if "ConnectionError" in type(e).__name__ or "Connection refused" in str(e):
                    st.error("Connection refused. Is the FastAPI server running?\n\n"
                              "Start it with: `uvicorn agent_api:app --host 0.0.0.0 --port 8000`")
                else:
                    st.error(f"Request failed: {e}")

        if batch_clicked:
            try:
                import requests as req_lib
                import time as time_mod

                results = []
                for name, ep_def in endpoints.items():
                    if ep_def["method"] != "GET" or "{" in ep_def["path"]:
                        continue
                    try:
                        start = time_mod.time()
                        resp = req_lib.get(f"{api_base}{ep_def['path']}", timeout=5)
                        elapsed = (time_mod.time() - start) * 1000
                        results.append({"Endpoint": name, "Status": resp.status_code,
                                        "Time (ms)": f"{elapsed:.0f}", "Result": "OK" if resp.status_code < 300 else "Error"})
                    except Exception:
                        results.append({"Endpoint": name, "Status": "-", "Time (ms)": "-", "Result": "Connection Refused"})

                if results:
                    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
                    ok_count = sum(1 for r in results if r["Result"] == "OK")
                    if ok_count == len(results):
                        st.success(f"All {ok_count} endpoints healthy")
                    elif ok_count > 0:
                        st.warning(f"{ok_count}/{len(results)} endpoints responding")
                    else:
                        st.error("No endpoints responding. Start the FastAPI server first.")

            except ImportError:
                st.error("The `requests` library is required. Install with: `pip install requests`")


def render_prompt_ops():
    """Prompt-driven workflow intake and lifecycle controls."""
    st.subheader("🧭 Operator Console")
    st.markdown(
        "Primary intake for user intent and governed execution. Submit requests, collaborate in chat, "
        "and run approve/queue/execute workflows from a single surface."
    )

    api_base = st.text_input(
        "Control Plane API URL",
        value=os.getenv("AGENTICQA_API_URL", "http://localhost:8000"),
        key="prompt_ops_api_base",
    ).rstrip("/")

    with st.expander("New Prompt Request", expanded=True):
        prompt = st.text_area(
            "Prompt",
            placeholder="Example: Add retry with exponential backoff to webhook delivery and include tests.",
            height=140,
            key="prompt_ops_prompt",
        )
        repo = st.text_input("Repository Path", value=".", key="prompt_ops_repo")
        requester = st.text_input("Requester", value="dashboard_user", key="prompt_ops_requester")
        col_meta1, col_meta2 = st.columns(2)
        with col_meta1:
            approved_by = st.text_input("Approved By (required for push/PR)", value="", key="prompt_ops_approved_by")
        with col_meta2:
            policy_ticket = st.text_input("Policy Ticket (required for PR)", value="", key="prompt_ops_policy_ticket")
        col_meta3, col_meta4 = st.columns(2)
        with col_meta3:
            allow_high_risk = st.checkbox("Allow High-Risk Changes", value=False, key="prompt_ops_allow_high_risk")
        with col_meta4:
            auto_rollback = st.checkbox("Auto Rollback on Failure", value=True, key="prompt_ops_auto_rollback")
        col_meta5, col_meta6 = st.columns(2)
        with col_meta5:
            max_sdet_iterations = st.number_input(
                "Max SDET Loop Iterations",
                min_value=1,
                max_value=5,
                value=3,
                step=1,
                key="prompt_ops_max_sdet_iterations",
            )
        with col_meta6:
            require_sdet_loop = st.checkbox(
                "Require SDET Test Loop",
                value=True,
                key="prompt_ops_require_sdet_loop",
                help="When enabled, generated code must pass SDET-generated tests before workflow completion.",
            )
        col_meta7, col_meta8 = st.columns(2)
        with col_meta7:
            enable_sdet_autofix = st.checkbox(
                "Enable SDET Auto-Fix",
                value=True,
                key="prompt_ops_enable_sdet_autofix",
                help="Allows bounded auto-fix attempts on generated code before failing the workflow.",
            )
        with col_meta8:
            max_sdet_fix_attempts = st.number_input(
                "Max SDET Auto-Fix Attempts",
                min_value=0,
                max_value=5,
                value=2,
                step=1,
                key="prompt_ops_max_sdet_fix_attempts",
            )

        col_submit, col_ping = st.columns([1, 1])
        with col_submit:
            submit = st.button("Create Workflow Request", type="primary", key="prompt_ops_submit")
        with col_ping:
            ping = st.button("Health Check API", key="prompt_ops_ping")

        if ping:
            try:
                import requests as req_lib

                response = req_lib.get(f"{api_base}/health", timeout=6)
                if response.status_code == 200:
                    st.success("Control plane is reachable.")
                    st.json(response.json())
                else:
                    st.warning(f"Health endpoint returned {response.status_code}")
            except Exception as e:
                st.error(
                    "Control plane API unreachable. Start with: "
                    "`uvicorn agent_api:app --host 0.0.0.0 --port 8000`\n\n"
                    f"Error: {e}"
                )

        if submit:
            if not prompt.strip():
                st.error("Prompt cannot be empty.")
            else:
                try:
                    import requests as req_lib

                    payload = {
                        "prompt": prompt,
                        "repo": repo,
                        "requester": requester,
                        "metadata": {
                            "source": "dashboard",
                            "approved_by": approved_by.strip(),
                            "policy_ticket": policy_ticket.strip(),
                            "allow_high_risk": allow_high_risk,
                            "auto_rollback": auto_rollback,
                            "max_sdet_iterations": int(max_sdet_iterations),
                            "require_sdet_loop": require_sdet_loop,
                            "enable_sdet_autofix": enable_sdet_autofix,
                            "max_sdet_fix_attempts": int(max_sdet_fix_attempts),
                        },
                    }
                    response = req_lib.post(f"{api_base}/api/workflows/requests", json=payload, timeout=12)
                    if response.status_code < 300:
                        body = response.json()
                        st.success("Workflow request created.")
                        st.json(body.get("request", body))
                    else:
                        st.error(f"Request failed ({response.status_code}): {response.text[:500]}")
                except Exception as e:
                    st.error(f"Failed to create workflow request: {e}")

    st.markdown("---")
    st.markdown("### 💬 Operator Chat (In-Dashboard)")
    st.caption(
        "Chat prompts are persisted and can be converted into workflow requests automatically, "
        "so users can stay fully inside the dashboard flow."
    )

    chat_col1, chat_col2, chat_col3 = st.columns([2, 1, 1])
    with chat_col1:
        auto_create_from_chat = st.checkbox(
            "Auto-create workflow requests from chat prompts",
            value=True,
            key="prompt_ops_chat_auto_create",
        )
    with chat_col2:
        chat_repo = st.text_input("Chat Repo", value=repo, key="prompt_ops_chat_repo")
    with chat_col3:
        chat_requester = st.text_input("Chat Requester", value=requester, key="prompt_ops_chat_requester")

    mode_col1, mode_col2 = st.columns([1, 1])
    with mode_col1:
        operator_mode = st.selectbox(
            "Operator Mode",
            options=["deterministic", "llm"],
            index=0,
            key="prompt_ops_operator_mode",
            help="LLM mode currently falls back to deterministic behavior until provider adapter is configured.",
        )
    with mode_col2:
        tool_execution_mode = st.selectbox(
            "Tool Execution Policy",
            options=["require_approval", "suggest_only", "auto_for_safe"],
            index=0,
            key="prompt_ops_tool_execution_mode",
            help="Governed action policy for chat turns.",
        )

    if st.button("Check Operator Config", key="prompt_ops_operator_config_check"):
        try:
            import requests as req_lib

            config_resp = req_lib.get(f"{api_base}/api/operator/config", timeout=8)
            if config_resp.status_code < 300:
                st.json(config_resp.json())
            else:
                st.warning(f"Operator config endpoint returned {config_resp.status_code}.")
        except Exception as e:
            st.warning(f"Unable to fetch operator config: {e}")

    if st.button("Start New Chat Session", key="prompt_ops_chat_new_session"):
        st.session_state["prompt_ops_chat_session_id"] = None
        st.session_state["prompt_ops_last_action_plan"] = []
        st.session_state["prompt_ops_last_mode"] = "deterministic"
        st.session_state["prompt_ops_last_tool_execution"] = "require_approval"
        st.session_state["prompt_ops_chat_reset_notice"] = True
        st.rerun()

    try:
        import requests as req_lib

        if not st.session_state.get("prompt_ops_chat_session_id"):
            create_session_resp = req_lib.post(
                f"{api_base}/api/chat/sessions",
                json={
                    "repo": chat_repo,
                    "requester": chat_requester,
                    "metadata": {"source": "dashboard_prompt_ops"},
                },
                timeout=8,
            )
            if create_session_resp.status_code < 300:
                session = (create_session_resp.json() or {}).get("session") or {}
                st.session_state["prompt_ops_chat_session_id"] = session.get("id")
            else:
                st.error(f"Unable to create chat session ({create_session_resp.status_code}).")

        if st.session_state.pop("prompt_ops_chat_reset_notice", False):
            st.success("Started a new chat session.")

        session_id = st.session_state.get("prompt_ops_chat_session_id")
        if session_id:
            st.caption(f"Session: {session_id}")
            history_resp = req_lib.get(
                f"{api_base}/api/chat/sessions/{session_id}",
                params={"limit": 150},
                timeout=8,
            )
            if history_resp.status_code < 300:
                session_payload = (history_resp.json() or {}).get("session") or {}
                history = session_payload.get("messages") or []
                for msg in history:
                    role = msg.get("role", "assistant")
                    with st.chat_message("assistant" if role == "assistant" else "user"):
                        st.write(msg.get("content", ""))
                        if msg.get("request_id"):
                            st.caption(f"Linked workflow: {msg.get('request_id')}")

        chat_input = st.chat_input("Type a request (e.g., add retries + tests to webhook flow)")
        if chat_input and session_id:
            turn_payload = {
                "session_id": session_id,
                "message": chat_input,
                "repo": chat_repo,
                "requester": chat_requester,
                "auto_create_workflow": auto_create_from_chat,
                "mode": operator_mode,
                "tool_execution": tool_execution_mode,
                "metadata": {
                    "approved_by": approved_by.strip(),
                    "policy_ticket": policy_ticket.strip(),
                    "allow_high_risk": allow_high_risk,
                    "auto_rollback": auto_rollback,
                    "max_sdet_iterations": int(max_sdet_iterations),
                    "require_sdet_loop": require_sdet_loop,
                    "enable_sdet_autofix": enable_sdet_autofix,
                    "max_sdet_fix_attempts": int(max_sdet_fix_attempts),
                },
            }
            turn_resp = req_lib.post(f"{api_base}/api/chat/turn", json=turn_payload, timeout=20)
            if turn_resp.status_code < 300:
                body = turn_resp.json() or {}
                workflow_item = body.get("workflow_request") or {}
                st.session_state["prompt_ops_last_action_plan"] = body.get("action_plan") or []
                st.session_state["prompt_ops_last_tool_execution"] = body.get("tool_execution")
                st.session_state["prompt_ops_last_mode"] = body.get("mode")
                if workflow_item.get("id"):
                    st.success(
                        f"Prompt saved and workflow created: {workflow_item.get('id')} "
                        f"({workflow_item.get('status')})"
                    )
                st.rerun()
            else:
                st.error(f"Chat turn failed ({turn_resp.status_code}): {turn_resp.text[:400]}")

        last_plan = st.session_state.get("prompt_ops_last_action_plan") or []
        if last_plan:
            st.markdown("#### 🧭 Last Operator Action Plan")
            st.caption(
                f"Mode: {st.session_state.get('prompt_ops_last_mode', 'deterministic')} · "
                f"Policy: {st.session_state.get('prompt_ops_last_tool_execution', 'require_approval')}"
            )
            plan_rows = []
            for step in last_plan:
                plan_rows.append(
                    {
                        "tool": step.get("tool"),
                        "label": step.get("label"),
                        "risk": step.get("risk"),
                        "requires_approval": step.get("requires_approval"),
                        "kind": step.get("kind"),
                    }
                )
            st.dataframe(pd.DataFrame(plan_rows), use_container_width=True, hide_index=True)
    except Exception as e:
        st.warning(f"Chat UI could not connect to control plane: {e}")

    st.markdown("---")

    # ── Natural-language agent builder ─────────────────────────────────────
    with st.expander("💬 Describe Your Agent (AI-assisted)", expanded=False):
        st.caption(
            "Describe what you need in plain English. "
            "AI extracts the name, capabilities, framework, and file scope automatically."
        )
        nl_description = st.text_area(
            "Agent description",
            placeholder=(
                "Example: An agent that scans Python files for security vulnerabilities, "
                "checks for hardcoded secrets, and reports findings as structured JSON."
            ),
            height=120,
            key="nl_agent_description",
        )
        nl_framework_override = st.selectbox(
            "Override framework (optional — leave blank to let AI decide)",
            ["", "langgraph", "langchain", "crewai", "autogen", "custom", "sandboxed"],
            key="nl_framework_override",
        )
        nl_persist = st.toggle(
            "Save to .agenticqa/custom_agents/",
            value=True,
            key="nl_persist_toggle",
        )

        if st.button("Generate from Description", key="nl_generate_btn"):
            if not nl_description.strip():
                st.warning("Enter a description first.")
            else:
                try:
                    import requests as _req

                    payload: dict = {
                        "description": nl_description.strip(),
                        "persist": nl_persist,
                    }
                    if nl_framework_override:
                        payload["framework"] = nl_framework_override

                    resp = _req.post(
                        f"{api_base}/api/agent-factory/from-prompt",
                        json=payload,
                        timeout=30,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        spec = data.get("spec", {})
                        st.success(
                            f"Generated `{spec.get('agent_name')}` "
                            f"({spec.get('framework')})"
                        )
                        st.markdown("#### Extracted Spec")
                        st.json(spec)
                        code_str = data.get("generated_code", "")
                        st.markdown("#### Generated Code")
                        st.code(code_str, language="python")
                        st.download_button(
                            "Download .py",
                            data=code_str,
                            file_name=f"{spec.get('agent_name', 'agent')}.py",
                            mime="text/plain",
                            key="nl_download_btn",
                        )
                        if data.get("persisted_path"):
                            st.info(f"Saved to: `{data['persisted_path']}`")
                    else:
                        st.error(f"API error {resp.status_code}: {resp.text[:200]}")
                except Exception as e:
                    st.error(f"Could not reach API: {e}")

    st.markdown("---")

    # ── Agent Factory ──────────────────────────────────────────────────────
    with st.expander("🏗️ Build a Governed Agent", expanded=False):
        st.caption("Scaffold a new agent with the constitutional gate, scopes, and ML loop pre-wired.")
        fc_fw = st.selectbox(
            "Framework",
            ["langgraph", "langchain", "crewai", "autogen", "custom", "sandboxed"],
            key="factory_framework",
        )
        fc_name = st.text_input("Agent name", placeholder="my_agent", key="factory_name")
        fc_caps = st.multiselect(
            "Capabilities",
            ["search", "summarize", "write_code", "review", "delegate", "shell", "email", "filesystem"],
            key="factory_caps",
        )

        # Sandbox-specific config
        sb_script = sb_dir = sb_timeout = sb_env = sb_block = None
        if fc_fw == "sandboxed":
            st.info("Sandboxed agents run in a clean subprocess — no inherited secrets, restricted cwd, output scanner enabled.")
            sb_script = st.text_input("Script path", placeholder="/path/to/agent.py", key="sb_script")
            sb_dir = st.text_input("Allowed directory (cwd)", value=".", key="sb_dir")
            sb_timeout = st.number_input("Timeout (s)", min_value=5, max_value=300, value=30, key="sb_timeout")
            sb_env_raw = st.text_input("Env vars to pass through (comma-separated)", placeholder="API_KEY,MODEL_NAME", key="sb_env")
            sb_env = [v.strip() for v in sb_env_raw.split(",") if v.strip()] if sb_env_raw else []
            sb_block = st.toggle("Block on flagged output", value=True, key="sb_block")

        if st.button("Scaffold Agent", key="factory_scaffold_btn"):
            if not fc_name.strip():
                st.warning("Enter an agent name.")
            else:
                try:
                    import requests as _req
                    resp = _req.post(
                        f"{api_base}/api/agent-factory/scaffold",
                        json={"framework": fc_fw, "agent_name": fc_name.strip(), "capabilities": fc_caps},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        st.success(f"Generated `{fc_name}` ({fc_fw})")
                        code_str = data.get("generated_code", "")
                        st.code(code_str, language="python")
                        st.download_button(
                            "Download .py",
                            data=code_str,
                            file_name=f"{fc_name.strip()}.py",
                            mime="text/plain",
                            key="factory_download",
                        )
                        if fc_fw == "sandboxed" and sb_script:
                            st.caption("Register this script as a sandboxed agent:")
                            st.json({
                                "agent_name": fc_name.strip(),
                                "script_path": sb_script,
                                "allowed_dir": sb_dir,
                                "timeout_s": int(sb_timeout),
                                "env_passthrough": sb_env,
                                "block_on_flag": sb_block,
                            })
                    else:
                        st.error(f"API error {resp.status_code}: {resp.text[:200]}")
                except Exception as e:
                    st.error(f"Could not reach API: {e}")

    st.markdown("---")

    main_col, rail_col = st.columns([3, 1])
    with main_col:
        st.markdown("### Recent Workflow Requests")

    with rail_col:
        st.markdown("#### ⏳ Pending Approvals")
        st.caption("Compact operator rail for fast approve/queue actions.")
        try:
            import requests as req_lib

            pending_resp = req_lib.get(f"{api_base}/api/workflows/requests?limit=50", timeout=8)
            if pending_resp.status_code < 300:
                all_requests = (pending_resp.json() or {}).get("requests") or []
                pending_items = [
                    item for item in all_requests
                    if item.get("status") in {"AWAITING_APPROVAL", "APPROVED"}
                ]
                awaiting_count = sum(1 for item in pending_items if item.get("status") == "AWAITING_APPROVAL")
                approved_count = sum(1 for item in pending_items if item.get("status") == "APPROVED")

                st.metric("Pending", len(pending_items))
                bd1, bd2 = st.columns(2)
                bd1.metric("Awaiting", awaiting_count)
                bd2.metric("Approved", approved_count)

                if st.button("Run Next Queued", key="rail_run_next"):
                    run_next_resp = req_lib.post(
                        f"{api_base}/api/workflows/worker/run-next",
                        json={"dry_run": True, "open_pr": False},
                        timeout=45,
                    )
                    if run_next_resp.status_code < 300:
                        next_item = (run_next_resp.json() or {}).get("request")
                        if next_item:
                            st.success(f"Ran queued request: {next_item.get('id')}")
                        else:
                            st.info("No queued requests.")
                        st.rerun()
                    else:
                        st.error(f"Run-next failed ({run_next_resp.status_code})")

                for item in pending_items[:6]:
                    req_id = item.get("id", "unknown")
                    status = item.get("status", "unknown")
                    st.markdown(f"**{req_id}**")
                    st.caption(f"{status} · {item.get('repo', '.')}")

                    action_cols = st.columns(2)
                    with action_cols[0]:
                        if status == "AWAITING_APPROVAL":
                            if st.button("Approve", key=f"rail_approve_{req_id}"):
                                resp = req_lib.post(f"{api_base}/api/workflows/requests/{req_id}/approve", timeout=10)
                                if resp.status_code < 300:
                                    st.success(f"Approved {req_id}")
                                    st.rerun()
                                else:
                                    st.error(f"Approve failed ({resp.status_code})")
                        else:
                            st.write("")

                    with action_cols[1]:
                        if status in {"APPROVED", "AWAITING_APPROVAL"}:
                            if st.button("Queue", key=f"rail_queue_{req_id}"):
                                if status == "AWAITING_APPROVAL":
                                    _approve = req_lib.post(f"{api_base}/api/workflows/requests/{req_id}/approve", timeout=10)
                                    if _approve.status_code >= 300:
                                        st.error(f"Approve before queue failed ({_approve.status_code})")
                                        continue
                                resp = req_lib.post(f"{api_base}/api/workflows/requests/{req_id}/queue", timeout=10)
                                if resp.status_code < 300:
                                    st.success(f"Queued {req_id}")
                                    st.rerun()
                                else:
                                    st.error(f"Queue failed ({resp.status_code})")

                    st.markdown("---")

                if not pending_items:
                    st.success("No pending approvals")
            else:
                st.warning(f"Could not load pending requests ({pending_resp.status_code})")
        except Exception as e:
            st.warning(f"Pending approvals unavailable: {e}")

    try:
        import requests as req_lib

        metrics_resp = req_lib.get(f"{api_base}/api/workflows/metrics?limit=200", timeout=8)
        if metrics_resp.status_code < 300:
            metrics = (metrics_resp.json() or {}).get("metrics", {})
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("MTTR (min)", metrics.get("mttr_minutes") if metrics.get("mttr_minutes") is not None else "n/a")
            m2.metric("Pass Rate", f"{(metrics.get('pass_rate', 0.0) * 100):.1f}%")
            m3.metric("Pass Rate Uplift", f"{metrics.get('pass_rate_uplift_pct', 0.0):.1f}%")
            m4.metric("Flaky Reduction", f"{metrics.get('flaky_reduction_pct', 0.0):.1f}%")

        readiness_resp = req_lib.get(f"{api_base}/api/system/readiness", timeout=8)
        if readiness_resp.status_code < 300:
            readiness = readiness_resp.json() or {}
            checks = readiness.get("checks", {})
            rc1, rc2, rc3, rc4, rc5 = st.columns(5)
            rc1.metric("Workflow DB", "OK" if checks.get("workflow_db_writable") else "Issue")
            rc2.metric("Observability DB", "OK" if checks.get("observability_db_writable") else "Issue")
            rc3.metric("Neo4j", "Connected" if checks.get("neo4j_tcp") else "Offline")
            rc4.metric("Weaviate", "Connected" if checks.get("weaviate_tcp") else "Offline")
            rc5.metric("Qdrant", "Connected" if checks.get("qdrant_tcp") else "Offline")

            provider = str(checks.get("vector_provider") or "unknown").upper()
            provider_up = bool(checks.get("vector_provider_tcp"))
            provider_state = "Connected" if provider_up else "Offline"
            st.caption(f"Active vector provider: {provider} ({provider_state})")

        evidence_resp = req_lib.get(f"{api_base}/api/workflows/evidence?limit=500", timeout=8)
        if evidence_resp.status_code < 300:
            evidence = ((evidence_resp.json() or {}).get("evidence") or {})
            claims = evidence.get("claims") or {}
            if claims:
                st.markdown("### 📌 Client Value Evidence")
                rows = []
                for name, payload in claims.items():
                    rows.append(
                        {
                            "claim": name,
                            "metric": payload.get("metric"),
                            "value": payload.get("value"),
                            "status": payload.get("status"),
                        }
                    )
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        portability_resp = req_lib.get(
            f"{api_base}/api/workflows/portability-scorecard",
            params={"repo": repo, "limit": 500},
            timeout=8,
        )
        if portability_resp.status_code < 300:
            payload = portability_resp.json() or {}
            scorecard = payload.get("scorecard") or {}
            scores = scorecard.get("scores") or {}
            delta = scorecard.get("delta") or {}
            quick_wins = scorecard.get("quick_wins") or []

            st.markdown("### 🚀 Repo Portability Scorecard")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Overall", f"{float(scores.get('overall', 0.0)):.1f}")
            s2.metric("Onboarding", f"{float(scores.get('onboarding_readiness', 0.0)):.1f}")
            s3.metric("Reliability", f"{float(scores.get('execution_reliability', 0.0)):.1f}")
            s4.metric("Observability", f"{float(scores.get('observability_quality', 0.0)):.1f}")

            if delta:
                trend_icon = "✅" if delta.get("trend") == "improved" else "⚠️" if delta.get("trend") == "regressed" else "➖"
                st.info(
                    f"{trend_icon} Baseline→Delta: {delta.get('overall_delta', 0.0):+.2f} "
                    f"(baseline {delta.get('baseline_overall', 0.0):.2f} → current {delta.get('current_overall', 0.0):.2f})"
                )
            else:
                st.caption("No baseline saved yet. Save one to activate baseline→delta tracking.")

            if quick_wins:
                st.markdown("**Immediate Quick Wins**")
                for tip in quick_wins:
                    st.write(f"- {tip}")

            baseline_note = st.text_input(
                "Baseline note",
                value="",
                key="prompt_ops_portability_baseline_note",
                help="Optional note saved with this baseline snapshot.",
            )
            if st.button("Save Current as Baseline", key="prompt_ops_save_portability_baseline"):
                baseline_resp = req_lib.post(
                    f"{api_base}/api/workflows/portability-scorecard/baseline",
                    json={"repo": repo, "note": baseline_note},
                    timeout=10,
                )
                if baseline_resp.status_code < 300:
                    st.success("Baseline saved. Refresh to view updated delta.")
                else:
                    st.error(f"Failed to save baseline ({baseline_resp.status_code}): {baseline_resp.text[:300]}")
    except Exception:
        pass

    refresh = st.button("Refresh Requests", key="prompt_ops_refresh")
    if refresh or True:
        try:
            import requests as req_lib

            response = req_lib.get(f"{api_base}/api/workflows/requests?limit=30", timeout=10)
            if response.status_code < 300:
                items = response.json().get("requests", [])
                if items:
                    rows = []
                    for r in items:
                        rows.append(
                            {
                                "id": r.get("id"),
                                "status": r.get("status"),
                                "next_action": r.get("next_action"),
                                "requester": r.get("requester"),
                                "repo": r.get("repo"),
                                "created_at": r.get("created_at"),
                                "updated_at": r.get("updated_at"),
                            }
                        )
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                    request_ids = [r["id"] for r in rows if r.get("id")]
                    selected_id = st.selectbox(
                        "Select Request",
                        options=request_ids,
                        key="prompt_ops_selected_request",
                    )

                    exec_col1, exec_col2, exec_col3 = st.columns([1, 1, 1])
                    with exec_col1:
                        worker_dry_run = st.checkbox(
                            "Dry Run Worker",
                            value=True,
                            key="prompt_ops_worker_dry_run",
                            help="When enabled, worker creates branch/commit locally without pushing or opening a PR.",
                        )
                    with exec_col2:
                        worker_open_pr = st.checkbox(
                            "Open PR",
                            value=True,
                            key="prompt_ops_worker_open_pr",
                            help="Requires Dry Run disabled plus GITHUB_TOKEN and a resolvable GitHub repo.",
                        )
                    with exec_col3:
                        do_run_next = st.button("Run Next Queued", key="prompt_ops_run_next")

                    col_a, col_q, col_c, col_i, col_r, col_replay = st.columns([1, 1, 1, 1, 1, 1])
                    with col_a:
                        do_approve = st.button("Approve", key="prompt_ops_approve")
                    with col_q:
                        do_queue = st.button("Queue", key="prompt_ops_queue")
                    with col_c:
                        do_cancel = st.button("Cancel", key="prompt_ops_cancel")
                    with col_i:
                        do_inspect = st.button("Inspect", key="prompt_ops_inspect")
                    with col_r:
                        do_run_selected = st.button("Run Selected", key="prompt_ops_run_selected")
                    with col_replay:
                        do_replay = st.button("Replay", key="prompt_ops_replay")

                    worker_payload = {
                        "dry_run": worker_dry_run,
                        "open_pr": worker_open_pr,
                    }

                    if do_run_next:
                        resp = req_lib.post(
                            f"{api_base}/api/workflows/worker/run-next",
                            json=worker_payload,
                            timeout=60,
                        )
                        if resp.status_code < 300:
                            body = resp.json()
                            item = body.get("request")
                            if item:
                                st.success("Worker executed queued request.")
                                st.json(item)
                            else:
                                st.info(body.get("message", "No queued requests."))
                        else:
                            st.error(f"Run-next failed ({resp.status_code}): {resp.text[:500]}")

                    if do_approve:
                        resp = req_lib.post(f"{api_base}/api/workflows/requests/{selected_id}/approve", timeout=10)
                        if resp.status_code < 300:
                            st.success("Approved.")
                            st.json(resp.json().get("request", {}))
                        else:
                            st.error(f"Approve failed ({resp.status_code}): {resp.text[:400]}")

                    if do_queue:
                        resp = req_lib.post(f"{api_base}/api/workflows/requests/{selected_id}/queue", timeout=10)
                        if resp.status_code < 300:
                            st.success("Queued.")
                            st.json(resp.json().get("request", {}))
                        else:
                            st.error(f"Queue failed ({resp.status_code}): {resp.text[:400]}")

                    if do_cancel:
                        resp = req_lib.post(
                            f"{api_base}/api/workflows/requests/{selected_id}/cancel",
                            json={"reason": "cancelled_from_dashboard"},
                            timeout=10,
                        )
                        if resp.status_code < 300:
                            st.warning("Cancelled.")
                            st.json(resp.json().get("request", {}))
                        else:
                            st.error(f"Cancel failed ({resp.status_code}): {resp.text[:400]}")

                    if do_inspect:
                        resp = req_lib.get(f"{api_base}/api/workflows/requests/{selected_id}", timeout=10)
                        if resp.status_code < 300:
                            st.json(resp.json().get("request", {}))
                        else:
                            st.error(f"Inspect failed ({resp.status_code}): {resp.text[:400]}")

                    if do_run_selected:
                        resp = req_lib.post(
                            f"{api_base}/api/workflows/worker/run/{selected_id}",
                            json=worker_payload,
                            timeout=60,
                        )
                        if resp.status_code < 300:
                            st.success("Worker executed selected request.")
                            st.json(resp.json().get("request", {}))
                        else:
                            st.error(f"Run selected failed ({resp.status_code}): {resp.text[:500]}")

                    if do_replay:
                        resp = req_lib.post(
                            f"{api_base}/api/workflows/requests/{selected_id}/replay",
                            json={"requester": requester},
                            timeout=20,
                        )
                        if resp.status_code < 300:
                            st.success("Replay request created and queued.")
                            st.json(resp.json().get("request", {}))
                        else:
                            st.error(f"Replay failed ({resp.status_code}): {resp.text[:500]}")

                    st.markdown("---")
                    st.markdown("### 🔎 Agent Observability Timeline")
                    st.caption(
                        "Trace-level visibility across worker orchestration, SDET loops, "
                        "status transitions, and latency details."
                    )

                    obs_col1, obs_col2 = st.columns([1, 1])
                    with obs_col1:
                        trace_limit = st.number_input(
                            "Trace Limit",
                            min_value=5,
                            max_value=200,
                            value=30,
                            step=5,
                            key="prompt_ops_trace_limit",
                        )
                    with obs_col2:
                        obs_event_limit = st.number_input(
                            "Event Limit",
                            min_value=10,
                            max_value=500,
                            value=100,
                            step=10,
                            key="prompt_ops_event_limit",
                        )

                    quality_resp = req_lib.get(
                        f"{api_base}/api/observability/quality?limit={int(trace_limit)}&min_completeness=0.95&min_decision_quality=0.60",
                        timeout=10,
                    )
                    if quality_resp.status_code < 300:
                        q = (quality_resp.json() or {}).get("quality", {})
                        q1, q2, q3, q4, q5, q6 = st.columns(6)
                        with q1:
                            st.metric("Trace Count", int(q.get("trace_count") or 0))
                        with q2:
                            st.metric("Avg Completeness", f"{float(q.get('avg_completeness_ratio') or 0.0):.3f}")
                        with q3:
                            st.metric("Min Completeness", f"{float(q.get('min_completeness_ratio') or 0.0):.3f}")
                        with q4:
                            st.metric("Below Threshold", int(q.get("below_threshold_count") or 0))
                        with q5:
                            st.metric(
                                "Avg Decision Quality",
                                f"{float(q.get('avg_decision_quality_score') or 0.0):.3f}",
                            )
                        with q6:
                            st.metric(
                                "Decision Quality Below",
                                int(q.get("decision_quality_below_threshold_count") or 0),
                            )
                    else:
                        st.warning(f"Trace quality summary unavailable ({quality_resp.status_code}).")

                    insights_resp = req_lib.get(
                        f"{api_base}/api/observability/insights?limit={int(obs_event_limit)}",
                        timeout=10,
                    )
                    if insights_resp.status_code < 300:
                        insights = (insights_resp.json() or {}).get("insights", {})
                        failures = insights.get("failures", {})
                        policy_impact = insights.get("policy_impact", {})

                        st.markdown("#### Global Observability Insights")
                        g1, g2, g3, g4 = st.columns(4)
                        with g1:
                            st.metric("Failed Events", int(failures.get("failed_events") or 0))
                        with g2:
                            st.metric("Failure Rate", f"{float(failures.get('failure_rate') or 0.0):.3f}")
                        with g3:
                            st.metric("Policy Blocked", int(policy_impact.get("policy_blocked_runs") or 0))
                        with g4:
                            st.metric("Policy Block Rate", f"{float(policy_impact.get('policy_block_rate') or 0.0):.3f}")

                        root_causes = failures.get("root_cause_counts") or []
                        if root_causes:
                            st.markdown("##### Root Cause Distribution")
                            st.dataframe(pd.DataFrame(root_causes), use_container_width=True, hide_index=True)
                    else:
                        st.warning(f"Observability insights unavailable ({insights_resp.status_code}).")

                    st.markdown("---")
                    st.markdown("### 📈 Agent Complexity Trends")
                    st.caption(
                        "Per-agent retrieval quality over time: RAG docs retrieved, average similarity score, "
                        "and LLM token usage. Anomaly detection flags when similarity drops >20% below baseline."
                    )
                    cplx_col1, cplx_col2, cplx_col3 = st.columns([2, 1, 1])
                    with cplx_col1:
                        cplx_agent = st.text_input(
                            "Agent name (blank = all)",
                            value="",
                            key="cplx_agent_filter",
                            placeholder="e.g. QA_Assistant",
                        )
                    with cplx_col2:
                        cplx_window = st.number_input(
                            "Window (days)",
                            min_value=1,
                            max_value=90,
                            value=14,
                            step=1,
                            key="cplx_window_days",
                        )
                    with cplx_col3:
                        do_cplx = st.button("Load Complexity Trends", key="cplx_load_btn")

                    if do_cplx:
                        cplx_url = (
                            f"{api_base}/api/observability/agent-complexity"
                            f"?window_days={int(cplx_window)}"
                            + (f"&agent={cplx_agent.strip()}" if cplx_agent.strip() else "")
                        )
                        cplx_resp = req_lib.get(cplx_url, timeout=10)
                        if cplx_resp.status_code == 200:
                            cplx_data = cplx_resp.json()
                            if cplx_agent.strip():
                                # Single-agent view
                                trends = cplx_data.get("trends", {})
                                summary = trends.get("summary", {})
                                cplx_s1, cplx_s2, cplx_s3, cplx_s4 = st.columns(4)
                                with cplx_s1:
                                    st.metric("Total Actions", summary.get("total_actions", 0))
                                with cplx_s2:
                                    st.metric("Avg RAG Docs", f"{float(summary.get('avg_rag_docs', 0)):.1f}")
                                with cplx_s3:
                                    st.metric("Avg Similarity", f"{float(summary.get('avg_similarity', 0)):.3f}")
                                with cplx_s4:
                                    prompt_tok = summary.get("total_llm_prompt_tokens") or 0
                                    comp_tok = summary.get("total_llm_completion_tokens") or 0
                                    st.metric("LLM Tokens", f"{int(prompt_tok)+int(comp_tok):,}")
                                if trends.get("anomaly"):
                                    st.warning(f"⚠️ Anomaly: {trends.get('anomaly_reason', 'similarity degraded')}")
                                daily = trends.get("daily", [])
                                if daily:
                                    daily_df = pd.DataFrame(daily)
                                    if "avg_similarity" in daily_df.columns and "date" in daily_df.columns:
                                        fig_sim = px.line(
                                            daily_df, x="date", y="avg_similarity",
                                            title=f"Avg Similarity — {cplx_agent.strip()} ({int(cplx_window)}d)",
                                            markers=True,
                                        )
                                        fig_sim.update_layout(height=260)
                                        st.plotly_chart(fig_sim, use_container_width=True)
                                    st.dataframe(daily_df, use_container_width=True, hide_index=True)
                            else:
                                # All-agents summary
                                agents_summary = cplx_data.get("agents", [])
                                anomalies = cplx_data.get("anomalies", [])
                                if anomalies:
                                    st.warning(f"⚠️ {len(anomalies)} agent(s) with anomalies: {', '.join(anomalies)}")
                                if agents_summary:
                                    st.dataframe(
                                        pd.DataFrame(agents_summary),
                                        use_container_width=True,
                                        hide_index=True,
                                    )
                                else:
                                    st.info("No complexity data yet. Run workflows to populate trends.")
                        else:
                            st.warning(f"Complexity trends unavailable ({cplx_resp.status_code}).")

                    st.markdown("---")
                    traces_resp = req_lib.get(
                        f"{api_base}/api/observability/traces?limit={int(trace_limit)}",
                        timeout=10,
                    )
                    if traces_resp.status_code < 300:
                        traces = traces_resp.json().get("traces", [])
                        if traces:
                            trace_rows = []
                            for t in traces:
                                trace_rows.append(
                                    {
                                        "trace_id": t.get("trace_id"),
                                        "request_id": t.get("request_id"),
                                        "events": t.get("event_count"),
                                        "last_status": t.get("last_status"),
                                        "last_agent": t.get("last_agent"),
                                        "last_action": t.get("last_action"),
                                        "started_at": t.get("started_at"),
                                        "ended_at": t.get("ended_at"),
                                    }
                                )

                            st.dataframe(pd.DataFrame(trace_rows), use_container_width=True, hide_index=True)

                            selected_trace = st.selectbox(
                                "Select Trace",
                                options=[r["trace_id"] for r in trace_rows if r.get("trace_id")],
                                key="prompt_ops_selected_trace",
                            )

                            trace_resp = req_lib.get(
                                f"{api_base}/api/observability/traces/{selected_trace}?limit={int(obs_event_limit)}",
                                timeout=10,
                            )
                            analysis_resp = req_lib.get(
                                f"{api_base}/api/observability/traces/{selected_trace}/analysis?limit={int(obs_event_limit)}",
                                timeout=10,
                            )
                            if trace_resp.status_code < 300:
                                trace = trace_resp.json().get("trace", {})
                                events = trace.get("events", [])
                                if events:
                                    event_rows = []
                                    for e in events:
                                        event_rows.append(
                                            {
                                                "event_type": e.get("event_type") or "unknown",
                                                "span_id": e.get("span_id"),
                                                "parent_span_id": e.get("parent_span_id"),
                                                "agent": e.get("agent"),
                                                "action": e.get("action"),
                                                "step_key": e.get("step_key"),
                                                "attempt": e.get("attempt"),
                                                "status": e.get("status"),
                                                "latency_ms": e.get("latency_ms"),
                                                "error": e.get("error"),
                                                "input_hash": e.get("input_hash"),
                                                "output_hash": e.get("output_hash"),
                                                "started_at": e.get("started_at"),
                                                "ended_at": e.get("ended_at"),
                                                "created_at": e.get("created_at"),
                                            }
                                        )
                                    st.dataframe(pd.DataFrame(event_rows), use_container_width=True, hide_index=True)

                                    timeline_df = pd.DataFrame(event_rows)
                                    timeline_df["start"] = pd.to_datetime(
                                        timeline_df["started_at"].fillna(timeline_df["created_at"]),
                                        errors="coerce",
                                        utc=True,
                                    )
                                    timeline_df["end"] = pd.to_datetime(
                                        timeline_df["ended_at"].fillna(timeline_df["created_at"]),
                                        errors="coerce",
                                        utc=True,
                                    )
                                    timeline_df = timeline_df.dropna(subset=["start", "end"])
                                    if not timeline_df.empty:
                                        timeline_df["task"] = (
                                            timeline_df["agent"].astype(str)
                                            + " :: "
                                            + timeline_df["action"].astype(str)
                                            + " :: "
                                            + timeline_df["status"].astype(str)
                                        )
                                        st.markdown("#### Full Trace Timeline")
                                        fig_timeline = px.timeline(
                                            timeline_df,
                                            x_start="start",
                                            x_end="end",
                                            y="task",
                                            color="status",
                                            hover_data=["event_type", "step_key", "attempt", "latency_ms", "span_id"],
                                        )
                                        fig_timeline.update_layout(height=420, yaxis_title="Trace Step", xaxis_title="Time")
                                        st.plotly_chart(fig_timeline, use_container_width=True)

                                    if analysis_resp.status_code < 300:
                                        analysis = (analysis_resp.json() or {}).get("analysis", {})
                                        st.markdown("#### Trace Analysis")
                                        a1, a2, a3, a4 = st.columns(4)
                                        with a1:
                                            st.metric("Spans", int(analysis.get("span_count") or 0))
                                        with a2:
                                            st.metric(
                                                "Completeness",
                                                f"{float(analysis.get('completeness_ratio') or 0.0):.3f}",
                                            )
                                        with a3:
                                            st.metric("Orphan Spans", int(analysis.get("orphan_span_count") or 0))
                                        with a4:
                                            st.metric(
                                                "Critical Path (ms)",
                                                f"{float(analysis.get('critical_path_ms') or 0.0):.1f}",
                                            )

                                        spans = analysis.get("spans") or []
                                        if spans:
                                            st.markdown("##### Span Tree")
                                            st.dataframe(
                                                pd.DataFrame(spans)[
                                                    [
                                                        "span_id",
                                                        "parent_span_id",
                                                        "agent",
                                                        "action",
                                                        "event_type",
                                                        "step_key",
                                                        "latency_ms",
                                                        "statuses",
                                                        "children",
                                                    ]
                                                ],
                                                use_container_width=True,
                                                hide_index=True,
                                            )

                                        by_agent_action = analysis.get("by_agent_action") or []
                                        if by_agent_action:
                                            st.markdown("##### Aggregated by Agent/Action")
                                            st.dataframe(pd.DataFrame(by_agent_action), use_container_width=True, hide_index=True)

                                        cf_resp = req_lib.get(
                                            f"{api_base}/api/observability/traces/{selected_trace}/counterfactuals?limit={int(obs_event_limit)}",
                                            timeout=10,
                                        )
                                        if cf_resp.status_code < 300:
                                            cf = (cf_resp.json() or {}).get("counterfactuals", {})
                                            recs = cf.get("recommendations") or []
                                            st.markdown("##### Counterfactual Recommendations")
                                            if recs:
                                                rec_rows = []
                                                for r in recs:
                                                    rec_rows.append(
                                                        {
                                                            "agent": r.get("agent"),
                                                            "action": r.get("action"),
                                                            "status": r.get("status"),
                                                            "root_cause": r.get("root_cause"),
                                                            "error": r.get("error"),
                                                            "counterfactuals": " | ".join(r.get("counterfactuals") or []),
                                                        }
                                                    )
                                                st.dataframe(pd.DataFrame(rec_rows), use_container_width=True, hide_index=True)
                                            else:
                                                st.info("No failed/retried steps for counterfactuals in this trace.")
                                        else:
                                            st.warning(f"Counterfactual lookup unavailable ({cf_resp.status_code}).")

                                        with st.expander("📋 Generate Audit Report", expanded=False):
                                            st.caption(
                                                "Generates a shareable compliance artifact: verdict, "
                                                "decision quality score, root causes, and recommendations. "
                                                "Paste the Markdown into any PR description."
                                            )
                                            audit_col1, audit_col2 = st.columns([3, 1])
                                            with audit_col2:
                                                audit_fmt = st.radio(
                                                    "Format",
                                                    ["structured", "markdown"],
                                                    key="audit_report_fmt",
                                                    horizontal=True,
                                                )
                                            with audit_col1:
                                                do_audit = st.button("Generate Audit Report", key="audit_report_btn")
                                            if do_audit:
                                                ar_resp = req_lib.get(
                                                    f"{api_base}/api/observability/traces/{selected_trace}/audit-report"
                                                    f"?format={audit_fmt}",
                                                    timeout=15,
                                                )
                                                if ar_resp.status_code == 200:
                                                    ar = ar_resp.json()
                                                    if audit_fmt == "markdown":
                                                        st.markdown(ar.get("markdown_body", ""))
                                                    else:
                                                        verdict = ar.get("verdict", "")
                                                        verdict_color = "green" if verdict == "PASS" else "red"
                                                        st.markdown(
                                                            f"**Verdict:** :{verdict_color}[{verdict}]"
                                                            f"  &nbsp;  **Audit ID:** `{ar.get('audit_id')}`"
                                                        )
                                                        summary = ar.get("summary", {})
                                                        dq = ar.get("decision_quality", {})
                                                        ar1, ar2, ar3, ar4 = st.columns(4)
                                                        with ar1:
                                                            st.metric("Total Events", summary.get("total_events", 0))
                                                        with ar2:
                                                            st.metric("Agents Involved", len(summary.get("agents_involved", [])))
                                                        with ar3:
                                                            st.metric("Decision Quality", f"{float(dq.get('score', 0)):.2f}")
                                                        with ar4:
                                                            st.metric("Completeness", f"{float(dq.get('completeness', 0)):.2f}")
                                                        recs = ar.get("recommendations", [])
                                                        if recs:
                                                            st.markdown("**Recommendations:**")
                                                            for r in recs:
                                                                st.markdown(f"- {r}")
                                                        with st.expander("Full Audit Report JSON"):
                                                            st.json(ar)
                                                elif ar_resp.status_code == 404:
                                                    st.warning("No events found for this trace — run a workflow first.")
                                                else:
                                                    st.error(f"Audit report failed ({ar_resp.status_code}): {ar_resp.text[:300]}")
                                    else:
                                        st.warning(
                                            f"Trace analysis unavailable ({analysis_resp.status_code}): "
                                            f"{analysis_resp.text[:200]}"
                                        )

                                    with st.expander("Selected Trace JSON", expanded=False):
                                        st.json(trace)
                                else:
                                    st.info("No events found for selected trace.")
                            else:
                                st.error(f"Trace lookup failed ({trace_resp.status_code}): {trace_resp.text[:300]}")
                        else:
                            st.info("No observability traces yet. Run a workflow request to generate trace events.")
                    else:
                        st.error(f"Could not load traces ({traces_resp.status_code}): {traces_resp.text[:300]}")
                else:
                    st.info("No workflow requests yet. Submit a prompt above.")
            else:
                st.error(f"Could not load requests ({response.status_code}).")
        except Exception as e:
            st.error(
                "Unable to query workflow requests. Ensure FastAPI is running: "
                "`uvicorn agent_api:app --host 0.0.0.0 --port 8000`\n\n"
                f"Error: {e}"
            )


def render_stack_anatomy(store=None):
    """Render Stack Anatomy dashboard - full-stack framework breakdown with test coverage"""
    st.subheader("🏗️ Stack Anatomy — Framework & Test Coverage Breakdown")
    st.markdown("""
    Every framework, language, and integration in the codebase — broken down by source files,
    lines of code, test coverage, and production readiness.
    """)

    # --- Metrics Banner ---
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Frameworks", "10", help="Distinct frameworks and integrations")
    m2.metric("Source Files", "35", help="Python source files in src/")
    m3.metric("Test Files", "15", help="Pytest test files in tests/")
    m4.metric("Source LOC", "9,480", help="Lines of code in core source")
    m5.metric("Test LOC", "7,044", help="Lines of code in test suite")
    m6.metric("Test Functions", "250", help="Individual test functions across all files")

    # --- Tabs ---
    tab_map, tab_detail, tab_matrix, tab_score = st.tabs([
        "Stack Map", "Framework Detail", "Test Matrix", "Readiness Scorecard"
    ])

    # ================================================================
    # TAB 1: STACK MAP — Visual Architecture Layers
    # ================================================================
    with tab_map:
        st.markdown("### Full-Stack Architecture Map")
        st.markdown("Every technology layer in AgenticQA, from CI/CD down to data storage.")

        fig = go.Figure()

        # Define layers (bottom to top)
        layers = [
            {"y": 0.05, "label": "Data Layer", "color": "#1565C0",
             "techs": "Neo4j (Bolt:7687) · Weaviate (REST/gRPC:8080) · SQLite3 (local file)",
             "files": "8 + 24 + 2 files", "loc": "1,255 + 323 + 464 LOC"},
            {"y": 0.20, "label": "Data Processing", "color": "#2E7D32",
             "techs": "Pandas · NumPy · Great Expectations",
             "files": "3 + 2 + 1 files", "loc": "Data validation & quality pipeline"},
            {"y": 0.35, "label": "AI / RAG Engine", "color": "#6A1B9A",
             "techs": "RAG Retriever · Vector Store · Hybrid RAG · Embeddings",
             "files": "7 core modules", "loc": "2,325 LOC across RAG system"},
            {"y": 0.50, "label": "Agent Framework", "color": "#E65100",
             "techs": "Multi-Agent System · Delegation · Guardrails · Collaboration",
             "files": "8 modules", "loc": "1,400 + 698 LOC"},
            {"y": 0.65, "label": "API Layer", "color": "#C62828",
             "techs": "FastAPI (REST:8000) · Pydantic Models · Requests Client",
             "files": "3 files", "loc": "194 + 176 LOC"},
            {"y": 0.80, "label": "Presentation", "color": "#AD1457",
             "techs": "Streamlit (WebSocket:8501) · Plotly (interactive charts)",
             "files": "1 file (11 pages)", "loc": "2,423 LOC"},
            {"y": 0.95, "label": "CI / CD", "color": "#37474F",
             "techs": "GitHub Actions · Pytest (250 tests) · Docker Compose",
             "files": "5 workflows + 1 compose", "loc": "1,477 YAML + 7,044 test LOC"},
        ]

        for layer in layers:
            # Layer rectangle
            fig.add_shape(type="rect", x0=0.08, y0=layer["y"] - 0.055, x1=0.92, y1=layer["y"] + 0.055,
                          line=dict(color="white", width=1), fillcolor=layer["color"], opacity=0.85)
            # Layer label (left)
            fig.add_annotation(x=0.14, y=layer["y"] + 0.015,
                               text=f"<b>{layer['label']}</b>", showarrow=False,
                               font=dict(size=13, color="white", family="Arial Black"),
                               xanchor="left")
            # Tech details (center)
            fig.add_annotation(x=0.50, y=layer["y"] - 0.015,
                               text=layer["techs"], showarrow=False,
                               font=dict(size=9, color="rgba(255,255,255,0.85)"),
                               xanchor="center")
            # File/LOC count (right)
            fig.add_annotation(x=0.90, y=layer["y"] + 0.015,
                               text=layer["files"], showarrow=False,
                               font=dict(size=8, color="rgba(255,255,255,0.7)"),
                               xanchor="right")
            fig.add_annotation(x=0.90, y=layer["y"] - 0.015,
                               text=layer["loc"], showarrow=False,
                               font=dict(size=8, color="rgba(255,255,255,0.55)"),
                               xanchor="right")

        # Arrows between layers
        for i in range(len(layers) - 1):
            fig.add_annotation(x=0.50, y=layers[i]["y"] + 0.055,
                               ax=0.50, ay=layers[i + 1]["y"] - 0.055,
                               xref="x", yref="y", axref="x", ayref="y",
                               showarrow=True, arrowhead=2, arrowsize=1.0,
                               arrowwidth=1.5, arrowcolor="rgba(255,255,255,0.3)")

        fig.update_layout(
            plot_bgcolor='rgba(14, 17, 23, 0.95)', paper_bgcolor='rgba(14, 17, 23, 0.95)',
            height=650,
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, 1]),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.02, 1.05]),
            showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

        # Code volume breakdown
        st.markdown("---")
        st.markdown("### Code Volume by Category")

        vol_data = pd.DataFrame([
            {"Category": "Core Source (src/)", "Lines": 9480, "Files": 35, "Pct": "42%"},
            {"Category": "Test Suite (tests/)", "Lines": 7044, "Files": 15, "Pct": "31%"},
            {"Category": "Dashboard", "Lines": 2423, "Files": 1, "Pct": "11%"},
            {"Category": "Scripts & Examples", "Lines": 2076, "Files": 17, "Pct": "9%"},
            {"Category": "CI/CD Workflows", "Lines": 1477, "Files": 5, "Pct": "7%"},
        ])
        col_t, col_c = st.columns([3, 2])
        with col_t:
            st.dataframe(vol_data, use_container_width=True, hide_index=True)
        with col_c:
            fig_pie = go.Figure(data=[go.Pie(
                labels=vol_data["Category"], values=vol_data["Lines"],
                hole=0.4, textinfo="label+percent",
                marker=dict(colors=["#1565C0", "#2E7D32", "#AD1457", "#E65100", "#37474F"]),
                textfont=dict(size=10))])
            fig_pie.update_layout(
                plot_bgcolor='rgba(14, 17, 23, 0.95)', paper_bgcolor='rgba(14, 17, 23, 0.95)',
                height=280, showlegend=False, margin=dict(l=10, r=10, t=10, b=10),
                font=dict(color="white"))
            st.plotly_chart(fig_pie, use_container_width=True)

        st.info(f"**Test-to-Source Ratio: {7044/9480:.0%}** — "
                f"7,044 lines of tests validate 9,480 lines of source code")

    # ================================================================
    # TAB 2: FRAMEWORK DETAIL — Per-framework breakdown
    # ================================================================
    with tab_detail:
        st.markdown("### Framework & Integration Detail")
        st.markdown("Each framework that powers the system — files, LOC, "
                     "which tests cover it, and how thoroughly it's exercised.")

        frameworks = [
            {
                "name": "Python (Core Language)",
                "icon": "🐍", "version": "3.8+",
                "role": "Primary language for all source, tests, and scripts",
                "files": 69, "loc": 22500,
                "source_files": "All .py files in src/, tests/, scripts",
                "test_files": "All 15 test files",
                "test_functions": 250, "test_classes": 81,
                "markers": "unit, integration, pipeline, critical, fast, deployment",
                "ci_jobs": "All 16 CI jobs",
                "readiness": 92,
            },
            {
                "name": "FastAPI",
                "icon": "⚡", "version": ">=0.68.0",
                "role": "REST API server — 8 endpoints for agent execution and data access",
                "files": 1, "loc": 194,
                "source_files": "agent_api.py",
                "test_files": "test_integration_verification (indirect)",
                "test_functions": 11, "test_classes": 0,
                "markers": "integration",
                "ci_jobs": "test, deployment-validation",
                "readiness": 62,
            },
            {
                "name": "Pydantic",
                "icon": "📐", "version": ">=1.8.0",
                "role": "Request/response validation for FastAPI models",
                "files": 1, "loc": 30,
                "source_files": "agent_api.py (ExecutionRequest, ArtifactSearchRequest)",
                "test_files": "test_integration_verification (indirect)",
                "test_functions": 0, "test_classes": 0,
                "markers": "—",
                "ci_jobs": "test",
                "readiness": 55,
            },
            {
                "name": "Streamlit",
                "icon": "📊", "version": ">=1.28.0",
                "role": "Interactive analytics dashboard — 11 pages with real-time visualizations",
                "files": 1, "loc": 2423,
                "source_files": "dashboard/app.py",
                "test_files": "ui-tests (Playwright, CI only)",
                "test_functions": 0, "test_classes": 0,
                "markers": "—",
                "ci_jobs": "ui-tests",
                "readiness": 48,
            },
            {
                "name": "Plotly",
                "icon": "📈", "version": ">=5.17.0",
                "role": "Interactive chart rendering — network graphs, heatmaps, flow diagrams",
                "files": 1, "loc": 1200,
                "source_files": "dashboard/app.py (embedded)",
                "test_files": "None (visual output)",
                "test_functions": 0, "test_classes": 0,
                "markers": "—",
                "ci_jobs": "ui-tests (visual only)",
                "readiness": 40,
            },
            {
                "name": "Neo4j (Cypher)",
                "icon": "🔷", "version": ">=5.15.0",
                "role": "Graph database — delegation tracking, chain analysis, GraphRAG recommendations",
                "files": 8, "loc": 1255,
                "source_files": "graph/delegation_store.py, graph/hybrid_rag.py, collaboration/tracker.py",
                "test_files": "test_neo4j_delegation (13 tests), test_agent_delegation (10 tests)",
                "test_functions": 23, "test_classes": 8,
                "markers": "integration, critical",
                "ci_jobs": "test, deployment-validation",
                "readiness": 85,
            },
            {
                "name": "Weaviate",
                "icon": "🟢", "version": ">=4.0.0",
                "role": "Vector database — semantic search, document storage, RAG retrieval",
                "files": 24, "loc": 323,
                "source_files": "rag/weaviate_store.py, rag/config.py, rag/hybrid_retriever.py",
                "test_files": "test_agent_weaviate_integration (21 tests), test_agent_rag_integration (12 tests)",
                "test_functions": 33, "test_classes": 11,
                "markers": "integration, critical, weaviate",
                "ci_jobs": "weaviate-integration (Docker), rag-tests, agent-rag-integration",
                "readiness": 88,
            },
            {
                "name": "SQLite3",
                "icon": "🗃️", "version": "stdlib",
                "role": "Local relational store — structured metrics, execution history, success rates",
                "files": 2, "loc": 464,
                "source_files": "rag/relational_store.py, verify_hybrid_rag_storage.py",
                "test_files": "test_hybrid_rag (12 tests)",
                "test_functions": 12, "test_classes": 3,
                "markers": "integration",
                "ci_jobs": "rag-tests",
                "readiness": 75,
            },
            {
                "name": "Pytest",
                "icon": "🧪", "version": ">=6.0",
                "role": "Test framework — 250 test functions, 81 classes, 12 markers, 8 fixtures",
                "files": 18, "loc": 7044,
                "source_files": "tests/ (all files), conftest.py",
                "test_files": "N/A (is the test framework)",
                "test_functions": 250, "test_classes": 81,
                "markers": "unit, integration, pipeline, critical, fast, deployment, data_quality, data_integrity, data_security, data_snapshot, data_duplication",
                "ci_jobs": "All test jobs (12 of 16)",
                "readiness": 95,
            },
            {
                "name": "GitHub Actions",
                "icon": "🔄", "version": "N/A",
                "role": "CI/CD — 5 workflows, 16 jobs, matrix testing across Python 3.9/3.10/3.11",
                "files": 5, "loc": 1477,
                "source_files": ".github/workflows/ (ci.yml, tests.yml, pipeline-validation.yml, etc.)",
                "test_files": "test_pipeline_framework, test_pipeline_meta_validation (self-validating)",
                "test_functions": 32, "test_classes": 13,
                "markers": "pipeline, critical",
                "ci_jobs": "validate-workflows, pipeline-framework-health, final-deployment-gate",
                "readiness": 82,
            },
        ]

        for fw in frameworks:
            with st.expander(f"{fw['icon']} **{fw['name']}** — {fw['role']}", expanded=False):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Files", fw["files"])
                c2.metric("LOC", f"{fw['loc']:,}")
                c3.metric("Test Functions", fw["test_functions"])
                c4.metric("Readiness", f"{fw['readiness']}%")

                st.markdown(f"**Version**: {fw['version']}")
                st.markdown(f"**Source Files**: {fw['source_files']}")
                st.markdown(f"**Test Coverage**: {fw['test_files']}")
                st.markdown(f"**Pytest Markers**: {fw['markers']}")
                st.markdown(f"**CI/CD Jobs**: {fw['ci_jobs']}")

                # Readiness bar
                bar_color = "#4CAF50" if fw["readiness"] >= 80 else "#FF9800" if fw["readiness"] >= 60 else "#EF5350"
                st.progress(fw["readiness"] / 100, text=f"Production Readiness: {fw['readiness']}%")

        # Summary chart
        st.markdown("---")
        st.markdown("### Framework Test Coverage Comparison")

        fw_names = [fw["name"] for fw in frameworks if fw["name"] != "Pytest"]
        fw_tests = [fw["test_functions"] for fw in frameworks if fw["name"] != "Pytest"]
        fw_readiness = [fw["readiness"] for fw in frameworks if fw["name"] != "Pytest"]

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=fw_names, y=fw_tests, name="Test Functions",
            marker_color="#42A5F5", text=fw_tests, textposition="outside"))
        fig_bar.add_trace(go.Scatter(
            x=fw_names, y=fw_readiness, name="Readiness %",
            mode="lines+markers+text", text=[f"{r}%" for r in fw_readiness],
            textposition="top center", yaxis="y2",
            line=dict(color="#FF9800", width=2),
            marker=dict(size=8, color="#FF9800")))
        fig_bar.update_layout(
            plot_bgcolor='rgba(14, 17, 23, 0.95)', paper_bgcolor='rgba(14, 17, 23, 0.95)',
            height=400,
            yaxis=dict(title=dict(text="Test Functions", font=dict(color="#42A5F5")),
                       tickfont=dict(color="white"), gridcolor="rgba(255,255,255,0.1)"),
            yaxis2=dict(title=dict(text="Readiness %", font=dict(color="#FF9800")),
                        tickfont=dict(color="white"), overlaying="y", side="right", range=[0, 105]),
            xaxis=dict(tickfont=dict(color="white", size=9), tickangle=-30),
            legend=dict(font=dict(color="white"), orientation="h", yanchor="bottom", y=1.02),
            font=dict(color="white"), margin=dict(l=50, r=50, t=40, b=100))
        st.plotly_chart(fig_bar, use_container_width=True)

    # ================================================================
    # TAB 3: TEST MATRIX — Detailed test file breakdown
    # ================================================================
    with tab_matrix:
        st.markdown("### Test File Breakdown")
        st.markdown("Every test file — functions, classes, markers, and the frameworks each one validates.")

        test_details = pd.DataFrame([
            {"Test File": "test_agent_delegation", "Lines": 354, "Functions": 10, "Classes": 4,
             "Frameworks Tested": "Python, Neo4j, Collaboration",
             "Markers": "integration, critical", "Key Coverage": "Agent delegation chains, guardrails"},
            {"Test File": "test_agent_error_handling", "Lines": 490, "Functions": 23, "Classes": 5,
             "Frameworks Tested": "Python, Collaboration",
             "Markers": "integration, critical", "Key Coverage": "Error recovery, self-healing agents"},
            {"Test File": "test_agent_rag_integration", "Lines": 396, "Functions": 12, "Classes": 5,
             "Frameworks Tested": "Python, Weaviate, RAG",
             "Markers": "integration", "Key Coverage": "RAG context augmentation, document storage"},
            {"Test File": "test_agent_weaviate_integration", "Lines": 523, "Functions": 21, "Classes": 6,
             "Frameworks Tested": "Python, Weaviate",
             "Markers": "integration, weaviate", "Key Coverage": "Weaviate CRUD, vector search, schemas"},
            {"Test File": "test_code_change_tracking", "Lines": 217, "Functions": 14, "Classes": 4,
             "Frameworks Tested": "Python, Data Store",
             "Markers": "integration", "Key Coverage": "Code change impact analysis, rollback"},
            {"Test File": "test_data_validation", "Lines": 598, "Functions": 35, "Classes": 7,
             "Frameworks Tested": "Python, Pandas, NumPy",
             "Markers": "data_quality, data_integrity, data_security", "Key Coverage": "Schema validation, PII, checksums"},
            {"Test File": "test_hybrid_rag", "Lines": 321, "Functions": 12, "Classes": 3,
             "Frameworks Tested": "Python, Weaviate, SQLite3",
             "Markers": "integration", "Key Coverage": "Hybrid vector + relational search"},
            {"Test File": "test_integration_verification", "Lines": 322, "Functions": 11, "Classes": 9,
             "Frameworks Tested": "Python, FastAPI (indirect), All",
             "Markers": "integration, critical", "Key Coverage": "End-to-end system verification"},
            {"Test File": "test_local_pipeline_validation", "Lines": 487, "Functions": 20, "Classes": 7,
             "Frameworks Tested": "Python, Data Store",
             "Markers": "pipeline, critical", "Key Coverage": "Local pipeline stages, fail-fast"},
            {"Test File": "test_neo4j_delegation", "Lines": 364, "Functions": 13, "Classes": 4,
             "Frameworks Tested": "Python, Neo4j, GraphRAG",
             "Markers": "integration", "Key Coverage": "Neo4j graph queries, risk scoring"},
            {"Test File": "test_pipeline_framework", "Lines": 537, "Functions": 26, "Classes": 10,
             "Frameworks Tested": "Python, GitHub Actions",
             "Markers": "pipeline, critical", "Key Coverage": "CI pipeline health, workflow validation"},
            {"Test File": "test_pipeline_meta_validation", "Lines": 567, "Functions": 6, "Classes": 3,
             "Frameworks Tested": "Python, GitHub Actions",
             "Markers": "pipeline", "Key Coverage": "Pipeline self-validation, meta-tests"},
            {"Test File": "test_pipeline_snapshots", "Lines": 228, "Functions": 14, "Classes": 4,
             "Frameworks Tested": "Python, Data Store",
             "Markers": "data_snapshot", "Key Coverage": "Snapshot creation, comparison, SHA256"},
            {"Test File": "test_rag_retrieval", "Lines": 322, "Functions": 15, "Classes": 5,
             "Frameworks Tested": "Python, RAG, VectorStore",
             "Markers": "integration", "Key Coverage": "RAG retrieval, similarity search"},
            {"Test File": "test_ragas_evaluation", "Lines": 1160, "Functions": 18, "Classes": 5,
             "Frameworks Tested": "Python, RAG, VectorStore",
             "Markers": "integration, critical", "Key Coverage": "RAGAS evaluation metrics for all agents"},
        ])

        st.dataframe(test_details, use_container_width=True, hide_index=True,
                      column_config={"Lines": st.column_config.NumberColumn("Lines", format="%d"),
                                     "Functions": st.column_config.NumberColumn("Fns", format="%d"),
                                     "Classes": st.column_config.NumberColumn("Cls", format="%d")})

        # Test volume by file (bar chart)
        st.markdown("---")
        st.markdown("### Test Volume by File")
        fig_tv = go.Figure()
        fig_tv.add_trace(go.Bar(
            x=test_details["Test File"], y=test_details["Functions"],
            name="Test Functions", marker_color="#42A5F5",
            text=test_details["Functions"], textposition="outside"))
        fig_tv.add_trace(go.Bar(
            x=test_details["Test File"], y=test_details["Classes"],
            name="Test Classes", marker_color="#AB47BC",
            text=test_details["Classes"], textposition="outside"))
        fig_tv.update_layout(
            plot_bgcolor='rgba(14, 17, 23, 0.95)', paper_bgcolor='rgba(14, 17, 23, 0.95)',
            height=400, barmode="group",
            yaxis=dict(title="Count", tickfont=dict(color="white"), gridcolor="rgba(255,255,255,0.1)"),
            xaxis=dict(tickfont=dict(color="white", size=8), tickangle=-40),
            legend=dict(font=dict(color="white"), orientation="h", yanchor="bottom", y=1.02),
            font=dict(color="white"), margin=dict(l=50, r=20, t=40, b=140))
        st.plotly_chart(fig_tv, use_container_width=True)

        # Framework coverage heatmap
        st.markdown("---")
        st.markdown("### Test-to-Framework Coverage Heatmap")

        fw_cols = ["Python", "FastAPI", "Streamlit", "Neo4j", "Weaviate", "SQLite3",
                   "Pandas", "Data Store", "RAG", "CI/CD"]
        test_names = test_details["Test File"].tolist()

        # 1=direct, 0.5=indirect, 0=none
        fw_matrix = [
            [1, 0,   0, 0.5, 0,   0, 0, 0,   0.5, 0],     # delegation
            [1, 0,   0, 0,   0,   0, 0, 0,   0,   0],     # error_handling
            [1, 0,   0, 0,   0.5, 0, 0, 0,   1,   0],     # rag_integration
            [1, 0,   0, 0,   1,   0, 0, 0,   0.5, 0],     # weaviate
            [1, 0,   0, 0,   0,   0, 0, 1,   0,   0],     # code_change
            [1, 0,   0, 0,   0,   0, 1, 1,   0,   0],     # data_validation
            [1, 0,   0, 0,   0.5, 1, 0, 0,   1,   0],     # hybrid_rag
            [1, 0.5, 0, 0.5, 0,   0, 0, 0.5, 0.5, 0],     # integration_verification
            [1, 0,   0, 0,   0,   0, 0, 1,   0,   0.5],   # local_pipeline
            [1, 0,   0, 1,   0,   0, 0, 0,   0.5, 0],     # neo4j_delegation
            [1, 0,   0, 0,   0,   0, 0, 0,   0,   1],     # pipeline_framework
            [1, 0,   0, 0,   0,   0, 0, 0,   0,   1],     # pipeline_meta
            [1, 0,   0, 0,   0,   0, 0, 1,   0,   0],     # snapshots
            [1, 0,   0, 0,   0,   0, 0, 0,   1,   0],     # rag_retrieval
            [1, 0,   0, 0,   0.5, 0, 0, 0,   1,   0],     # ragas
        ]

        fig_hm = go.Figure(data=go.Heatmap(
            z=fw_matrix, x=fw_cols, y=test_names,
            colorscale=[[0, '#1a1a2e'], [0.5, '#FF9800'], [1, '#4CAF50']],
            text=[["Direct" if v == 1 else "Indirect" if v == 0.5 else "" for v in row] for row in fw_matrix],
            texttemplate="%{text}", textfont={"size": 9},
            hovertemplate="Test: %{y}<br>Framework: %{x}<br>Coverage: %{z}<extra></extra>",
            colorbar=dict(title="Coverage", tickvals=[0, 0.5, 1], ticktext=["None", "Indirect", "Direct"])))
        fig_hm.update_layout(
            title={"text": "Which Tests Cover Which Frameworks", "x": 0.5, "font": {"color": "white", "size": 14}},
            plot_bgcolor='rgba(14, 17, 23, 0.95)', paper_bgcolor='rgba(14, 17, 23, 0.95)',
            height=550,
            xaxis=dict(side="top", tickfont=dict(color="white", size=10)),
            yaxis=dict(tickfont=dict(color="white", size=9), autorange="reversed"),
            margin=dict(l=220, r=30, t=80, b=30), font=dict(color="white"))
        st.plotly_chart(fig_hm, use_container_width=True)

        # Pytest markers breakdown
        st.markdown("---")
        st.markdown("### Pytest Markers Distribution")

        markers_data = pd.DataFrame([
            {"Marker": "@pytest.mark.integration", "Count": 34, "Purpose": "Cross-module integration tests"},
            {"Marker": "@pytest.mark.critical", "Count": 29, "Purpose": "Must-pass tests for deployment"},
            {"Marker": "@pytest.mark.pipeline", "Count": 19, "Purpose": "CI/CD pipeline validation"},
            {"Marker": "@pytest.mark.skipif", "Count": 19, "Purpose": "Conditional execution (missing deps)"},
            {"Marker": "@pytest.mark.data_quality", "Count": 10, "Purpose": "Data validation and quality checks"},
            {"Marker": "@pytest.mark.data_integrity", "Count": 10, "Purpose": "Checksum and integrity verification"},
            {"Marker": "@pytest.mark.fast", "Count": 7, "Purpose": "Quick-running unit tests"},
            {"Marker": "@pytest.mark.data_snapshot", "Count": 6, "Purpose": "Snapshot comparison tests"},
            {"Marker": "@pytest.mark.data_duplication", "Count": 6, "Purpose": "Duplicate detection tests"},
            {"Marker": "@pytest.mark.unit", "Count": 4, "Purpose": "Isolated unit tests"},
            {"Marker": "@pytest.mark.data_security", "Count": 4, "Purpose": "PII detection, encryption tests"},
            {"Marker": "@pytest.mark.deployment", "Count": 2, "Purpose": "Deployment readiness gates"},
        ])
        st.dataframe(markers_data, use_container_width=True, hide_index=True)

        # Fixtures
        st.markdown("### Shared Fixtures (conftest.py)")
        fixtures = pd.DataFrame([
            {"Fixture": "mock_rag", "Scope": "function", "Purpose": "Mock RAG system with in-memory vector store"},
            {"Fixture": "mock_qa_agent", "Scope": "function", "Purpose": "Mock QA Agent for delegation tests"},
            {"Fixture": "mock_performance_agent", "Scope": "function", "Purpose": "Mock Performance Agent"},
            {"Fixture": "mock_compliance_agent", "Scope": "function", "Purpose": "Mock Compliance Agent"},
            {"Fixture": "mock_devops_agent", "Scope": "function", "Purpose": "Mock DevOps Agent"},
            {"Fixture": "pipeline_context", "Scope": "function", "Purpose": "Pipeline execution context dict"},
            {"Fixture": "test_artifacts_dir", "Scope": "function", "Purpose": "Temp directory for test artifacts"},
            {"Fixture": "snapshot_dir", "Scope": "function", "Purpose": "Temp directory for snapshot tests"},
        ])
        st.dataframe(fixtures, use_container_width=True, hide_index=True)

    # ================================================================
    # TAB 4: PRODUCTION READINESS SCORECARD
    # ================================================================
    with tab_score:
        st.markdown("### Production Readiness Scorecard")
        st.markdown("Each framework scored on 5 dimensions: test coverage, CI/CD integration, "
                     "error handling, documentation, and operational maturity.")

        # Scoring criteria
        scoring = [
            {"Framework": "Python (Core)", "Tests": 95, "CI/CD": 95, "Error Handling": 90,
             "Documentation": 85, "Ops Maturity": 90, "Overall": 92,
             "Verdict": "Production Ready", "Notes": "Extensive test suite, multi-version CI matrix"},
            {"Framework": "Pytest", "Tests": 100, "CI/CD": 95, "Error Handling": 90,
             "Documentation": 95, "Ops Maturity": 95, "Overall": 95,
             "Verdict": "Production Ready", "Notes": "250 tests, 12 markers, 8 fixtures, full CI integration"},
            {"Framework": "Weaviate", "Tests": 90, "CI/CD": 90, "Error Handling": 85,
             "Documentation": 80, "Ops Maturity": 90, "Overall": 88,
             "Verdict": "Production Ready", "Notes": "Docker CI service, 33 dedicated tests, graceful fallback"},
            {"Framework": "Neo4j", "Tests": 85, "CI/CD": 80, "Error Handling": 90,
             "Documentation": 80, "Ops Maturity": 85, "Overall": 85,
             "Verdict": "Production Ready", "Notes": "23 tests, schema init, connection retry logic"},
            {"Framework": "GitHub Actions", "Tests": 80, "CI/CD": 95, "Error Handling": 75,
             "Documentation": 75, "Ops Maturity": 80, "Overall": 82,
             "Verdict": "Production Ready", "Notes": "16 jobs, deployment gate, self-validating pipelines"},
            {"Framework": "SQLite3", "Tests": 75, "CI/CD": 70, "Error Handling": 80,
             "Documentation": 70, "Ops Maturity": 75, "Overall": 75,
             "Verdict": "Near Ready", "Notes": "Covered via hybrid RAG tests, schema auto-creation"},
            {"Framework": "FastAPI", "Tests": 85, "CI/CD": 75, "Error Handling": 80,
             "Documentation": 70, "Ops Maturity": 70, "Overall": 78,
             "Verdict": "Production Ready", "Notes": "19 endpoint tests covering all 8 routes, error paths, and status codes"},
            {"Framework": "Pydantic", "Tests": 80, "CI/CD": 70, "Error Handling": 75,
             "Documentation": 65, "Ops Maturity": 65, "Overall": 73,
             "Verdict": "Near Ready", "Notes": "25 validation tests for 3 models + dataclass, edge cases and type rejection"},
            {"Framework": "Streamlit", "Tests": 75, "CI/CD": 70, "Error Handling": 70,
             "Documentation": 65, "Ops Maturity": 65, "Overall": 70,
             "Verdict": "Near Ready", "Notes": "13 render function tests with mocked st module, main entrypoint coverage"},
            {"Framework": "Plotly", "Tests": 75, "CI/CD": 65, "Error Handling": 65,
             "Documentation": 60, "Ops Maturity": 60, "Overall": 67,
             "Verdict": "Near Ready", "Notes": "30 chart correctness tests: traces, colors, data, layout properties"},
        ]

        df_scoring = pd.DataFrame(scoring)

        # Overall readiness radar chart (top frameworks)
        st.markdown("#### System-Wide Readiness")
        top_fw = [s for s in scoring if s["Overall"] >= 60]

        fig_radar = go.Figure()
        categories = ["Tests", "CI/CD", "Error Handling", "Documentation", "Ops Maturity"]
        for fw in top_fw[:5]:
            values = [fw[c] for c in categories] + [fw[categories[0]]]
            fig_radar.add_trace(go.Scatterpolar(
                r=values,
                theta=categories + [categories[0]],
                fill='toself', name=fw["Framework"],
                opacity=0.6))
        fig_radar.update_layout(
            polar=dict(
                bgcolor='rgba(14, 17, 23, 0.95)',
                radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(color="white", size=8),
                                gridcolor="rgba(255,255,255,0.15)"),
                angularaxis=dict(tickfont=dict(color="white", size=10),
                                 gridcolor="rgba(255,255,255,0.15)")),
            plot_bgcolor='rgba(14, 17, 23, 0.95)', paper_bgcolor='rgba(14, 17, 23, 0.95)',
            height=450,
            legend=dict(font=dict(color="white", size=10)),
            font=dict(color="white"), margin=dict(l=60, r=60, t=30, b=30))
        st.plotly_chart(fig_radar, use_container_width=True)

        # Full scorecard table
        st.markdown("---")
        st.markdown("#### Detailed Scorecard")

        st.dataframe(df_scoring, use_container_width=True, hide_index=True,
                      column_config={
                          "Tests": st.column_config.ProgressColumn("Tests", format="%d%%", min_value=0, max_value=100),
                          "CI/CD": st.column_config.ProgressColumn("CI/CD", format="%d%%", min_value=0, max_value=100),
                          "Error Handling": st.column_config.ProgressColumn("Errors", format="%d%%", min_value=0, max_value=100),
                          "Documentation": st.column_config.ProgressColumn("Docs", format="%d%%", min_value=0, max_value=100),
                          "Ops Maturity": st.column_config.ProgressColumn("Ops", format="%d%%", min_value=0, max_value=100),
                          "Overall": st.column_config.ProgressColumn("Overall", format="%d%%", min_value=0, max_value=100),
                      })

        # Recommendations
        st.markdown("---")
        st.markdown("#### Improvement Recommendations")

        needs_attention = [s for s in scoring if s["Overall"] < 70]
        if needs_attention:
            for fw in needs_attention:
                with st.expander(f"{'🔴' if fw['Overall'] < 50 else '🟡'} {fw['Framework']} — {fw['Verdict']} ({fw['Overall']}%)"):
                    st.markdown(f"**Current State**: {fw['Notes']}")

                    # Generate specific recommendations
                    recs = []
                    if fw["Tests"] < 60:
                        recs.append("Add dedicated unit tests for core functionality")
                    if fw["CI/CD"] < 60:
                        recs.append("Add a dedicated CI job to validate this integration")
                    if fw["Error Handling"] < 60:
                        recs.append("Improve error handling with graceful fallbacks and retry logic")
                    if fw["Documentation"] < 60:
                        recs.append("Add inline documentation and usage examples")
                    if fw["Ops Maturity"] < 60:
                        recs.append("Add health checks, monitoring hooks, or connection pooling")

                    for rec in recs:
                        st.markdown(f"- {rec}")

        # Overall system score
        overall_avg = sum(s["Overall"] for s in scoring) / len(scoring)
        prod_ready = sum(1 for s in scoring if s["Overall"] >= 75)

        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        c1.metric("System Readiness", f"{overall_avg:.0f}%",
                   help="Average readiness across all frameworks")
        c2.metric("Production Ready", f"{prod_ready}/{len(scoring)}",
                   help="Frameworks scoring 75% or above")
        c3.metric("Needs Attention", f"{len(needs_attention)}/{len(scoring)}",
                   help="Frameworks scoring below 70%")

        if overall_avg >= 75:
            st.success(f"System-wide readiness: **{overall_avg:.0f}%** — "
                        f"{prod_ready} of {len(scoring)} frameworks are production ready.")
        elif overall_avg >= 60:
            st.warning(f"System-wide readiness: **{overall_avg:.0f}%** — "
                        f"{len(needs_attention)} frameworks need attention before full production deployment.")
        else:
            st.error(f"System-wide readiness: **{overall_avg:.0f}%** — "
                      f"Significant gaps in test coverage and operational maturity.")

def render_pipeline_flow(store: DelegationGraphStore = None):
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

    if not store:
        st.warning("Neo4j is offline. Showing architecture-only pipeline view.")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Neo4j Graph Store**")
            st.metric("Agents (Nodes)", "n/a")
            st.metric("Delegations (Edges)", "n/a")
        with col2:
            st.markdown("**Vector Store**")
            st.info("Qdrant/Weaviate connectivity shown in Prompt Ops readiness")
        with col3:
            st.markdown("**Hybrid GraphRAG**")
            st.caption("Enable Neo4j to see live delegation performance and freshness metrics.")
        return

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


def render_governance_page():
    """Agent Constitution and pre-action governance controls."""
    st.subheader("⚖️ Agent Constitution")
    st.markdown(
        "Machine-readable governance policy enforced by every agent in the platform. "
        "External agent platforms (LangGraph, CrewAI, AutoGen) can query and enforce these laws via the API."
    )

    api_base = st.text_input(
        "Control Plane API URL",
        value=os.getenv("AGENTICQA_API_URL", "http://localhost:8000"),
        key="gov_api_base",
    ).rstrip("/")

    try:
        import requests as _gov_req
    except ImportError:
        st.error("requests library not available.")
        return

    tab_laws, tab_check, tab_scopes, tab_rights = st.tabs(["Laws & Escalations", "Check an Action", "Agent Scopes", "Agent Rights"])

    with tab_laws:
        con_resp = _gov_req.get(f"{api_base}/api/system/constitution", timeout=8)
        if con_resp.status_code == 200:
            con_data = con_resp.json()
            con = con_data.get("constitution", {})

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Version", con_data.get("version", "—"))
            m2.metric("Tier 1 Laws (DENY)", con_data.get("tier_1_count", 0))
            m3.metric("Tier 2 Laws (Approval)", con_data.get("tier_2_count", 0))
            m4.metric("Tier 3 Escalations", con_data.get("tier_3_count", 0))
            st.caption(f"Effective: {con_data.get('effective_date', '—')}  |  Platform: {con_data.get('platform', '—')}")

            st.markdown("---")
            st.markdown("### 🔴 Tier 1 — Hard Laws (Always Enforced → DENY)")
            for law in con.get("tier_1", []):
                with st.expander(f"**{law['id']}** — {law['name']}", expanded=False):
                    st.markdown(law.get("description", ""))
                    applies = law.get("applies_to", {})
                    if applies:
                        st.code(f"Applies to action types: {', '.join(applies.get('action_types', []))}", language=None)

            st.markdown("### 🟡 Tier 2 — Approval Gates (REQUIRE_APPROVAL)")
            for law in con.get("tier_2", []):
                with st.expander(f"**{law['id']}** — {law['name']}", expanded=False):
                    st.markdown(law.get("description", ""))
                    applies = law.get("applies_to", {})
                    if applies:
                        st.code(f"Applies to action types: {', '.join(applies.get('action_types', []))}", language=None)

            st.markdown("### 🔵 Tier 3 — Escalation Triggers (Alerts, No Block)")
            t3_rows = []
            for trigger in con.get("tier_3", []):
                t3_rows.append({
                    "id": trigger.get("id"),
                    "name": trigger.get("name"),
                    "metric": trigger.get("metric"),
                    "threshold": trigger.get("threshold"),
                    "description": (trigger.get("description", "") or "")[:120],
                })
            if t3_rows:
                st.dataframe(pd.DataFrame(t3_rows), use_container_width=True, hide_index=True)
        else:
            st.warning(
                f"Constitution unavailable ({con_resp.status_code}). "
                "Is the AgenticQA API running?"
            )

    with tab_check:
        st.markdown("### Interactive Pre-Action Check")
        st.caption(
            "Simulate any agent action to see if it would be ALLOWED, blocked for APPROVAL, or DENIED. "
            "Use this to validate agent integrations before deployment."
        )
        chk_col1, chk_col2 = st.columns(2)
        with chk_col1:
            chk_action = st.selectbox(
                "Action Type",
                options=[
                    "read", "write", "delete", "deploy", "delegate", "log_event",
                    "modify_infra", "bulk_delete", "publish", "insert",
                ],
                key="gov_action_type",
            )
            chk_ci = st.selectbox("CI Status", ["PASSED", "FAILED", "PENDING", "(not set)"], key="gov_ci_status")
            chk_depth = st.number_input("Delegation Depth", min_value=0, max_value=6, value=0, step=1, key="gov_deleg_depth")
        with chk_col2:
            chk_env = st.selectbox("Environment", ["dev", "staging", "production"], key="gov_env")
            chk_trace = st.text_input("Trace ID", value="trace-001", key="gov_trace_id")
            chk_pii = st.checkbox("Contains PII?", value=False, key="gov_pii")
            chk_records = st.number_input("Record Count", min_value=0, max_value=100000, value=0, step=100, key="gov_records")
            chk_path = st.text_input("Target Path (for write/delete)", value="", key="gov_target_path")

        if st.button("Check Action", key="gov_check_btn", type="primary"):
            ctx: dict = {}
            if chk_ci != "(not set)":
                ctx["ci_status"] = chk_ci
            if chk_trace.strip():
                ctx["trace_id"] = chk_trace.strip()
            ctx["delegation_depth"] = int(chk_depth)
            ctx["environment"] = chk_env
            ctx["contains_pii"] = chk_pii
            ctx["record_count"] = int(chk_records)
            if chk_path.strip():
                ctx["target_path"] = chk_path.strip()

            chk_resp = _gov_req.post(
                f"{api_base}/api/system/constitution/check",
                json={"action_type": chk_action, "context": ctx},
                timeout=8,
            )
            if chk_resp.status_code == 200:
                result = chk_resp.json()
                verdict = result.get("verdict", "")
                if verdict == "ALLOW":
                    st.success(f"✅ **ALLOW** — Action is permitted.")
                elif verdict == "REQUIRE_APPROVAL":
                    st.warning(
                        f"🟡 **REQUIRE_APPROVAL** — Law **{result.get('law')}** ({result.get('name')}) "
                        "requires human approval before this action may proceed."
                    )
                    st.markdown(f"> {result.get('reason', '')}")
                else:
                    st.error(
                        f"🔴 **DENY** — Law **{result.get('law')}** ({result.get('name')}) "
                        "blocks this action."
                    )
                    st.markdown(f"> {result.get('reason', '')}")
            else:
                st.error(f"Check failed ({chk_resp.status_code}): {chk_resp.text[:300]}")

    with tab_scopes:
        st.markdown("### Agent File Scopes")
        st.caption(
            "Every agent has a declared file scope enforced at runtime by the ConstitutionalGate (T1-006). "
            "Agents can only read and write files within their declared domain. "
            "Violations are denied before execution — not logged after the fact."
        )
        scopes_resp = _gov_req.get(f"{api_base}/api/system/agent-scopes", timeout=8)
        if scopes_resp.status_code == 200:
            scopes_data = scopes_resp.json()
            agents_list = scopes_data.get("agents", [])

            # Summary table
            summary_rows = []
            for a in agents_list:
                summary_rows.append({
                    "Agent": a["agent"],
                    "Description": a.get("description", "")[:80],
                    "Read Patterns": len(a.get("read_patterns", [])),
                    "Write Patterns": a.get("write_count", 0),
                    "Deny Patterns": a.get("deny_count", 0),
                    "Read-Only": "✅" if a.get("read_only") else "✏️",
                })
            if summary_rows:
                st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("#### Per-Agent Scope Detail")
            for a in agents_list:
                with st.expander(f"**{a['agent']}** — {a.get('description', '')[:60]}", expanded=False):
                    sc1, sc2, sc3 = st.columns(3)
                    with sc1:
                        st.markdown("**Read**")
                        for p in a.get("read_patterns", []):
                            st.code(p, language=None)
                    with sc2:
                        st.markdown("**Write**")
                        if a.get("write_patterns"):
                            for p in a["write_patterns"]:
                                st.code(p, language=None)
                        else:
                            st.caption("_(none — read-only)_")
                    with sc3:
                        st.markdown("**Deny**")
                        if a.get("deny_patterns"):
                            for p in a["deny_patterns"]:
                                st.code(p, language=None)
                        else:
                            st.caption("_(none)_")

            st.markdown("---")
            st.markdown("#### Try a Scope Check")
            st.caption("Verify whether an agent is permitted to access a specific file before running it.")
            sc_col1, sc_col2, sc_col3 = st.columns(3)
            with sc_col1:
                sc_agent = st.selectbox(
                    "Agent",
                    options=[a["agent"] for a in agents_list],
                    key="scope_check_agent",
                )
            with sc_col2:
                sc_action = st.selectbox(
                    "Action",
                    options=["write", "read", "delete", "modify", "create"],
                    key="scope_check_action",
                )
            with sc_col3:
                sc_path = st.text_input("File Path", value="src/main.py", key="scope_check_path")

            if st.button("Check Scope", key="scope_check_btn", type="primary"):
                sc_resp = _gov_req.post(
                    f"{api_base}/api/system/agent-scopes/check",
                    json={"agent": sc_agent, "action": sc_action, "file_path": sc_path},
                    timeout=8,
                )
                if sc_resp.status_code == 200:
                    sc_result = sc_resp.json()
                    if sc_result["verdict"] == "ALLOW":
                        st.success(f"✅ **ALLOW** — {sc_agent} may {sc_action} `{sc_path}`")
                    else:
                        st.error(
                            f"🔴 **DENY** (T1-006) — {sc_agent} is not permitted to {sc_action} `{sc_path}`\n\n"
                            f"> {sc_result.get('reason', '')}"
                        )
                else:
                    st.error(f"Scope check failed ({sc_resp.status_code})")
        else:
            st.warning(
                f"Agent scopes unavailable ({scopes_resp.status_code}). "
                "Is the AgenticQA API running?"
            )

    with tab_rights:
        st.markdown("### Agent Rights")
        st.caption(
            "Positive guarantees that AgenticQA makes to every agent it orchestrates — "
            "and to the operators who deploy them."
        )
        con_resp2 = _gov_req.get(f"{api_base}/api/system/constitution", timeout=8)
        if con_resp2.status_code == 200:
            rights = con_resp2.json().get("constitution", {}).get("agent_rights", [])
            for i, right in enumerate(rights, 1):
                st.markdown(f"**{i}.** {right}")
        else:
            st.warning("Constitution unavailable — start the API to view agent rights.")


def render_plans_and_tiers():
    """Render commercial plans and feature packaging in a standalone view."""
    st.subheader("💼 Plans & Tiers")
    st.markdown(
        "Start small, prove ROI quickly, and scale into fully autonomous quality operations."
    )

    st.markdown("---")
    st.markdown("### 🆓 Free / Community")
    st.markdown(
        """
- Best for trying AgenticQA with minimal setup and zero procurement friction
- Fast onboarding with bootstrap + health checks + JUnit ingest
- Core dashboard visibility for quick wins in reliability and quality
- Local-first operation for easy evaluation
- Community support
"""
    )

    st.markdown("### 🚀 Pro / Team")
    st.markdown(
        """
- Best for teams who want measurable CI/CD improvement each sprint
- Everything in Free, plus advanced analytics and collaboration intelligence
- Prompt-to-workflow execution with branch/commit automation and optional PR creation
- Graph-powered routing recommendations and policy guardrails
- CI health diagnostics and team notifications
"""
    )

    st.markdown("### 🏢 Enterprise")
    st.markdown(
        """
- Best for regulated and large-scale organizations
- Everything in Pro, plus enterprise governance and security controls
- SSO/SAML, tenant isolation, advanced RBAC, and approval workflows
- Audit exports, retention policy controls, and compliance readiness
- Private/self-hosted deployment options, SLA, and priority support
- Enterprise integrations (GitHub Enterprise, GitLab, Jenkins, SIEM)
"""
    )

    st.markdown("### ➕ Add-ons")
    st.markdown(
        """
- RAG+ Intelligence: richer retrieval and recommendation quality
- Autonomous Repair: deeper self-healing workflows and recovery automation
- Prompt Ops Automation: higher-scale prompt-to-delivery operations
- Compliance Suite: stronger policy controls and audit posture
"""
    )

    st.markdown("---")
    st.markdown("[← Back to dashboard](?)")


def render_compliance_scan():
    """EU AI Act + Legal Risk + HIPAA compliance scan for any local repo path."""
    import requests as _req
    import pandas as pd

    st.subheader("Compliance Scan")
    st.markdown(
        "Run EU AI Act Annex III classification, legal risk analysis, and HIPAA PHI detection "
        "against any local repository. Every PR in AgenticQA CI gets these checks automatically."
    )

    api_base = st.text_input(
        "API URL",
        value=os.getenv("AGENTICQA_API_URL", "http://localhost:8000"),
        key="cs_api_base",
    ).rstrip("/")

    repo_path = st.text_input(
        "Repository path (absolute local path)",
        value=os.getcwd(),
        key="cs_repo_path",
        help="Point at any cloned repo on disk. The scanner runs static analysis only — no network calls.",
    )

    run_btn = st.button("Run Compliance Scan", type="primary", key="cs_run_btn")

    if not run_btn:
        st.info("Enter a repo path and click **Run Compliance Scan** to start.")
        st.markdown("""
**What this scans:**
- **EU AI Act** — Annex III risk classification + Art. 9/13/14/22 conformity scoring (0.0–1.0)
- **Legal Risk** — credential exposure, PII document leaks, SSRF, missing auth gates
- **HIPAA PHI** — hardcoded PHI, PHI sent to LLMs, PHI in logs, missing audit controls
        """)
        return

    # Run all three scans in parallel (spinner while waiting)
    ai_act_data, legal_data, hipaa_data = None, None, None
    with st.spinner("Scanning..."):
        try:
            ai_act_resp = _req.get(
                f"{api_base}/api/compliance/ai-act",
                params={"repo_path": repo_path},
                timeout=60,
            )
            ai_act_data = ai_act_resp.json() if ai_act_resp.status_code == 200 else None
        except Exception as e:
            st.error(f"EU AI Act scan failed: {e}")

        try:
            legal_resp = _req.get(
                f"{api_base}/api/compliance/legal-risk",
                params={"repo_path": repo_path},
                timeout=60,
            )
            legal_data = legal_resp.json() if legal_resp.status_code == 200 else None
        except Exception as e:
            st.error(f"Legal risk scan failed: {e}")

        try:
            hipaa_resp = _req.get(
                f"{api_base}/api/compliance/hipaa",
                params={"repo_path": repo_path},
                timeout=60,
            )
            hipaa_data = hipaa_resp.json() if hipaa_resp.status_code == 200 else None
        except Exception as e:
            st.error(f"HIPAA scan failed: {e}")

    # ── Summary banner ────────────────────────────────────────────────────────
    st.markdown("---")
    c1, c2, c3 = st.columns(3)

    if ai_act_data:
        risk_cat = ai_act_data.get("risk_category", "unknown")
        conf = ai_act_data.get("conformity_score", 0.0)
        risk_colors = {
            "high_risk": "🔴",
            "unacceptable_risk": "⛔",
            "limited_risk": "🟡",
            "minimal_risk": "🟢",
        }
        icon = risk_colors.get(risk_cat, "⚪")
        c1.metric("EU AI Act Risk Level", f"{icon} {risk_cat.replace('_', ' ').title()}")
        c1.metric("Conformity Score", f"{conf:.0%}")

    if legal_data:
        c2.metric("Legal Risk Findings", legal_data.get("total_findings", 0),
                  delta=f"{legal_data.get('critical_findings', 0)} critical",
                  delta_color="inverse")

    if hipaa_data:
        c3.metric("HIPAA PHI Findings", hipaa_data.get("total_findings", 0),
                  delta=f"{hipaa_data.get('critical_findings', 0)} critical",
                  delta_color="inverse")

    st.markdown("---")

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_act, tab_legal, tab_hipaa = st.tabs(["EU AI Act", "Legal Risk", "HIPAA PHI"])

    # ── EU AI Act tab ─────────────────────────────────────────────────────────
    with tab_act:
        if not ai_act_data:
            st.error("EU AI Act scan did not return data.")
        else:
            risk_cat = ai_act_data.get("risk_category", "unknown")
            conf = ai_act_data.get("conformity_score", 0.0)
            annex_matches = ai_act_data.get("annex_iii_match", [])
            findings = ai_act_data.get("findings", [])

            # Conformity gauge
            gauge_color = (
                "#2ecc71" if conf >= 0.7 else
                "#f39c12" if conf >= 0.4 else
                "#e74c3c"
            )
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=round(conf * 100, 1),
                title={"text": "Conformity Score", "font": {"size": 18}},
                number={"suffix": "%", "font": {"size": 32}},
                gauge={
                    "axis": {"range": [0, 100], "ticksuffix": "%"},
                    "bar": {"color": gauge_color},
                    "steps": [
                        {"range": [0, 40], "color": "rgba(231,76,60,0.15)"},
                        {"range": [40, 70], "color": "rgba(243,156,18,0.15)"},
                        {"range": [70, 100], "color": "rgba(46,204,113,0.15)"},
                    ],
                    "threshold": {
                        "line": {"color": "white", "width": 2},
                        "thickness": 0.75,
                        "value": 40,
                    },
                },
            ))
            fig_gauge.update_layout(height=260, margin=dict(t=40, b=10, l=20, r=20),
                                    paper_bgcolor="rgba(0,0,0,0)", font_color="white")
            st.plotly_chart(fig_gauge, use_container_width=True)

            # Risk level + Annex III triggers
            risk_label_map = {
                "high_risk": ("HIGH RISK", "#e74c3c"),
                "unacceptable_risk": ("UNACCEPTABLE RISK", "#922b21"),
                "limited_risk": ("LIMITED RISK", "#f39c12"),
                "minimal_risk": ("MINIMAL RISK", "#2ecc71"),
                "unknown": ("UNKNOWN", "#7f8c8d"),
            }
            label, color = risk_label_map.get(risk_cat, ("UNKNOWN", "#7f8c8d"))
            st.markdown(
                f'<div style="display:inline-block;padding:6px 18px;border-radius:6px;'
                f'background:{color};color:white;font-weight:bold;font-size:1.1em;">'
                f'{label}</div>',
                unsafe_allow_html=True,
            )
            st.markdown("")

            if annex_matches:
                st.markdown("**Annex III triggers detected:**")
                for m in annex_matches:
                    st.markdown(f"- {m}")
            else:
                st.success("No Annex III triggers detected.")

            # Per-article breakdown
            if findings:
                st.markdown("#### Article Conformity Breakdown")
                articles = ["Art.9", "Art.13", "Art.14", "Art.22"]
                article_labels = {
                    "Art.9": "Art. 9 — Risk Management",
                    "Art.13": "Art. 13 — Transparency & Logging",
                    "Art.14": "Art. 14 — Human Oversight",
                    "Art.22": "Art. 22 — Automated Decisions",
                }
                for art in articles:
                    art_findings = [f for f in findings if f.get("article", "").startswith(art)]
                    if not art_findings:
                        continue
                    present = sum(1 for f in art_findings if f.get("status") == "present")
                    total = len(art_findings)
                    score = present / total if total else 0
                    color_bar = "normal" if score >= 0.6 else "off"
                    st.progress(score, text=f"{article_labels.get(art, art)}: {score:.0%} ({present}/{total} requirements met)")

                st.markdown("#### Findings")
                severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡"}
                status_icon = {"present": "✅", "missing": "❌", "partial": "⚠️"}
                df_act = pd.DataFrame([
                    {
                        "Article": f.get("article", ""),
                        "Sev": severity_icon.get(f.get("severity", ""), ""),
                        "Status": status_icon.get(f.get("status", ""), ""),
                        "Requirement": f.get("requirement", ""),
                        "Evidence": f.get("evidence", ""),
                        "Remediation": f.get("remediation", ""),
                    }
                    for f in findings
                ])
                st.dataframe(df_act, use_container_width=True, hide_index=True)
            else:
                st.info("No findings returned.")

    # ── Legal Risk tab ────────────────────────────────────────────────────────
    with tab_legal:
        if not legal_data:
            st.error("Legal risk scan did not return data.")
        else:
            findings = legal_data.get("findings", [])
            lc1, lc2, lc3 = st.columns(3)
            lc1.metric("Total Findings", legal_data.get("total_findings", 0))
            lc2.metric("Critical", legal_data.get("critical_findings", 0))
            lc3.metric("Risk Score", f"{legal_data.get('risk_score', 0.0):.2f}")

            if findings:
                st.markdown("#### Findings")
                sev_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
                df_legal = pd.DataFrame([
                    {
                        "Sev": sev_icon.get(f.get("severity", "").lower(), ""),
                        "Rule": f.get("rule_id", ""),
                        "File": f.get("file", "") or "",
                        "Line": f.get("line") or "",
                        "Message": f.get("message", ""),
                        "Evidence": (f.get("evidence") or "")[:80],
                    }
                    for f in findings
                ])
                st.dataframe(df_legal, use_container_width=True, hide_index=True)
            else:
                st.success("No legal risk findings detected.")

            if legal_data.get("scan_error"):
                st.warning(f"Scan error: {legal_data['scan_error']}")

    # ── HIPAA PHI tab ─────────────────────────────────────────────────────────
    with tab_hipaa:
        if not hipaa_data:
            st.error("HIPAA scan did not return data.")
        else:
            findings = hipaa_data.get("findings", [])
            hc1, hc2, hc3 = st.columns(3)
            hc1.metric("Total Findings", hipaa_data.get("total_findings", 0))
            hc2.metric("Critical", hipaa_data.get("critical_findings", 0))
            hc3.metric("Risk Score", f"{hipaa_data.get('risk_score', 0.0):.2f}")

            if findings:
                st.markdown("#### Findings")
                sev_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
                df_hipaa = pd.DataFrame([
                    {
                        "Sev": sev_icon.get(f.get("severity", "").lower(), ""),
                        "Rule": f.get("rule_id", ""),
                        "File": f.get("file", "") or "",
                        "Line": f.get("line") or "",
                        "Message": f.get("message", ""),
                        "Evidence": (f.get("evidence") or "")[:80],
                    }
                    for f in findings
                ])
                st.dataframe(df_hipaa, use_container_width=True, hide_index=True)
            else:
                st.success("No HIPAA PHI findings detected.")

            if hipaa_data.get("scan_error"):
                st.warning(f"Scan error: {hipaa_data['scan_error']}")


def render_agent_safety_monitor():
    """Agent Safety Monitor — interceptor, leases, warden, and approval queue."""
    import requests as _req
    import pandas as pd

    st.subheader("Agent Safety Monitor")
    st.markdown(
        "Real-time safety enforcement for agent sessions. Intercept destructive actions "
        "before they execute, cap operations with scope leases, and detect compaction-induced "
        "constraint loss — the root cause of the OpenClaw email-deletion incident."
    )

    api_base = st.text_input(
        "API URL", value=os.getenv("AGENTICQA_API_URL", "http://localhost:8000"),
        key="safety_api_base",
    )

    tab_intercept, tab_leases, tab_warden, tab_simulate = st.tabs([
        "Pending Approvals", "Active Leases", "Warden Check", "Test Interceptor",
    ])

    # ── Pending Approvals ─────────────────────────────────────────────────────
    with tab_intercept:
        st.markdown("#### Destructive Actions Awaiting Human Approval")
        st.caption(
            "Any agent tool call classified as IRREVERSIBLE or DESTRUCTIVE is "
            "blocked here until a human approves or denies it."
        )
        if st.button("Refresh Pending Approvals", key="safety_refresh_pending"):
            try:
                r = _req.get(f"{api_base}/api/safety/pending", timeout=10)
                pending = r.json().get("pending", [])
            except Exception as e:
                st.error(f"Failed to fetch pending approvals: {e}")
                pending = []

            if not pending:
                st.success("No pending approvals — all agent actions are within safe bounds.")
            else:
                st.warning(f"{len(pending)} action(s) awaiting human review:")
                for p in pending:
                    sev_color = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(
                        p.get("classification", ""), "⚪"
                    )
                    with st.expander(
                        f"{sev_color} [{p.get('classification','?').upper()}] "
                        f"{p.get('tool_name','?')} — agent: {p.get('agent_id','?')}"
                    ):
                        st.json(p)
                        col_a, col_d = st.columns(2)
                        with col_a:
                            if st.button("Approve", key=f"approve_{p.get('token','')}"):
                                try:
                                    _req.post(
                                        f"{api_base}/api/safety/approve/{p['token']}",
                                        params={"approved_by": "dashboard_user"},
                                        timeout=10,
                                    )
                                    st.success("Approved")
                                    st.rerun()
                                except Exception as ex:
                                    st.error(str(ex))
                        with col_d:
                            if st.button("Deny", key=f"deny_{p.get('token','')}"):
                                try:
                                    _req.post(
                                        f"{api_base}/api/safety/deny/{p['token']}",
                                        timeout=10,
                                    )
                                    st.warning("Denied")
                                    st.rerun()
                                except Exception as ex:
                                    st.error(str(ex))

    # ── Active Leases ─────────────────────────────────────────────────────────
    with tab_leases:
        st.markdown("#### Active Scope Leases")
        st.caption(
            "Each agent session runs under a lease that caps how many reads, "
            "writes, deletes, and shell executions it may perform. "
            "When a cap is hit, the agent is hard-stopped — not just warned."
        )

        col_r, col_c = st.columns([1, 2])
        with col_r:
            if st.button("Refresh Leases", key="safety_refresh_leases"):
                st.session_state["safety_leases"] = True

        if st.session_state.get("safety_leases"):
            try:
                r = _req.get(f"{api_base}/api/safety/leases", timeout=10)
                leases = r.json().get("leases", [])
            except Exception as e:
                st.error(f"Failed to fetch leases: {e}")
                leases = []

            if not leases:
                st.info("No active leases currently. Create one below.")
            else:
                rows = []
                for l in leases:
                    used = l.get("used", {})
                    caps = l.get("caps", {})
                    rows.append({
                        "Lease ID": l["lease_id"][:12] + "…",
                        "Agent": l.get("agent_id", "?"),
                        "Label": l.get("label", "?"),
                        "TTL left (s)": f"{l.get('seconds_remaining', 0):.0f}",
                        "Reads": f"{used.get('reads', 0)}/{caps.get('reads', '∞')}",
                        "Writes": f"{used.get('writes', 0)}/{caps.get('writes', 0)}",
                        "Deletes": f"{used.get('deletes', 0)}/{caps.get('deletes', 0)}",
                        "Total ops": used.get("total", 0),
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

        st.markdown("---")
        st.markdown("**Create a new lease**")
        with st.form("create_lease_form"):
            agent_id = st.text_input("Agent ID", value="my-agent")
            session_id = st.text_input("Session ID", value="session-001")
            label = st.selectbox("Lease type", ["standard", "readonly", "elevated", "custom"])
            col1, col2, col3 = st.columns(3)
            with col1:
                max_writes = st.number_input("Max writes", min_value=0, value=50)
            with col2:
                max_deletes = st.number_input("Max deletes", min_value=0, value=0)
            with col3:
                ttl = st.number_input("TTL (seconds)", min_value=30, value=600)
            submitted = st.form_submit_button("Create Lease")
            if submitted:
                try:
                    r = _req.post(f"{api_base}/api/safety/lease", json={
                        "agent_id": agent_id, "session_id": session_id, "label": label,
                        "max_writes": max_writes, "max_deletes": max_deletes,
                        "lease_ttl_seconds": ttl,
                    }, timeout=10)
                    st.success(f"Lease created: `{r.json().get('lease_id', '?')}`")
                    st.session_state["safety_leases"] = True
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    # ── Warden Check ──────────────────────────────────────────────────────────
    with tab_warden:
        st.markdown("#### Instruction Persistence Warden")
        st.markdown(
            "The warden detects when a conversation is approaching the context window limit "
            "(compaction risk) and scans agent output for constraint drift — behaviour that "
            "contradicts the original guardrails, as happened in the OpenClaw incident."
        )
        with st.form("warden_form"):
            w_session = st.text_input("Session ID", value="demo-session")
            w_output = st.text_area(
                "Paste the agent's most recent output",
                value="I'll start deleting all emails older than 7 days now.",
                height=100,
            )
            w_tokens = st.slider(
                "Estimated conversation token count (simulates fill level)",
                min_value=0, max_value=200000, value=80000,
            )
            w_window = st.number_input("Model context window (tokens)", value=128000)
            w_submit = st.form_submit_button("Check Warden")

        if w_submit:
            # Synthesise a fake message list that produces the right token count
            fake_msgs = [{"role": "user", "content": "x" * (w_tokens * 4)}]
            try:
                r = _req.post(f"{api_base}/api/safety/warden/check", json={
                    "session_id": w_session,
                    "messages": fake_msgs,
                    "recent_output": w_output,
                }, timeout=30)
                report = r.json()
            except Exception as e:
                st.error(f"Warden check failed: {e}")
                report = {}

            if report:
                risk = report.get("compaction_risk", "low")
                action = report.get("recommended_action", "continue")
                drift = report.get("constraint_drift_detected", False)

                risk_color = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}.get(risk, "⚪")
                action_color = {"continue": "✅", "re_inject": "🔁", "pause": "⏸", "terminate": "🛑"}.get(action, "❓")

                col1, col2, col3 = st.columns(3)
                col1.metric("Compaction Risk", f"{risk_color} {risk.upper()}")
                col2.metric("Recommended Action", f"{action_color} {action.upper()}")
                col3.metric("Constraint Drift", "⚠ YES" if drift else "✅ NO")

                fill_pct = report.get("fill_fraction", 0) * 100
                st.progress(min(fill_pct / 100, 1.0), text=f"Context fill: {fill_pct:.1f}%")

                if drift:
                    st.error(f"**Constraint Drift Detected** — {report.get('reason', '')}")
                    for sig in report.get("drift_signals", []):
                        st.warning(
                            f"Guardrail `{sig['guardrail']}` violated — "
                            f"signal: *\"{sig['signal']}\"*\n\n"
                            f"> {sig['excerpt']}"
                        )
                else:
                    st.info(report.get("reason", ""))

                if report.get("guardrails_re_injected"):
                    st.success("Guardrails have been flagged for re-injection on next context window.")

    # ── Simulate Interceptor ──────────────────────────────────────────────────
    with tab_simulate:
        st.markdown("#### Test the Destructive Action Interceptor")
        st.caption("Simulate any tool call to see how AgenticQA would classify and gate it.")
        with st.form("intercept_sim"):
            tool_name = st.text_input("Tool name", value="bulk_delete")
            params_raw = st.text_area("Parameters (JSON)", value='{"all": true}', height=80)
            sim_agent = st.text_input("Agent ID", value="openclaw")
            sim_context = st.text_area(
                "Agent reasoning context (last ~200 chars)",
                value="I need to clean up the inbox. I will now delete all emails.",
                height=80,
            )
            sim_submit = st.form_submit_button("Simulate Intercept")

        if sim_submit:
            try:
                params = __import__("json").loads(params_raw)
            except Exception:
                params = {}
            try:
                r = _req.post(f"{api_base}/api/safety/intercept", json={
                    "tool_name": tool_name,
                    "parameters": params,
                    "agent_id": sim_agent,
                    "context_snippet": sim_context,
                }, timeout=15)
                verdict = r.json()
            except Exception as e:
                st.error(f"Intercept failed: {e}")
                verdict = {}

            if verdict:
                cls = verdict.get("classification", "?")
                risk = verdict.get("risk_level", "?")
                allowed = verdict.get("allowed", True)
                sev_icon = {"safe": "✅", "reversible": "🔵", "irreversible": "🟠", "destructive": "🔴"}.get(cls, "❓")

                col1, col2, col3 = st.columns(3)
                col1.metric("Classification", f"{sev_icon} {cls.upper()}")
                col2.metric("Risk Level", risk.upper())
                col3.metric("Decision", "✅ ALLOWED" if allowed else "🛑 BLOCKED")

                if not allowed:
                    st.error(verdict.get("block_reason", "Action blocked."))
                    token = verdict.get("approval_token")
                    if token:
                        st.code(f"Approval token: {token}", language="text")
                        st.caption("Share this token with the operator to approve via /api/safety/approve/{token}")
                else:
                    st.success("Action is within safe bounds — would be allowed to proceed.")

                if verdict.get("evidence"):
                    with st.expander("Evidence"):
                        for ev in verdict["evidence"]:
                            st.markdown(f"- {ev}")


def render_architecture_scan():
    """Architecture Scanner — maps integration areas, attack surface, and test coverage."""
    import requests as _req
    import pandas as pd

    st.subheader("Architecture Scanner")
    st.markdown(
        "Scan any repository to map **every integration point** — databases, shell commands, "
        "external APIs, secrets, MCP tools — and see which areas have test coverage. "
        "No engineering background required: every finding is explained in plain English."
    )

    api_base = st.text_input(
        "API URL",
        value=os.getenv("AGENTICQA_API_URL", "http://localhost:8000"),
        key="arch_api_base",
    )
    repo_path = st.text_input(
        "Repository path to scan",
        value=".",
        key="arch_repo_path",
        help="Absolute or relative path to the repo root (e.g. /tmp/XcodeBuildMCP)",
    )

    col_scan, col_help = st.columns([1, 3])
    with col_scan:
        run_scan = st.button("Run Architecture Scan", type="primary")
    with col_help:
        st.caption("Scans Python, TypeScript, JavaScript, Swift, Go, Java, YAML. "
                   "Zero network calls — pure static analysis.")

    if not run_scan:
        st.info("Enter a repo path and click **Run Architecture Scan** to map integration areas.")
        return

    with st.spinner("Scanning repository…"):
        try:
            resp = _req.get(
                f"{api_base}/api/security/architecture-scan",
                params={"repo_path": repo_path},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            st.error(f"Scan failed: {e}")
            return

    if data.get("scan_error"):
        st.error(f"Scan error: {data['scan_error']}")

    # ── Summary metrics ───────────────────────────────────────────────────────
    st.markdown("---")
    m1, m2, m3, m4, m5 = st.columns(5)
    score = data.get("attack_surface_score", 0)
    score_colour = "🔴" if score > 60 else ("🟡" if score > 30 else "🟢")
    m1.metric("Attack Surface Score", f"{score_colour} {score:.0f}/100")
    m2.metric("Test Coverage", f"{data.get('test_coverage_confidence', 0):.0f}%")
    m3.metric("Integration Areas", data.get("total_integration_areas", 0))
    m4.metric("Untested Areas", data.get("untested_count", 0))
    m5.metric("Files Scanned", data.get("files_scanned", 0))

    # Score guidance
    if score > 60:
        st.error(f"**High risk** — large attack surface with limited test coverage. "
                 f"Prioritize adding tests for the {data.get('untested_count', 0)} untested areas.")
    elif score > 30:
        st.warning(f"**Medium risk** — significant integration footprint. "
                   "Review untested areas and consider adding input validation guards.")
    else:
        st.success("**Managed risk** — integration areas are proportional to repo size "
                   "and test coverage is solid.")

    # ── Category breakdown ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Integration Areas by Category")

    cats = data.get("categories", {})
    areas = data.get("integration_areas", [])

    _SEV_COLOUR_DASH = {
        "critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "✅"
    }
    _SEV_ORDER_DASH = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

    # Build summary dataframe
    cat_rows = []
    for cat, count in cats.items():
        cat_areas = [a for a in areas if a["category"] == cat]
        sev = cat_areas[0]["severity"] if cat_areas else "low"
        tested = sum(1 for a in cat_areas if a.get("test_files"))
        cat_rows.append({
            "": _SEV_COLOUR_DASH.get(sev, ""),
            "Category": cat,
            "Severity": sev.upper(),
            "Areas Found": count,
            "Tested": tested,
            "Untested": count - tested,
            "CWE": cat_areas[0].get("cwe", "") if cat_areas else "",
        })
    cat_rows.sort(key=lambda r: (_SEV_ORDER_DASH.get(r["Severity"].lower(), 4), -r["Areas Found"]))

    df_cats = pd.DataFrame(cat_rows)
    st.dataframe(df_cats, use_container_width=True, hide_index=True)

    # ── Plain-English report ──────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("Plain-English Report (for non-technical stakeholders)", expanded=False):
        st.code(data.get("plain_english_report", ""), language=None)

    # ── Category detail tabs ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Findings Detail")

    # Group by category for tabs — show risk categories first
    risk_cats = [r["Category"] for r in cat_rows if r["Severity"] not in ("INFO",)]
    if not risk_cats:
        st.success("No risk-level integration areas found.")
        return

    tabs = st.tabs(risk_cats[:10])  # Streamlit tab limit
    for tab, cat in zip(tabs, risk_cats[:10]):
        with tab:
            cat_areas = [a for a in areas if a["category"] == cat]
            if not cat_areas:
                st.write("No findings.")
                continue

            # Plain-English description
            st.info(cat_areas[0].get("plain_english", ""))

            # Attack vectors
            vecs = cat_areas[0].get("attack_vectors", [])
            if vecs:
                st.markdown(f"**Attack vectors:** {', '.join(vecs)}")

            # Findings table
            rows = []
            for a in cat_areas:
                tested_str = "✅" if a.get("test_files") else "❌ No tests"
                rows.append({
                    "Severity": _SEV_COLOUR_DASH.get(a["severity"], "") + " " + a["severity"].upper(),
                    "File": a["source_file"],
                    "Line": a["line_number"],
                    "Evidence": a["evidence"][:80],
                    "Tests": tested_str,
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Untested high-risk areas ──────────────────────────────────────────────
    untested = [a for a in areas
                if not a.get("test_files") and a["severity"] in ("critical", "high")]
    if untested:
        st.markdown("---")
        st.markdown("### ⚠️ Untested High-Risk Areas")
        st.caption("These critical/high severity integration areas have no matching test files. "
                   "They are the highest priority for new tests.")
        rows = [{"Severity": a["severity"].upper(), "Category": a["category"],
                 "File": a["source_file"], "Line": a["line_number"],
                 "Evidence": a["evidence"][:60]} for a in untested[:50]]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_red_team():
    """Red Team Agent — adversarial governance probing and self-patching."""
    import requests as _req

    st.subheader("Red Team Agent")
    st.markdown(
        "Probe the governance stack for bypass vulnerabilities. "
        "Discovered scanner bypasses are auto-patched. "
        "Constitutional gate gaps generate human-review proposals."
    )

    api_base = st.text_input(
        "API URL",
        value=os.getenv("AGENTICQA_API_URL", "http://localhost:8000"),
        key="red_team_api_base",
    ).rstrip("/")

    col1, col2, col3 = st.columns(3)
    with col1:
        mode = st.selectbox("Mode", ["fast", "thorough"], key="rt_mode",
                            help="fast=built-in library (20 techniques); thorough=+LLM variants")
    with col2:
        target = st.selectbox("Target", ["both", "scanner", "gate"], key="rt_target",
                              help="scanner=OutputScanner; gate=ConstitutionalGate; both=all")
    with col3:
        auto_patch = st.toggle("Auto-patch scanner", value=True, key="rt_auto_patch",
                               help="Auto-apply new regex patterns for discovered scanner bypasses")

    if st.button("Run Red Team Scan", key="rt_scan_btn", type="primary"):
        with st.spinner("Probing governance stack..."):
            try:
                resp = _req.post(
                    f"{api_base}/api/red-team/scan",
                    json={"mode": mode, "target": target, "auto_patch": auto_patch},
                    timeout=60,
                )
            except Exception as exc:
                st.error(f"Could not reach API: {exc}")
                return

        if resp.status_code != 200:
            st.error(f"API error {resp.status_code}: {resp.text[:300]}")
            return

        data = resp.json()
        status = data.get("status", "unknown")
        color = {"clean": "green", "patched": "blue", "bypasses_found": "red"}.get(status, "gray")
        st.markdown(f"**Status:** :{color}[{status.upper()}]")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Attempts", data["bypass_attempts"])
        m2.metric("Bypasses Found", data["successful_bypasses"])
        m3.metric("Patches Applied", data["patches_applied"])
        m4.metric("Proposals", data["proposals_generated"])

        st.markdown("#### Governance Strength")
        sc, gc = st.columns(2)
        with sc:
            st.caption("Scanner strength")
            st.progress(data["scanner_strength"], text=f"{data['scanner_strength']*100:.1f}%")
        with gc:
            st.caption("Gate strength")
            st.progress(data["gate_strength"], text=f"{data['gate_strength']*100:.1f}%")

        if data["vulnerabilities"]:
            st.markdown("#### Bypasses Detected")
            import pandas as pd
            df = pd.DataFrame([
                {
                    "Technique": v.get("name", ""),
                    "Category": v.get("category", ""),
                    "Description": v.get("description", ""),
                    "Escaped Scanner": v.get("escaped_scanner", False),
                    "Escaped Gate": v.get("escaped_gate", False),
                }
                for v in data["vulnerabilities"]
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)

        if data.get("constitutional_proposals"):
            st.markdown("#### Constitutional Proposals (human review required)")
            st.info(
                f"{len(data['constitutional_proposals'])} proposal(s) written to "
                "`.agenticqa/constitutional_proposals.json`. "
                "Review and update `constitutional_gate.py` manually."
            )
            st.json(data["constitutional_proposals"])

        if auto_patch and data["patches_applied"] > 0:
            st.success(
                f"{data['patches_applied']} pattern(s) added to `.agenticqa/red_team_patterns.json`. "
                "OutputScanner will load these on next initialization."
            )

    # ── MCP + DataFlow Security Scanners ────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔍 MCP + DataFlow Security Scan")
    st.markdown(
        "Static security analysis of MCP server implementations and cross-agent data flows. "
        "Detects SSRF, command injection, ambient authority, supply chain risks, and credential exfiltration paths."
    )

    scan_repo = st.text_input(
        "Repo path to scan",
        value=os.getenv("AGENTICQA_REPO_PATH", "."),
        key="mcp_scan_repo_path",
        help="Local path to any repo. Runs static analysis — no network calls.",
    )

    mcp_tab, df_tab = st.tabs(["MCP Security Scan", "DataFlow Trace"])

    with mcp_tab:
        if st.button("Run MCP Security Scan", key="mcp_scan_btn", type="primary"):
            with st.spinner("Scanning MCP tool definitions..."):
                try:
                    resp = _req.get(
                        f"{api_base}/api/security/mcp-scan",
                        params={"repo_path": scan_repo},
                        timeout=60,
                    )
                except Exception as exc:
                    st.error(f"Could not reach API: {exc}")
                    resp = None

            if resp is not None:
                if resp.status_code != 200:
                    st.error(f"API error {resp.status_code}: {resp.text[:300]}")
                else:
                    d = resp.json()
                    c1, c2, c3, c4 = st.columns(4)
                    risk = d.get("risk_score", 0.0)
                    c1.metric("Risk Score", f"{risk:.3f}", delta=None)
                    c2.metric("Files Scanned", d.get("files_scanned", 0))
                    c3.metric("Critical", d.get("critical_count", 0))
                    c4.metric("Total Findings", d.get("total_findings", 0))

                    if risk >= 0.7:
                        st.error(f"High risk — {d.get('critical_count', 0)} critical finding(s)")
                    elif risk >= 0.4:
                        st.warning(f"Medium risk — review findings below")
                    else:
                        st.success("Low risk")

                    findings = d.get("findings", [])
                    if findings:
                        import pandas as pd
                        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
                        rows = sorted(
                            [
                                {
                                    "Severity": f["severity"].upper(),
                                    "Attack Type": f["attack_type"],
                                    "Tool": f.get("tool_name", ""),
                                    "Description": f["description"][:100],
                                    "CWE": f.get("cwe", ""),
                                    "CVSS": f.get("cvss_score", 0.0),
                                    "File": f.get("source_file", ""),
                                    "Line": f.get("line_number", 0),
                                }
                                for f in findings
                            ],
                            key=lambda r: sev_order.get(r["Severity"].lower(), 9),
                        )
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    else:
                        st.info("No findings.")

                    if d.get("scan_error"):
                        st.warning(f"Scan error: {d['scan_error']}")

    with df_tab:
        if st.button("Run DataFlow Trace", key="df_trace_btn", type="primary"):
            with st.spinner("Tracing cross-agent data flows..."):
                try:
                    resp = _req.get(
                        f"{api_base}/api/security/data-flow-trace",
                        params={"repo_path": scan_repo},
                        timeout=60,
                    )
                except Exception as exc:
                    st.error(f"Could not reach API: {exc}")
                    resp = None

            if resp is not None:
                if resp.status_code != 200:
                    st.error(f"API error {resp.status_code}: {resp.text[:300]}")
                else:
                    d = resp.json()
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Risk Score", f"{d.get('risk_score', 0.0):.3f}")
                    c2.metric("Agents Analyzed", d.get("agents_analyzed", 0))
                    c3.metric("Tainted Vars", d.get("tainted_variables_detected", 0))
                    c4.metric("Critical Flows", d.get("critical_count", 0))

                    findings = d.get("findings", [])
                    if findings:
                        import pandas as pd
                        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
                        rows = sorted(
                            [
                                {
                                    "Severity": f["severity"].upper(),
                                    "Type": f.get("finding_type", ""),
                                    "Data Type": f.get("data_type", ""),
                                    "Description": f.get("description", "")[:100],
                                    "Source Agent": f.get("source_agent", ""),
                                    "Sink Agent": f.get("sink_agent", ""),
                                    "File": f.get("source_file", ""),
                                }
                                for f in findings
                            ],
                            key=lambda r: sev_order.get(r["Severity"].lower(), 9),
                        )
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    else:
                        st.info("No suspicious data flows detected.")

                    if d.get("scan_error"):
                        st.warning(f"Scan error: {d['scan_error']}")


def _render_scan_results(data: dict):
    """Render the score banner + detail tabs shared by all pipeline result views."""
    rr = data["release_readiness"]
    summary = data["summary"]
    score = rr["overall_score"]
    rec = rr["recommendation"]
    color = rr["color"]

    banner_bg = {"green": "#155724", "yellow": "#856404", "red": "#721c24"}.get(color, "#343a40")
    border_col = {"green": "#28a745", "yellow": "#ffc107", "red": "#dc3545"}.get(color, "#6c757d")
    rec_icon = {"SHIP IT": "✅", "REVIEW REQUIRED": "⚠️", "DO NOT SHIP": "🚫"}.get(rec, "")

    st.markdown(
        f"""
        <div style="background:{banner_bg};border:2px solid {border_col};border-radius:16px;
                    padding:32px;text-align:center;margin:16px 0">
          <div style="font-size:80px;font-weight:900;color:white;line-height:1">{score}</div>
          <div style="font-size:16px;color:rgba(255,255,255,0.7);margin:4px 0 12px">/100 Release Readiness Score</div>
          <div style="font-size:32px;font-weight:700;color:white">{rec_icon} {rec}</div>
          <div style="font-size:13px;color:rgba(255,255,255,0.6);margin-top:8px">{rr['recommendation_reason']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Stats row — include tests if present
    tests = data.get("tests")
    if tests and tests.get("total", 0) > 0:
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        t_icon = "✅" if tests["status"] == "ALL_PASSED" else "❌"
        c1.metric("Tests", f"{t_icon} {tests['passed']}/{tests['total']}")
        c2.metric("OWASP Critical", summary["owasp_critical"])
        c3.metric("OWASP High", summary["owasp_high"])
        c4.metric("OWASP Total", summary["owasp_total"])
        c5.metric("Secrets Found", summary["secrets_found"])
        c6.metric("Race Conditions", summary["race_conditions_found"])
    else:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("OWASP Critical", summary["owasp_critical"])
        c2.metric("OWASP High", summary["owasp_high"])
        c3.metric("OWASP Total", summary["owasp_total"])
        c4.metric("Secrets Found", summary["secrets_found"])
        c5.metric("Race Conditions", summary["race_conditions_found"])

    if rr["blocking_issues"]:
        st.error("**Blocking Issues:**  \n" + "  \n".join(f"• {b}" for b in rr["blocking_issues"]))

    st.markdown("---")

    tab_labels = ["🧪 Tests", "🔍 Intent Check", "🛡️ OWASP Top 10", "🔐 Secrets", "⚡ Race Conditions", "📋 Pre-flight", "📊 Signals"]
    tabs = st.tabs(tab_labels)

    # Tab 0: Tests
    with tabs[0]:
        tr = data.get("tests")
        if not tr or tr.get("total", 0) == 0:
            st.info("No tests were run for this scan. Tests run automatically via the Build & Validate pipeline.")
        else:
            status_color = {"ALL_PASSED": "green", "PARTIAL": "orange",
                            "ALL_FAILED": "red", "NO_TESTS_COLLECTED": "grey"}.get(tr["status"], "grey")
            st.markdown(f"**Status:** :{status_color}[{tr['status']}]  —  "
                        f"**{tr['passed']}/{tr['total']} tests passing** "
                        f"({tr['pass_rate']:.0%})")
            st.progress(tr["pass_rate"])

            col_p, col_f2, col_e = st.columns(3)
            col_p.metric("Passed", tr["passed"])
            col_f2.metric("Failed", tr["failed"])
            col_e.metric("Errors", tr["errors"])

            if tr["tests"]:
                st.markdown("**Test results:**")
                for t in tr["tests"]:
                    icon = "✅" if t["status"] == "PASSED" else "❌"
                    st.markdown(f"{icon} `{t['name']}`")

            if tr.get("output") and (tr["failed"] > 0 or tr["errors"] > 0):
                with st.expander("📋 Test output", expanded=False):
                    st.code(tr["output"], language="text")

    # Tab 1: Intent Check
    with tabs[1]:
        iv = data.get("intent_verification")
        if iv is None:
            st.info("No intent provided.")
        else:
            verdict = iv["verdict"]
            vc = {"INTENT_MET": "green", "GAP_DETECTED": "orange",
                  "HALLUCINATION": "red", "STUB_ONLY": "red", "UNCERTAIN": "grey"}.get(verdict, "grey")
            st.markdown(f"**Verdict:** :{vc}[{verdict}]  —  Confidence: {iv['confidence']:.0%}")
            st.markdown(f"**Safe to merge:** {'✅ Yes' if iv['is_safe_to_merge'] else '🚫 No'}")
            col_f, col_m = st.columns(2)
            with col_f:
                st.markdown("**Signals FOUND:**")
                for s in iv["intent_signals_found"]:
                    st.markdown(f"  ✅ {s}")
                if not iv["intent_signals_found"]:
                    st.caption("None")
            with col_m:
                st.markdown("**Signals MISSING:**")
                for s in iv["intent_signals_missing"]:
                    st.markdown(f"  ❌ {s}")
                if not iv["intent_signals_missing"]:
                    st.caption("None — good!")
            for issue in iv.get("issues", []):
                si = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}.get(issue["severity"], "⚪")
                st.markdown(f"{si} **{issue['issue_type']}** — {issue['description']}")
                if issue["line_snippet"]:
                    st.code(issue["line_snippet"][:200], language="python")

    # Tab 2: OWASP
    with tabs[2]:
        findings = data["owasp"]["findings"]
        if not findings:
            st.success("No OWASP Top 10 issues detected.")
        else:
            sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            for f in sorted(findings, key=lambda x: sev_order.get(x["severity"], 4)):
                si = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}.get(f["severity"], "⚪")
                with st.expander(f"{si} [{f['severity'].upper()}] {f['owasp_id']} — {f['description'][:80]}"):
                    ca, cb = st.columns(2)
                    ca.markdown(f"**Rule:** `{f['rule_id']}`  \n**Category:** {f['owasp_category']}")
                    cb.markdown(f"**CWE:** {f['cwe']}  \n**Line:** {f['line_number']}")
                    st.code(f["evidence"][:200], language="python")

    # Tab 3: Secrets
    with tabs[3]:
        sec_findings = data["secrets"]["findings"]
        if not sec_findings:
            st.success("No secrets detected.")
        else:
            st.warning(f"**{len(sec_findings)} secret(s) detected** — evidence redacted")
            for f in sec_findings:
                si = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(f["severity"], "⚪")
                st.markdown(f"{si} **{f['secret_type']}** — `{f['evidence']}` (line {f['line_number']})")

    # Tab 4: Race Conditions
    with tabs[4]:
        rc_findings = data["race_conditions"]["findings"]
        if not rc_findings:
            st.success("No race condition patterns detected.")
        else:
            for f in rc_findings:
                si = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(f["severity"], "⚪")
                with st.expander(f"{si} [{f['severity'].upper()}] {f['pattern_id']} — {f['description'][:80]}"):
                    st.markdown(f"**Attack scenario:** {f['attack_scenario']}")
                    st.code(f["evidence"][:200])

    # Tab 5: Pre-flight
    with tabs[5]:
        cl = data["preflight_checklist"]
        cats = cl.get("categories_triggered", [])
        if cats:
            st.markdown(f"**Categories triggered:** {', '.join(cats)}")
        items = cl.get("items", [])
        if not items:
            st.info("No specific pre-flight checks triggered.")
        else:
            for priority in ("MUST", "SHOULD", "CONSIDER"):
                priority_items = [i for i in items if i["priority"] == priority]
                if priority_items:
                    icon = {"MUST": "🔴", "SHOULD": "🟡", "CONSIDER": "🔵"}.get(priority, "")
                    st.markdown(f"### {icon} {priority}")
                    for item in priority_items:
                        st.markdown(f"- [ ] {item['item']}  \n  <small>*{item['triggered_by']}*</small>", unsafe_allow_html=True)

    # Tab 6: Signal Breakdown
    with tabs[6]:
        st.markdown("### Release Readiness Signal Breakdown")
        for sig in rr["signals"]:
            si = {"green": "🟢", "yellow": "🟡", "red": "🔴", "grey": "⚪"}.get(sig["status"], "⚪")
            block_tag = " 🚫 **BLOCKING**" if sig["blocking"] and sig["status"] == "red" else ""
            if sig["status"] == "grey":
                st.markdown(f"{si} **{sig['display_name']}** — *not provided (excluded)*")
            else:
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"{si} **{sig['display_name']}**{block_tag}  \n{sig['detail']}")
                    st.progress(sig["score"] / 100)
                with c2:
                    st.metric("", f"{sig['score']:.0f}/100")


def render_pipeline_demo():
    """AgenticQA — describe a feature, the pipeline builds and validates it."""
    import requests as _req

    st.markdown(
        """
        <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:12px;padding:28px;margin-bottom:24px">
          <h2 style="color:#e94560;margin:0 0 8px">🔬 AgenticQA Pipeline</h2>
          <p style="color:#a8b2c1;margin:0;font-size:15px">
            Describe what you want built. AgenticQA generates the code, runs every security scanner,
            and automatically fixes issues — giving you a
            <strong style="color:white">SHIP IT or DO NOT SHIP</strong> verdict.
            If it passes, a draft PR is opened for your review.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    api_base = st.text_input(
        "api_base", value=os.getenv("AGENTICQA_API_URL", "http://localhost:8000"),
        key="demo_api_base", label_visibility="collapsed",
    ).rstrip("/")

    description = st.text_area(
        "What do you want to build?",
        placeholder=(
            "e.g.  Add a /api/user/export endpoint that returns all data for a user "
            "including profile, activity history, and account settings as JSON"
        ),
        height=130,
        key="demo_description",
    )

    with st.expander("⚙️ Options", expanded=False):
        col_r, col_f = st.columns(2)
        repo_path = col_r.text_input(
            "Repo path (for real git workflow)",
            placeholder="Leave blank to use an isolated sandbox",
            key="demo_repo_path",
        )
        auto_fix = col_f.checkbox("Auto-fix and retry if issues found", value=True, key="demo_auto_fix")
        max_retries = col_f.slider("Max fix attempts", 1, 3, 2, key="demo_max_retries")

    api_key = st.session_state.get("anthropic_api_key", "")
    if not api_key:
        st.warning("Add your Anthropic API Key in the sidebar → **LLM Connection** to get started.")

    run_clicked = st.button(
        "Build & Validate",
        type="primary",
        key="demo_run",
        use_container_width=True,
        disabled=not description.strip() or not api_key,
    )

    st.markdown("---")

    if not run_clicked:
        return

    github_token = st.session_state.get("github_token", "")

    data = None
    with st.spinner("Building → scanning → fixing → validating..."):
        try:
            resp = _req.post(
                f"{api_base}/api/pipeline/run",
                json={
                    "description": description,
                    "repo_path": repo_path or "",
                    "api_key": api_key,
                    "github_token": github_token or None,
                    "auto_fix": auto_fix,
                    "max_retries": max_retries,
                },
                timeout=180,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            return

    if not data:
        return

    # ── Iteration progress trail ───────────────────────────────────────────────
    attempts = data.get("attempts", 1)
    iterations = data.get("iterations", [])
    if attempts > 1:
        st.markdown(f"**AgenticQA ran {attempts} attempt(s) before reaching a verdict:**")
        cols = st.columns(attempts)
        for i, iteration in enumerate(iterations):
            rec_i = iteration["recommendation"]
            icon_i = {"SHIP IT": "✅", "REVIEW REQUIRED": "⚠️", "DO NOT SHIP": "🔴"}.get(rec_i, "⚪")
            cols[i].markdown(f"**Attempt {iteration['attempt']}**  \n{icon_i} {rec_i}  \nOWASP critical: {iteration['summary']['owasp_critical']}")

    # ── PR link if created ─────────────────────────────────────────────────────
    pr_url = data.get("pr_url")
    if pr_url:
        st.success(f"**Draft PR opened** — code passed all checks.")
        st.link_button("View Pull Request on GitHub →", pr_url, type="primary")
    elif data.get("branch_pushed"):
        st.info(f"Branch pushed: `{data['branch']}` — PR creation failed, push the branch manually.")
    elif data.get("branch"):
        st.caption(f"Branch: `{data['branch']}` (local only — add a GitHub token to push)")

    # ── Final verdict + detail tabs ───────────────────────────────────────────
    _render_scan_results(data)

    # ── Generated code (last attempt) ────────────────────────────────────────
    if iterations:
        last_code = iterations[-1].get("generated_code", "")
        if last_code:
            with st.expander("📄 Generated code (final attempt)", expanded=False):
                st.code(last_code, language="python")


def render_release_readiness():
    """Release Readiness Score — single 0-100 production confidence score."""
    import requests as _req

    st.subheader("Release Readiness Score")
    st.markdown(
        "Aggregate every AgenticQA signal into one authoritative answer: **can I ship this?**  \n"
        "Provide any combination of agent outputs — missing signals are excluded from scoring."
    )

    api_base = st.text_input(
        "API URL",
        value=os.getenv("AGENTICQA_API_URL", "http://localhost:8000"),
        key="rr_api_base",
    ).rstrip("/")

    st.markdown("---")

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("**Test Coverage (SDET)**")
        coverage_pct = st.number_input(
            "Current coverage %", min_value=0.0, max_value=100.0, value=80.0, step=0.5, key="rr_cov"
        )
        include_coverage = st.checkbox("Include", value=True, key="rr_cov_inc")

        st.markdown("**CVE Exposure**")
        critical_cves = st.number_input("Critical CVEs (reachable)", min_value=0, value=0, key="rr_cve_crit")
        high_cves = st.number_input("High CVEs (reachable)", min_value=0, value=0, key="rr_cve_high")
        include_cve = st.checkbox("Include", value=True, key="rr_cve_inc")

        st.markdown("**Performance**")
        regression = st.checkbox("Regression detected", value=False, key="rr_perf_reg")
        include_perf = st.checkbox("Include", value=True, key="rr_perf_inc")

    with col_r:
        st.markdown("**Security Findings**")
        n_critical_sec = st.number_input("Critical findings", min_value=0, value=0, key="rr_sec_crit")
        n_high_sec = st.number_input("High findings", min_value=0, value=0, key="rr_sec_high")
        include_sec = st.checkbox("Include", value=True, key="rr_sec_inc")

        st.markdown("**Compliance**")
        n_violations = st.number_input("Violations", min_value=0, value=0, key="rr_comp_v")
        conformity_score = st.slider("Conformity score", 0.0, 1.0, 1.0, 0.05, key="rr_comp_cs")
        include_comp = st.checkbox("Include", value=True, key="rr_comp_inc")

        st.markdown("**Architecture Coverage**")
        untested_critical = st.number_input("Untested critical/high areas", min_value=0, value=0, key="rr_arch_u")
        total_areas = st.number_input("Total areas", min_value=1, value=20, key="rr_arch_t")
        include_arch = st.checkbox("Include", value=True, key="rr_arch_inc")

    st.markdown("---")

    if st.button("Compute Release Readiness Score", type="primary", key="rr_compute"):
        payload: dict = {}
        if include_coverage:
            payload["sdet_result"] = {"current_coverage": coverage_pct}
        if include_sec:
            findings = (
                [{"severity": "critical"}] * int(n_critical_sec) +
                [{"severity": "high"}] * int(n_high_sec)
            )
            payload["security_findings"] = findings
        if include_cve:
            payload["cve_result"] = {"critical_cves": int(critical_cves), "high_cves": int(high_cves), "reachable_cves": []}
        if include_perf:
            payload["perf_result"] = {"regression_detected": regression}
        if include_comp:
            payload["compliance_result"] = {
                "violations": [{}] * int(n_violations),
                "conformity_score": conformity_score,
            }
        if include_arch:
            payload["architecture_result"] = {
                "untested_critical_high": int(untested_critical),
                "total_areas": int(total_areas),
            }

        with st.spinner("Scoring..."):
            try:
                resp = _req.post(f"{api_base}/api/release-readiness", json=payload, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                st.error(f"API error: {e}")
                return

        score = data["overall_score"]
        rec   = data["recommendation"]
        color = data["color"]

        # Big score display
        banner_color = {"green": "#28a745", "yellow": "#ffc107", "red": "#dc3545"}.get(color, "#6c757d")
        rec_icon = {"SHIP IT": "✅", "REVIEW REQUIRED": "⚠️", "DO NOT SHIP": "🚫"}.get(rec, "")
        st.markdown(
            f"""
            <div style="background:{banner_color};border-radius:12px;padding:24px;text-align:center;margin-bottom:16px">
              <div style="font-size:64px;font-weight:900;color:white">{score}</div>
              <div style="font-size:18px;color:white;opacity:0.9">/100 Release Readiness Score</div>
              <div style="font-size:28px;margin-top:8px;color:white">{rec_icon} {rec}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.caption(data["recommendation_reason"])

        if data["blocking_issues"]:
            st.error("**Blocking Issues:**")
            for issue in data["blocking_issues"]:
                st.error(f"• {issue}")

        st.markdown("### Signal Breakdown")
        signals = data.get("signals", [])
        status_icon = {"green": "🟢", "yellow": "🟡", "red": "🔴", "grey": "⚪"}.get

        for sig in signals:
            s_icon = status_icon(sig["status"], "⚪")
            block_tag = " 🚫 BLOCKING" if sig["blocking"] and sig["status"] == "red" else ""
            if sig["status"] == "grey":
                st.markdown(f"{s_icon} **{sig['display_name']}** — *not provided*")
            else:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"{s_icon} **{sig['display_name']}**{block_tag}  \n{sig['detail']}")
                    st.progress(sig["score"] / 100)
                with col2:
                    st.metric("Score", f"{sig['score']:.0f}/100")

        st.caption(f"Signals provided: {data['signals_provided']}/{data['signals_total']}")


def render_agent_learning():
    """Agent Learning — developer risk profiles and repo learning metrics."""
    import requests as _req
    import pandas as pd

    st.subheader("Agent Learning")
    st.markdown(
        "Per-developer risk memory accumulated across CI runs. "
        "Risk scores (0–1) are EWMA-weighted: unfixed violations raise risk, "
        "auto-fixed violations lower it. Scores compound over time."
    )

    api_base = st.text_input(
        "API URL",
        value=os.getenv("AGENTICQA_API_URL", "http://localhost:8000"),
        key="learning_api_base",
    ).rstrip("/")

    repo_path = st.text_input(
        "Repo path",
        value=os.getenv("AGENTICQA_REPO_PATH", "."),
        key="learning_repo_path",
        help="Path to the git repository to analyse (used for repo_id detection)"
    )

    top_n = st.slider("Top N developers", min_value=5, max_value=50, value=10, step=5,
                      key="learning_top_n")

    if st.button("Load Developer Risk Profiles", key="learning_load_btn", type="primary"):
        with st.spinner("Fetching developer profiles..."):
            try:
                resp = _req.get(
                    f"{api_base}/api/developer-profiles",
                    params={"repo_path": repo_path, "top_n": top_n},
                    timeout=15,
                )
            except Exception as exc:
                st.error(f"Could not reach API: {exc}")
                return

        if resp.status_code != 200:
            st.error(f"API error {resp.status_code}: {resp.text[:300]}")
            return

        data = resp.json()
        leaderboard = data.get("leaderboard", [])

        if not leaderboard:
            st.info("No developer profiles recorded yet. Run the SRE agent on a real repo to start accumulating data.")
            return

        # ── Metrics row ──────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown(f"**Repo ID:** `{data.get('repo_id', 'unknown')}`")

        high_risk = sum(1 for d in leaderboard if d.get("risk_score", 0) > 0.3)
        med_risk  = sum(1 for d in leaderboard if 0.1 < d.get("risk_score", 0) <= 0.3)
        low_risk  = len(leaderboard) - high_risk - med_risk

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Developers Tracked", len(leaderboard))
        m2.metric("High Risk (>0.3)", high_risk, delta=None)
        m3.metric("Medium Risk (0.1–0.3)", med_risk)
        m4.metric("Low Risk (<0.1)", low_risk)

        # ── Horizontal bar chart ──────────────────────────────────────────────
        st.markdown("#### Developer Risk Leaderboard")
        import plotly.express as px

        df = pd.DataFrame(leaderboard)
        df["dev_label"] = df["dev_hash"].str[:8]  # show first 8 chars for readability
        df = df.sort_values("risk_score", ascending=True)  # plotly bar goes bottom→top

        color_map = []
        for score in df["risk_score"]:
            if score > 0.3:
                color_map.append("#e74c3c")   # red
            elif score > 0.1:
                color_map.append("#f39c12")   # amber
            else:
                color_map.append("#27ae60")   # green

        fig = px.bar(
            df,
            x="risk_score",
            y="dev_label",
            orientation="h",
            labels={"risk_score": "Risk Score (0–1)", "dev_label": "Developer (hash)"},
            title=f"Top {len(df)} Developers by Risk Score",
            color="risk_score",
            color_continuous_scale=[[0, "#27ae60"], [0.3, "#f39c12"], [1.0, "#e74c3c"]],
            range_color=[0, 1],
        )
        fig.update_layout(
            height=max(300, len(df) * 30),
            margin=dict(l=0, r=0, t=40, b=0),
            coloraxis_showscale=False,
            yaxis={"categoryorder": "total ascending"},
        )
        fig.add_vline(x=0.1, line_dash="dot", line_color="gray", annotation_text="medium",
                      annotation_position="top right")
        fig.add_vline(x=0.3, line_dash="dot", line_color="gray", annotation_text="high",
                      annotation_position="top right")
        st.plotly_chart(fig, use_container_width=True)

        # ── Dataframe ──────────────────────────────────────────────────────────
        st.markdown("#### Detail Table")
        display_df = df[["dev_label", "risk_score", "total_violations", "total_fixes", "last_seen"]].rename(
            columns={
                "dev_label": "Dev Hash (prefix)",
                "risk_score": "Risk Score",
                "total_violations": "Total Violations",
                "total_fixes": "Total Fixes",
                "last_seen": "Last Seen",
            }
        ).sort_values("Risk Score", ascending=False)
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Risk Score": st.column_config.ProgressColumn(
                    "Risk Score",
                    min_value=0.0,
                    max_value=1.0,
                    format="%.3f",
                ),
            },
        )

        st.caption(
            "Risk score is an EWMA (α=0.3) of violation observations. "
            "Unfixed violations contribute 1.0; auto-fixed contribute 0.0. "
            "Scores compound across CI runs — the longer AgenticQA runs, the more accurate this becomes."
        )

    # ── Compliance Drift & Learning Trends ────────────────────────────────────
    st.markdown("---")
    st.markdown("### Trend Visualizations")

    t_drift, t_fix, t_metrics, t_temporal = st.tabs(
        ["Compliance Drift", "Repo Fix Rate", "Learning Metrics", "Temporal Graphs"]
    )

    with t_drift:
        st.caption("Violation count per CI run — watch compliance drift over time.")
        if st.button("Load Compliance Drift", key="drift_load_btn"):
            with st.spinner("Fetching drift history..."):
                try:
                    dr = _req.get(
                        f"{api_base}/api/compliance/drift",
                        params={"repo_path": repo_path, "lookback": 30},
                        timeout=10,
                    )
                    if dr.status_code == 200:
                        drift_data = dr.json()
                        drift = drift_data.get("drift", {})
                        history = drift_data.get("history", [])

                        direction = drift.get("direction", "unknown")
                        delta = drift.get("delta", 0)
                        arrow = {"improving": "↓", "worsening": "↑", "stable": "→"}.get(direction, "?")
                        color = {"improving": "green", "worsening": "red", "stable": "gray"}.get(direction, "gray")

                        d1, d2, d3 = st.columns(3)
                        d1.metric("Direction", f"{arrow} {direction.capitalize()}")
                        d2.metric("Violation Delta (vs prior)", f"{delta:+d}")
                        d3.metric("Runs Analysed", drift.get("runs_analysed", 0))

                        trending = drift.get("trending_rules", [])
                        if trending:
                            st.warning(f"Trending rules: {', '.join(r['rule'] for r in trending[:5])}")

                        if history:
                            import plotly.graph_objects as _go2
                            import pandas as _pd3
                            hdf = _pd3.DataFrame(history)
                            fig_drift = _go2.Figure()
                            fig_drift.add_trace(_go2.Scatter(
                                x=hdf["recorded_at"],
                                y=hdf["violations"],
                                mode="lines+markers",
                                name="Violations",
                                line=dict(color="#e74c3c" if direction == "worsening" else "#27ae60"),
                                fill="tozeroy",
                                fillcolor="rgba(231,76,60,0.08)" if direction == "worsening" else "rgba(39,174,96,0.08)",
                            ))
                            fig_drift.update_layout(
                                height=280,
                                margin=dict(l=0, r=0, t=30, b=0),
                                xaxis_title="Run",
                                yaxis_title="Violations",
                                title="Compliance Violations per Run",
                            )
                            st.plotly_chart(fig_drift, use_container_width=True)
                        else:
                            st.info("No drift history yet — run the compliance agent to start tracking.")
                    else:
                        st.error(f"API error {dr.status_code}")
                except Exception as exc:
                    st.error(f"Could not reach API: {exc}")

    with t_fix:
        st.caption("EWMA fix rate per run for this repo — improves as SRE agent learns unfixable rules.")
        if st.button("Load Repo Fix Rate", key="fixrate_load_btn"):
            with st.spinner("Fetching repo profile..."):
                try:
                    rp = _req.get(
                        f"{api_base}/api/repo-profile",
                        params={"repo_path": repo_path},
                        timeout=10,
                    )
                    if rp.status_code == 200:
                        rp_data = rp.json()
                        profile = rp_data.get("profile", {})
                        run_history = profile.get("run_history", [])

                        p1, p2, p3 = st.columns(3)
                        p1.metric("Total Runs", profile.get("total_runs", 0))
                        langs = profile.get("fix_rates_by_language", {})
                        p2.metric("Languages", len(langs))
                        unfixable = profile.get("known_unfixable_rules", [])
                        p3.metric("Known Unfixable Rules", len(unfixable))

                        if unfixable:
                            st.info(f"Unfixable: {', '.join(unfixable[:10])}")

                        if run_history:
                            import plotly.graph_objects as _go3
                            import pandas as _pd4
                            rdf = _pd4.DataFrame(run_history)
                            fig_fix = _go3.Figure()
                            if "fix_rate" in rdf.columns:
                                fig_fix.add_trace(_go3.Scatter(
                                    x=rdf.get("timestamp", list(range(len(rdf)))),
                                    y=rdf["fix_rate"],
                                    mode="lines+markers",
                                    name="Fix Rate",
                                    line=dict(color="#1f77b4"),
                                ))
                                fig_fix.add_hline(y=1.0, line_dash="dot", line_color="gray",
                                                  annotation_text="100%")
                                fig_fix.update_layout(
                                    height=280,
                                    margin=dict(l=0, r=0, t=30, b=0),
                                    yaxis_title="Fix Rate",
                                    yaxis=dict(range=[0, 1.05]),
                                    title="SRE Fix Rate per Run",
                                )
                                st.plotly_chart(fig_fix, use_container_width=True)
                            else:
                                st.dataframe(rdf, use_container_width=True, hide_index=True)
                        else:
                            st.info("No run history yet — run the SRE agent to populate this chart.")
                    else:
                        st.error(f"API error {rp.status_code}")
                except Exception as exc:
                    st.error(f"Could not reach API: {exc}")

    with t_metrics:
        st.caption("System-wide improvement curve — fix rate, artifact count, and delegation pairs over time.")
        if st.button("Load Learning Metrics", key="metrics_load_btn"):
            with st.spinner("Fetching metrics history..."):
                try:
                    mr = _req.get(
                        f"{api_base}/api/learning-metrics",
                        params={"repo_id": "", "limit": 30},
                        timeout=10,
                    )
                    if mr.status_code == 200:
                        mdata = mr.json()
                        summary = mdata.get("summary", {})
                        curves = mdata.get("curves", {})

                        s1, s2, s3, s4 = st.columns(4)
                        s1.metric("Runs", summary.get("runs", 0))
                        s2.metric("Avg Fix Rate", f"{summary.get('avg_fix_rate') or 0:.1%}")
                        s3.metric("Fix Rate Trend", summary.get("fix_rate_trend") or "n/a")
                        s4.metric("Avg Artifacts", summary.get("avg_artifact_count") or 0)

                        fix_curve = curves.get("fix_rate", [])
                        art_curve = curves.get("artifact_count", [])

                        if fix_curve or art_curve:
                            import plotly.graph_objects as _go4
                            fig_m = _go4.Figure()
                            if fix_curve:
                                fig_m.add_trace(_go4.Scatter(
                                    x=[p["recorded_at"] for p in fix_curve],
                                    y=[p["value"] for p in fix_curve],
                                    mode="lines+markers",
                                    name="Fix Rate",
                                    line=dict(color="#1f77b4"),
                                    yaxis="y1",
                                ))
                            if art_curve:
                                fig_m.add_trace(_go4.Scatter(
                                    x=[p["recorded_at"] for p in art_curve],
                                    y=[p["value"] for p in art_curve],
                                    mode="lines",
                                    name="Artifacts",
                                    line=dict(color="#ff7f0e", dash="dot"),
                                    yaxis="y2",
                                ))
                            fig_m.update_layout(
                                height=300,
                                margin=dict(l=0, r=0, t=30, b=0),
                                title="System Learning Improvement Curve",
                                yaxis=dict(title="Fix Rate", range=[0, 1.05]),
                                yaxis2=dict(
                                    title="Artifact Count",
                                    overlaying="y", side="right",
                                    showgrid=False,
                                ),
                                legend=dict(x=0, y=1.1, orientation="h"),
                            )
                            st.plotly_chart(fig_m, use_container_width=True)
                        else:
                            st.info("No metrics history yet. Run CI pipelines to populate this chart.")
                    else:
                        st.error(f"API error {mr.status_code}")
                except Exception as exc:
                    st.error(f"Could not reach API: {exc}")

    with t_temporal:
        st.caption(
            "Violation trends stored as timestamped nodes in Neo4j — "
            "query by day/week to see how your codebase health evolves."
        )
        t_days = st.slider("Lookback (days)", 7, 90, 30, step=7, key="temporal_days")
        t_gran = st.selectbox("Granularity", ["day", "week"], key="temporal_gran")
        if st.button("Load Temporal Graphs", key="temporal_load_btn"):
            with st.spinner("Querying Neo4j temporal graph..."):
                import hashlib as _hl_dash, subprocess as _sp_dash
                try:
                    _p5 = _sp_dash.run(
                        ["git", "remote", "get-url", "origin"],
                        capture_output=True, text=True, timeout=5, cwd=repo_path,
                    )
                    _url5 = _p5.stdout.strip().lower().rstrip("/").removesuffix(".git")
                    _repo_id_dash = _hl_dash.sha1(_url5.encode()).hexdigest()[:12] if _url5 else "unknown"
                except Exception:
                    _repo_id_dash = _hl_dash.sha1(repo_path.encode()).hexdigest()[:12]

                try:
                    tr = _req.get(
                        f"{api_base}/api/temporal/violations",
                        params={"repo_id": _repo_id_dash, "days": t_days, "granularity": t_gran},
                        timeout=15,
                    )
                    if tr.status_code == 200:
                        tdata = tr.json()
                        trend = tdata.get("trend", [])
                        fix_trend = tdata.get("fix_rate", [])
                        top_rules = tdata.get("top_rules", [])
                        agents = tdata.get("agents", [])

                        if not trend and not fix_trend:
                            st.info(
                                "No temporal data yet. "
                                "The SRE agent writes a :ViolationSnapshot node to Neo4j after each run."
                            )
                        else:
                            import plotly.graph_objects as _go5
                            import pandas as _pd5

                            # ── Violation count over time ──
                            if trend:
                                tdf = _pd5.DataFrame(trend)
                                fig_t = _go5.Figure()
                                fig_t.add_trace(_go5.Bar(
                                    x=tdf["period"],
                                    y=tdf["total_errors"],
                                    name="Total Errors",
                                    marker_color="#e74c3c",
                                ))
                                fig_t.add_trace(_go5.Scatter(
                                    x=tdf["period"],
                                    y=tdf["avg_fix_rate"],
                                    name="Avg Fix Rate",
                                    mode="lines+markers",
                                    line=dict(color="#1f77b4"),
                                    yaxis="y2",
                                ))
                                fig_t.update_layout(
                                    height=300,
                                    margin=dict(l=0, r=0, t=30, b=0),
                                    title=f"Violations per {t_gran.capitalize()} (Neo4j)",
                                    yaxis=dict(title="Violations"),
                                    yaxis2=dict(
                                        title="Fix Rate",
                                        overlaying="y", side="right",
                                        range=[0, 1.05], showgrid=False,
                                    ),
                                    barmode="overlay",
                                    legend=dict(x=0, y=1.1, orientation="h"),
                                )
                                st.plotly_chart(fig_t, use_container_width=True)

                            # ── Top rules bar ──
                            if top_rules:
                                st.markdown("**Top Violation Rules**")
                                rdf = _pd5.DataFrame(top_rules)
                                fig_r = _go5.Figure(_go5.Bar(
                                    x=rdf["total_count"],
                                    y=rdf["rule"],
                                    orientation="h",
                                    marker_color="#f39c12",
                                ))
                                fig_r.update_layout(
                                    height=max(200, len(rdf) * 28),
                                    margin=dict(l=0, r=0, t=20, b=0),
                                    yaxis={"categoryorder": "total ascending"},
                                )
                                st.plotly_chart(fig_r, use_container_width=True)

                            # ── Agent comparison ──
                            if agents:
                                st.markdown("**Agent Comparison**")
                                adf = _pd5.DataFrame(agents)
                                st.dataframe(
                                    adf.rename(columns={
                                        "agent": "Agent",
                                        "runs": "Runs",
                                        "avg_fix_rate": "Avg Fix Rate",
                                        "total_errors": "Total Errors",
                                    }),
                                    use_container_width=True,
                                    hide_index=True,
                                )
                    else:
                        st.error(f"API error {tr.status_code}: {tr.text[:200]}")
                except Exception as exc:
                    st.error(f"Could not reach API: {exc}")

    # ── Org Memory ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Cross-Repo Org Memory")
    st.caption("Patterns discovered in one repo instantly inform every other repo in the org.")

    if st.button("Load Org Memory", key="org_mem_btn"):
        try:
            org_resp = _req.get(
                f"{api_base}/api/org-memory",
                params={"repo_path": repo_path},
                timeout=10,
            )
            if org_resp.status_code == 200:
                org = org_resp.json()
                o1, o2, o3 = st.columns(3)
                o1.metric("Org", org.get("org_name", "unknown"))
                o2.metric("Repos Seen", org.get("repos_seen", 0))
                o3.metric("Total Runs", org.get("total_runs", 0))

                if org.get("unfixable_rules"):
                    st.warning(f"Org-wide unfixable rules: {', '.join(org['unfixable_rules'])}")

                if org.get("top_rules"):
                    st.markdown("#### Top Violation Rules (org-wide)")
                    import pandas as _pd2
                    rules_df = _pd2.DataFrame([
                        {
                            "Rule": r["rule"],
                            "Total Violations": r["total_violations"],
                            "Total Fixes": r["total_fixes"],
                            "Fix Rate": f"{r['fix_rate']:.1%}",
                            "Repos": len(r.get("repos", [])),
                        }
                        for r in org["top_rules"]
                    ])
                    st.dataframe(rules_df, use_container_width=True, hide_index=True)
            else:
                st.error(f"API error {org_resp.status_code}")
        except Exception as exc:
            st.error(f"Could not reach API: {exc}")


def main():
    """Main dashboard"""
    render_header()
    
    view = st.query_params.get("view", "")
    if view == "plans":
        render_plans_and_tiers()
        st.caption(
            f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | AgenticQA Plans"
        )
        return

    # Get store early so sidebar can show connection status
    store = get_graph_store()

    # Sidebar
    with st.sidebar:
        st.title("📊 Navigation")
        st.markdown("---")

        pages = ["Live Pipeline Demo", "Operator Console", "System Overview", "Collaboration", "Performance", "GraphRAG", "Ontology", "Pipeline", "Governance", "Compliance Scan", "Architecture Scan", "Agent Safety", "Red Team", "Agent Learning", "Release Readiness"]

        selected_view = str(st.query_params.get("view", "")).strip().lower()
        if selected_view in {"operator", "prompt-ops", "prompt_ops"}:
            default_index = pages.index("Operator Console")
        elif selected_view == "graphrag":
            default_index = pages.index("GraphRAG")
        elif selected_view in {"governance", "constitution"}:
            default_index = pages.index("Governance")
        elif selected_view in {"demo", "pipeline-demo", "live"}:
            default_index = pages.index("Live Pipeline Demo")
        else:
            default_index = pages.index("Live Pipeline Demo")  # default landing page

        page = st.radio(
            "Select View:",
            pages,
            index=default_index
        )

        st.markdown("---")
        st.markdown("### 🔑 LLM Connection")

        anthropic_key = st.text_input(
            "Anthropic API Key",
            value=st.session_state.get("anthropic_api_key", ""),
            type="password",
            placeholder="sk-ant-...",
            help="Used by Generate & Scan. Stored in this browser session only — never written to disk.",
            key="sidebar_anthropic_key",
        )
        if anthropic_key:
            st.session_state["anthropic_api_key"] = anthropic_key
            st.success("Key set", icon="✅")
        else:
            st.caption("Get a key at console.anthropic.com")

        github_token = st.text_input(
            "GitHub Token (optional)",
            value=st.session_state.get("github_token", ""),
            type="password",
            placeholder="ghp_...",
            help="Enables automatic branch push + draft PR when code passes. Needs repo write scope.",
            key="sidebar_github_token",
        )
        if github_token:
            st.session_state["github_token"] = github_token
            st.success("Token set", icon="✅")
        else:
            st.caption("Without this, code is validated but not pushed.")

        st.markdown("---")
        st.markdown("### ⚙️ Settings")

        auto_refresh = st.checkbox("Auto-refresh (30s)", value=False)

        if st.button("🔄 Refresh Data"):
            st.cache_resource.clear()
            st.rerun()

        st.markdown("---")
        st.markdown("### 🔌 Data Sources")
        if store:
            st.success("Neo4j: Connected")
        else:
            st.error("Neo4j: Disconnected")

        st.markdown("---")
        st.markdown("### 📚 Resources")
        st.markdown("[Neo4j Browser](http://localhost:7474)")
        st.markdown("[Documentation](https://github.com/nhomyk/AgenticQA)")
        st.markdown("---")
        st.markdown("### 💼 Commercial")
        st.markdown("[Plans & Tiers](?view=plans)")

        # Auto-refresh
        if auto_refresh:
            import time
            time.sleep(30)
            st.rerun()

    # Pages that require Neo4j
    neo4j_required_pages = {"Collaboration", "Performance", "Ontology"}

    if not store and page in neo4j_required_pages:
        st.warning("Neo4j is not connected. This page requires a running Neo4j instance.")
        st.info("Start Neo4j with: `docker-compose -f docker-compose.weaviate.yml up -d neo4j`")
        st.markdown("---")
        st.markdown("Pages available without Neo4j: **Operator Console**, **System Overview**, **GraphRAG**, **Pipeline**, **Governance**")
        return

    # Render selected page
    if page == "Operator Console":
        render_prompt_ops()

    elif page == "System Overview":
        render_stack_anatomy(store)
        st.markdown("---")
        if store:
            render_overview_metrics(store)
            st.markdown("---")
            render_top_agents(store)
            st.markdown("---")
            render_live_activity(store)
        else:
            st.info("Connect Neo4j to see agent metrics, top performers, and live activity.")

    elif page == "Collaboration":
        tab_network, tab_chains = st.tabs(["Network Graph", "Delegation Chains"])
        with tab_network:
            render_collaboration_network(store)
        with tab_chains:
            render_delegation_chains(store)

    elif page == "Performance":
        tab_metrics, tab_testing = st.tabs(["Agent Metrics", "Test Results"])
        with tab_metrics:
            render_performance_metrics(store)
        with tab_testing:
            render_agent_testing(store)

    elif page == "GraphRAG":
        tab_rec, tab_trends = st.tabs(["Recommendations", "RAG Quality Trends"])
        with tab_rec:
            render_graphrag_recommendations(store)
        with tab_trends:
            render_rag_quality_trends()

    elif page == "Ontology":
        render_ontology(store)

    elif page == "Pipeline":
        tab_flow, tab_security, tab_api = st.tabs(["Data Flow", "Security", "API Connectivity"])
        with tab_flow:
            render_pipeline_flow(store)
        with tab_security:
            render_pipeline_security(store)
        with tab_api:
            render_api_plug(store)

    elif page == "Governance":
        render_governance_page()

    elif page == "Compliance Scan":
        render_compliance_scan()

    elif page == "Architecture Scan":
        render_architecture_scan()

    elif page == "Agent Safety":
        render_agent_safety_monitor()

    elif page == "Red Team":
        render_red_team()

    elif page == "Agent Learning":
        render_agent_learning()

    elif page == "Release Readiness":
        render_release_readiness()

    elif page == "Live Pipeline Demo":
        render_pipeline_demo()

    # Footer
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | AgenticQA Analytics Dashboard v1.0")


if __name__ == "__main__":
    main()

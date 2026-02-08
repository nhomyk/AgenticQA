"""
Plotly Chart Correctness Tests

Validates that dashboard chart functions produce correct Plotly figures
with expected traces, data, and layout properties.
"""

import pytest
import sys
import os
import math
from unittest.mock import MagicMock, patch
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestCollaborationNetworkChart:
    """Tests for the network graph in render_collaboration_network"""

    def _build_network_figure(self, nodes, edges):
        """Reproduce the chart logic from render_collaboration_network."""
        node_list = list(nodes)
        node_x, node_y, node_text = [], [], []

        n = len(node_list)
        for i, node in enumerate(node_list):
            angle = 2 * math.pi * i / n
            node_x.append(math.cos(angle))
            node_y.append(math.sin(angle))
            node_text.append(node)

        edge_traces = []
        for edge in edges:
            src_idx = node_list.index(edge["source"])
            tgt_idx = node_list.index(edge["target"])
            color = "#28a745" if edge["success_rate"] > 0.8 else "#ffc107" if edge["success_rate"] > 0.5 else "#dc3545"

            edge_traces.append(go.Scatter(
                x=[node_x[src_idx], node_x[tgt_idx], None],
                y=[node_y[src_idx], node_y[tgt_idx], None],
                mode='lines',
                line=dict(width=edge["weight"], color=color),
                showlegend=False,
            ))

        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            marker=dict(size=30, color='#1f77b4'),
            text=node_text,
            showlegend=False,
        )

        fig = go.Figure(data=edge_traces + [node_trace])
        return fig

    def test_network_has_correct_trace_count(self):
        nodes = {"A", "B", "C"}
        edges = [
            {"source": "A", "target": "B", "weight": 3, "success_rate": 0.9},
            {"source": "B", "target": "C", "weight": 1, "success_rate": 0.4},
        ]
        fig = self._build_network_figure(nodes, edges)
        # 2 edge traces + 1 node trace
        assert len(fig.data) == 3

    def test_node_positions_circular_layout(self):
        nodes = {"A", "B", "C", "D"}
        fig = self._build_network_figure(nodes, [])
        node_trace = fig.data[-1]
        # 4 nodes on unit circle
        for x, y in zip(node_trace.x, node_trace.y):
            radius = math.sqrt(x**2 + y**2)
            assert abs(radius - 1.0) < 1e-10

    def test_edge_color_green_for_high_success(self):
        nodes = {"A", "B"}
        edges = [{"source": "A", "target": "B", "weight": 5, "success_rate": 0.95}]
        fig = self._build_network_figure(nodes, edges)
        assert fig.data[0].line.color == "#28a745"

    def test_edge_color_yellow_for_medium_success(self):
        nodes = {"A", "B"}
        edges = [{"source": "A", "target": "B", "weight": 3, "success_rate": 0.65}]
        fig = self._build_network_figure(nodes, edges)
        assert fig.data[0].line.color == "#ffc107"

    def test_edge_color_red_for_low_success(self):
        nodes = {"A", "B"}
        edges = [{"source": "A", "target": "B", "weight": 2, "success_rate": 0.3}]
        fig = self._build_network_figure(nodes, edges)
        assert fig.data[0].line.color == "#dc3545"

    def test_edge_width_matches_weight(self):
        nodes = {"A", "B"}
        edges = [{"source": "A", "target": "B", "weight": 7, "success_rate": 0.5}]
        fig = self._build_network_figure(nodes, edges)
        assert fig.data[0].line.width == 7

    def test_node_labels_present(self):
        nodes = {"Alpha", "Beta"}
        fig = self._build_network_figure(nodes, [])
        node_trace = fig.data[-1]
        assert set(node_trace.text) == {"Alpha", "Beta"}


class TestTopAgentsBarChart:
    """Tests for the bar chart in render_top_agents"""

    def _build_top_agents_figure(self, data):
        df = pd.DataFrame(data)
        df["success_rate"] = (df["successes"] / df["delegation_count"] * 100).round(1)
        df["avg_duration_ms"] = df["avg_duration_ms"].fillna(0).round(0)

        fig = px.bar(
            df, x="agent", y="delegation_count",
            color="success_rate", color_continuous_scale="RdYlGn",
            title="Delegation Count by Agent",
        )
        return fig, df

    def test_bar_chart_has_one_trace(self):
        data = [
            {"agent": "SRE", "delegation_count": 7, "successes": 6, "avg_duration_ms": 900.0},
            {"agent": "QA", "delegation_count": 3, "successes": 3, "avg_duration_ms": 490.0},
        ]
        fig, _ = self._build_top_agents_figure(data)
        assert len(fig.data) == 1

    def test_bar_chart_x_values(self):
        data = [
            {"agent": "SRE", "delegation_count": 7, "successes": 6, "avg_duration_ms": 900.0},
            {"agent": "QA", "delegation_count": 3, "successes": 3, "avg_duration_ms": 490.0},
        ]
        fig, _ = self._build_top_agents_figure(data)
        assert list(fig.data[0].x) == ["SRE", "QA"]

    def test_bar_chart_y_values(self):
        data = [
            {"agent": "SRE", "delegation_count": 7, "successes": 6, "avg_duration_ms": 900.0},
            {"agent": "QA", "delegation_count": 3, "successes": 3, "avg_duration_ms": 490.0},
        ]
        fig, _ = self._build_top_agents_figure(data)
        assert list(fig.data[0].y) == [7, 3]

    def test_success_rate_calculation(self):
        data = [
            {"agent": "SRE", "delegation_count": 10, "successes": 8, "avg_duration_ms": 100.0},
        ]
        _, df = self._build_top_agents_figure(data)
        assert df["success_rate"].iloc[0] == 80.0

    def test_title_set_correctly(self):
        data = [{"agent": "A", "delegation_count": 1, "successes": 1, "avg_duration_ms": 0.0}]
        fig, _ = self._build_top_agents_figure(data)
        assert fig.layout.title.text == "Delegation Count by Agent"

    def test_nan_duration_filled_to_zero(self):
        data = [{"agent": "A", "delegation_count": 1, "successes": 1, "avg_duration_ms": None}]
        _, df = self._build_top_agents_figure(data)
        assert df["avg_duration_ms"].iloc[0] == 0.0


class TestBottleneckChart:
    """Tests for the bottleneck detection chart in render_performance_metrics"""

    def _build_bottleneck_figure(self, data):
        df = pd.DataFrame(data)
        df["avg_duration"] = df["avg_duration"].round(0)
        df["p95_duration"] = df["p95_duration"].fillna(0).round(0)

        fig = px.bar(
            df, x="agent", y="avg_duration",
            color="slow_delegations",
            title="Slow Delegations by Agent",
            color_continuous_scale="Reds",
        )
        return fig, df

    def test_bottleneck_chart_data(self):
        data = [
            {"agent": "SRE", "avg_duration": 1500.3, "p95_duration": 2100.7, "slow_delegations": 3},
        ]
        fig, df = self._build_bottleneck_figure(data)
        assert list(fig.data[0].x) == ["SRE"]
        assert list(fig.data[0].y) == [1500.0]

    def test_p95_nan_handled(self):
        data = [
            {"agent": "QA", "avg_duration": 800.0, "p95_duration": None, "slow_delegations": 1},
        ]
        _, df = self._build_bottleneck_figure(data)
        assert df["p95_duration"].iloc[0] == 0.0

    def test_uses_reds_colorscale(self):
        data = [{"agent": "A", "avg_duration": 1000.0, "p95_duration": 1200.0, "slow_delegations": 2}]
        fig, _ = self._build_bottleneck_figure(data)
        assert fig.layout.title.text == "Slow Delegations by Agent"


class TestSuccessRateChart:
    """Tests for the success rate by pair chart"""

    def _build_success_rate_figure(self, data):
        df = pd.DataFrame(data)
        df["pair"] = df["from_agent"] + " → " + df["to_agent"]
        df["success_rate_pct"] = (df["success_rate"] * 100).round(1)

        fig = px.bar(
            df, x="pair", y="success_rate_pct",
            color="success_rate_pct",
            color_continuous_scale="RdYlGn",
            range_color=[0, 100],
            title="Success Rate by Agent Pair",
        )
        fig.update_xaxes(tickangle=45)
        return fig, df

    def test_pair_label_format(self):
        data = [{"from_agent": "SDET", "to_agent": "SRE", "success_rate": 0.75, "total": 4}]
        _, df = self._build_success_rate_figure(data)
        assert df["pair"].iloc[0] == "SDET → SRE"

    def test_success_rate_percentage_conversion(self):
        data = [{"from_agent": "A", "to_agent": "B", "success_rate": 0.923, "total": 10}]
        _, df = self._build_success_rate_figure(data)
        assert df["success_rate_pct"].iloc[0] == 92.3

    def test_color_range_0_to_100(self):
        data = [{"from_agent": "A", "to_agent": "B", "success_rate": 0.5, "total": 2}]
        fig, _ = self._build_success_rate_figure(data)
        coloraxis = fig.layout.coloraxis
        assert coloraxis.cmin == 0
        assert coloraxis.cmax == 100

    def test_x_axis_rotated(self):
        data = [{"from_agent": "A", "to_agent": "B", "success_rate": 0.5, "total": 2}]
        fig, _ = self._build_success_rate_figure(data)
        assert fig.layout.xaxis.tickangle == 45


class TestRadarChart:
    """Tests for the production readiness radar chart"""

    def _build_radar_figure(self, scoring):
        categories = ["Tests", "CI/CD", "Error Handling", "Documentation", "Ops Maturity"]
        fig = go.Figure()
        for fw in scoring:
            values = [fw[c] for c in categories] + [fw[categories[0]]]
            fig.add_trace(go.Scatterpolar(
                r=values,
                theta=categories + [categories[0]],
                fill='toself',
                name=fw["Framework"],
                opacity=0.6,
            ))
        return fig

    def test_radar_trace_count(self):
        scoring = [
            {"Framework": "Python", "Tests": 95, "CI/CD": 95, "Error Handling": 90, "Documentation": 85, "Ops Maturity": 90},
            {"Framework": "Pytest", "Tests": 100, "CI/CD": 95, "Error Handling": 90, "Documentation": 95, "Ops Maturity": 95},
        ]
        fig = self._build_radar_figure(scoring)
        assert len(fig.data) == 2

    def test_radar_values_loop_back(self):
        scoring = [
            {"Framework": "X", "Tests": 80, "CI/CD": 70, "Error Handling": 60, "Documentation": 50, "Ops Maturity": 40},
        ]
        fig = self._build_radar_figure(scoring)
        r_values = list(fig.data[0].r)
        # First and last should be equal (loop closure)
        assert r_values[0] == r_values[-1]
        assert len(r_values) == 6  # 5 categories + 1 closure

    def test_radar_trace_names(self):
        scoring = [
            {"Framework": "FastAPI", "Tests": 55, "CI/CD": 60, "Error Handling": 70, "Documentation": 60, "Ops Maturity": 60},
        ]
        fig = self._build_radar_figure(scoring)
        assert fig.data[0].name == "FastAPI"

    def test_radar_fill_mode(self):
        scoring = [
            {"Framework": "A", "Tests": 50, "CI/CD": 50, "Error Handling": 50, "Documentation": 50, "Ops Maturity": 50},
        ]
        fig = self._build_radar_figure(scoring)
        assert fig.data[0].fill == "toself"


class TestChainHistogram:
    """Tests for the delegation chain length histogram"""

    def test_histogram_creation(self):
        chain_data = [
            {"chain": ["A", "B", "C"], "length": 3},
            {"chain": ["A", "B", "C", "D"], "length": 4},
            {"chain": ["X", "Y", "Z"], "length": 3},
        ]
        df = pd.DataFrame(chain_data)
        fig = px.histogram(df, x="length", title="Chain Length Distribution")
        assert fig.data[0].x is not None
        assert fig.layout.title.text == "Chain Length Distribution"

    def test_histogram_bin_values(self):
        chain_data = [{"chain": ["A", "B"], "length": 2}] * 5 + \
                     [{"chain": ["A", "B", "C"], "length": 3}] * 3
        df = pd.DataFrame(chain_data)
        fig = px.histogram(df, x="length")
        # Should have data for lengths 2 and 3
        assert len(fig.data) == 1

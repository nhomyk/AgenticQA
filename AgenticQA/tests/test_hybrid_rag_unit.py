from agenticqa.graph.hybrid_rag import HybridGraphRAG, create_hybrid_rag


class _Rag:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail

    def augment_agent_context(self, agent_type, context):
        if self.should_fail:
            raise RuntimeError("rag failed")
        return {
            "rag_recommendations": [
                {
                    "insight": "Use retries",
                    "confidence": 0.82,
                    "metadata": {"execution_id": "exec-1"},
                },
                {"insight": "Low confidence", "confidence": 0.4, "metadata": {}},
            ]
        }


class _Graph:
    def get_delegation_history_for_task(self, task_type, status="success", limit=5):
        return [
            {
                "from_agent": "SDET_Agent",
                "to_agent": "SRE_Agent",
                "task": task_type,
                "result": "ok",
                "duration_ms": 120.0,
            },
            {
                "from_agent": "SDET_Agent",
                "to_agent": "SRE_Agent",
                "task": task_type,
                "result": "ok",
                "duration_ms": 80.0,
            },
        ]

    def recommend_delegation_target(self, from_agent, task_type, acceptable_duration_ms=5000.0):
        return {
            "recommended_agent": "SRE_Agent",
            "success_count": 5,
            "avg_duration": 110.0,
        }


def test_query_combines_weaviate_and_neo4j_patterns():
    hr = HybridGraphRAG(rag_system=_Rag(), graph_store=_Graph())

    result = hr.query(agent_type="qa", context={"x": 1}, task_type="deploy_tests")

    assert "weaviate" in result["sources"]
    assert "neo4j" in result["sources"]
    assert len(result["weaviate_insights"]) == 2
    assert len(result["neo4j_patterns"]) == 2
    assert len(result["combined_recommendations"]) >= 1


def test_query_weaviate_failure_graceful_and_factory():
    hr = create_hybrid_rag(rag_system=_Rag(should_fail=True), graph_store=None)

    result = hr.query(agent_type="qa", context={"x": 1})

    assert result["weaviate_insights"] == []
    assert result["neo4j_patterns"] == []
    assert result["combined_recommendations"] == []


def test_extract_delegation_recommendations_requires_multiple_successes():
    hr = HybridGraphRAG(rag_system=None, graph_store=None)

    recs = hr._extract_delegation_recommendations(
        [
            {
                "pattern_type": "delegation_success",
                "from_agent": "A",
                "to_agent": "B",
                "duration_ms": 100,
            },
            {
                "pattern_type": "delegation_success",
                "from_agent": "A",
                "to_agent": "B",
                "duration_ms": 200,
            },
            {
                "pattern_type": "other",
                "from_agent": "X",
                "to_agent": "Y",
                "duration_ms": 1,
            },
        ]
    )

    assert len(recs) == 1
    assert recs[0]["type"] == "delegation_pattern"
    assert "Delegate to B" in recs[0]["recommendation"]


def test_recommend_delegation_target_hybrid_and_fallback():
    class _LowConfidenceRag(_Rag):
        def augment_agent_context(self, agent_type, context):
            return {
                "rag_recommendations": [
                    {"insight": "weak hint", "confidence": 0.5, "metadata": {"execution_id": "exec-1"}}
                ]
            }

    hr = HybridGraphRAG(rag_system=_LowConfidenceRag(), graph_store=_Graph())

    hybrid = hr.recommend_delegation_target("SDET_Agent", {"a": 1}, task_type="deploy_tests")
    assert hybrid["hybrid"] is True
    assert hybrid["recommended_agent"] == "SRE_Agent"

    hr2 = HybridGraphRAG(rag_system=_Rag(), graph_store=None)
    fallback = hr2.recommend_delegation_target("SDET_Agent", {"a": 1}, task_type="deploy_tests")
    assert fallback is not None
    assert "recommendation" in fallback

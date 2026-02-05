"""
Hybrid GraphRAG System: Weaviate + Neo4j

Combines:
- Weaviate: Semantic similarity search (vector embeddings)
- Neo4j: Relationship context (delegation chains, structural patterns)

This enables AI agents to learn from BOTH:
1. "What similar situations looked like?" (Weaviate)
2. "How did we solve them collaboratively?" (Neo4j)
"""

from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class HybridGraphRAG:
    """
    Hybrid RAG combining Weaviate (semantic) and Neo4j (structural).

    Query Flow:
    1. User query → Weaviate (semantic search for similar past situations)
    2. Extract execution_ids from Weaviate results
    3. Neo4j lookup (delegation chains for those executions)
    4. Combine results → Rich context with BOTH semantic AND structural insights
    """

    def __init__(self, rag_system=None, graph_store=None):
        """
        Initialize Hybrid GraphRAG.

        Args:
            rag_system: Weaviate RAG system (MultiAgentRAG)
            graph_store: Neo4j graph store (DelegationGraphStore)
        """
        self.rag = rag_system
        self.graph = graph_store

        # Verify both systems are available
        self.weaviate_enabled = rag_system is not None
        self.neo4j_enabled = graph_store is not None

        if not self.weaviate_enabled:
            logger.warning("Weaviate RAG not available. Semantic search disabled.")
        if not self.neo4j_enabled:
            logger.warning("Neo4j not available. Graph queries disabled.")

    def query(
        self,
        agent_type: str,
        context: Dict[str, Any],
        task_type: Optional[str] = None,
        include_delegation_patterns: bool = True
    ) -> Dict[str, Any]:
        """
        Hybrid query combining Weaviate and Neo4j.

        Args:
            agent_type: Type of agent (qa, devops, etc.)
            context: Current execution context
            task_type: Type of task for delegation pattern matching
            include_delegation_patterns: Whether to include Neo4j delegation insights

        Returns:
            Combined results from both Weaviate and Neo4j
        """
        result = {
            "weaviate_insights": [],
            "neo4j_patterns": [],
            "combined_recommendations": [],
            "sources": []
        }

        # Step 1: Query Weaviate for semantic similarity
        if self.weaviate_enabled:
            weaviate_results = self._query_weaviate(agent_type, context)
            result["weaviate_insights"] = weaviate_results["insights"]
            result["sources"].append("weaviate")

            # Extract execution IDs for Neo4j lookup
            execution_ids = [
                insight.get("execution_id")
                for insight in weaviate_results.get("insights", [])
                if insight.get("execution_id")
            ]
        else:
            execution_ids = []

        # Step 2: Query Neo4j for delegation patterns
        if self.neo4j_enabled and include_delegation_patterns:
            if task_type:
                # Query by task type
                neo4j_results = self._query_neo4j_by_task(task_type)
            elif execution_ids:
                # Query by execution IDs from Weaviate
                neo4j_results = self._query_neo4j_by_executions(execution_ids)
            else:
                neo4j_results = []

            result["neo4j_patterns"] = neo4j_results
            if neo4j_results:
                result["sources"].append("neo4j")

        # Step 3: Combine and synthesize recommendations
        result["combined_recommendations"] = self._synthesize_recommendations(
            result["weaviate_insights"],
            result["neo4j_patterns"]
        )

        return result

    def _query_weaviate(self, agent_type: str, context: Dict[str, Any]) -> Dict:
        """
        Query Weaviate for semantically similar past executions.

        Returns:
            Weaviate query results with semantic insights
        """
        try:
            # Use existing RAG system's augment_agent_context method
            augmented_context = self.rag.augment_agent_context(agent_type, context)

            insights = []
            for rec in augmented_context.get("rag_recommendations", []):
                # Extract execution_id from metadata if available
                execution_id = rec.get("metadata", {}).get("execution_id")
                insights.append({
                    "insight": rec.get("insight", ""),
                    "confidence": rec.get("confidence", 0.0),
                    "execution_id": execution_id,
                    "source": "weaviate"
                })

            return {
                "insights": insights,
                "insights_count": len(insights)
            }

        except Exception as e:
            logger.error(f"Weaviate query failed: {e}")
            return {"insights": [], "insights_count": 0}

    def _query_neo4j_by_task(self, task_type: str, limit: int = 5) -> List[Dict]:
        """
        Query Neo4j for delegation patterns by task type.

        Returns:
            List of historical delegation patterns
        """
        try:
            # Use graph store's method
            history = self.graph.get_delegation_history_for_task(
                task_type=task_type,
                status="success",
                limit=limit
            )

            patterns = []
            for record in history:
                patterns.append({
                    "from_agent": record.get("from_agent"),
                    "to_agent": record.get("to_agent"),
                    "task": record.get("task"),
                    "result": record.get("result"),
                    "duration_ms": record.get("duration_ms"),
                    "source": "neo4j",
                    "pattern_type": "delegation_success"
                })

            return patterns

        except Exception as e:
            logger.error(f"Neo4j task query failed: {e}")
            return []

    def _query_neo4j_by_executions(self, execution_ids: List[str]) -> List[Dict]:
        """
        Query Neo4j for delegation chains involving specific executions.

        Returns:
            List of delegation patterns for those executions
        """
        try:
            # Query Neo4j for delegation chains related to these executions
            # This would require a new graph store method - placeholder for now
            patterns = []

            # For each execution ID, get its delegation context
            for execution_id in execution_ids[:5]:  # Limit to top 5
                # TODO: Implement graph_store.get_delegation_context_for_execution
                # For now, this is a placeholder
                patterns.append({
                    "execution_id": execution_id,
                    "source": "neo4j",
                    "pattern_type": "execution_context"
                })

            return patterns

        except Exception as e:
            logger.error(f"Neo4j execution query failed: {e}")
            return []

    def _synthesize_recommendations(
        self,
        weaviate_insights: List[Dict],
        neo4j_patterns: List[Dict]
    ) -> List[Dict]:
        """
        Synthesize recommendations from both Weaviate and Neo4j.

        Combines:
        - Semantic insights (Weaviate): "Similar situations"
        - Structural patterns (Neo4j): "Successful collaboration paths"

        Returns:
            Combined recommendations with confidence scores
        """
        recommendations = []

        # Process Weaviate insights
        for insight in weaviate_insights:
            if insight["confidence"] > 0.7:
                recommendations.append({
                    "type": "semantic_insight",
                    "recommendation": insight["insight"],
                    "confidence": insight["confidence"],
                    "source": "weaviate"
                })

        # Process Neo4j patterns
        delegation_recommendations = self._extract_delegation_recommendations(neo4j_patterns)
        recommendations.extend(delegation_recommendations)

        # Sort by confidence
        recommendations.sort(key=lambda x: x.get("confidence", 0.0), reverse=True)

        return recommendations

    def _extract_delegation_recommendations(self, patterns: List[Dict]) -> List[Dict]:
        """
        Extract actionable recommendations from Neo4j delegation patterns.

        Returns:
            List of recommendations based on structural patterns
        """
        recommendations = []

        # Group by (from_agent, to_agent) pairs
        agent_pairs = {}
        for pattern in patterns:
            if pattern.get("pattern_type") == "delegation_success":
                key = (pattern.get("from_agent"), pattern.get("to_agent"))
                if key not in agent_pairs:
                    agent_pairs[key] = {
                        "count": 0,
                        "total_duration": 0,
                        "from_agent": pattern.get("from_agent"),
                        "to_agent": pattern.get("to_agent")
                    }
                agent_pairs[key]["count"] += 1
                agent_pairs[key]["total_duration"] += pattern.get("duration_ms", 0)

        # Generate recommendations from patterns
        for pair, stats in agent_pairs.items():
            if stats["count"] >= 2:  # At least 2 successful delegations
                avg_duration = stats["total_duration"] / stats["count"]
                confidence = min(0.9, 0.5 + (stats["count"] * 0.1))  # Max 0.9

                recommendations.append({
                    "type": "delegation_pattern",
                    "recommendation": f"Delegate to {stats['to_agent']} (successful {stats['count']} times, avg {avg_duration:.0f}ms)",
                    "confidence": confidence,
                    "source": "neo4j",
                    "metadata": {
                        "from_agent": stats["from_agent"],
                        "to_agent": stats["to_agent"],
                        "success_count": stats["count"],
                        "avg_duration_ms": avg_duration
                    }
                })

        return recommendations

    def recommend_delegation_target(
        self,
        from_agent: str,
        task_context: Dict[str, Any],
        task_type: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Recommend which agent to delegate to using hybrid GraphRAG.

        Combines:
        1. Weaviate: Semantic similarity to past successful tasks
        2. Neo4j: Historical delegation patterns and success rates

        Args:
            from_agent: Agent considering delegation
            task_context: Current task context
            task_type: Optional task type for pattern matching

        Returns:
            Recommendation with confidence score and reasoning, or None
        """
        # Step 1: Query both systems
        hybrid_results = self.query(
            agent_type=from_agent,
            context=task_context,
            task_type=task_type,
            include_delegation_patterns=True
        )

        # Step 2: Extract top recommendation
        recommendations = hybrid_results.get("combined_recommendations", [])
        if not recommendations:
            return None

        # Get highest confidence recommendation
        top_rec = recommendations[0]

        # Step 3: If it's a delegation pattern from Neo4j, enhance with graph query
        if top_rec.get("type") == "delegation_pattern" and self.neo4j_enabled:
            metadata = top_rec.get("metadata", {})
            to_agent = metadata.get("to_agent")

            if to_agent:
                # Get detailed stats from Neo4j
                neo4j_rec = self.graph.recommend_delegation_target(
                    from_agent=from_agent,
                    task_type=task_type or "general",
                    acceptable_duration_ms=5000.0
                )

                if neo4j_rec:
                    return {
                        "recommended_agent": neo4j_rec["recommended_agent"],
                        "confidence": top_rec["confidence"],
                        "reasoning": top_rec["recommendation"],
                        "success_count": neo4j_rec["success_count"],
                        "avg_duration_ms": neo4j_rec["avg_duration"],
                        "sources": ["weaviate", "neo4j"],
                        "hybrid": True
                    }

        # Return top recommendation as-is
        return {
            "recommendation": top_rec.get("recommendation"),
            "confidence": top_rec.get("confidence"),
            "source": top_rec.get("source"),
            "hybrid": len(hybrid_results.get("sources", [])) > 1
        }


def create_hybrid_rag(rag_system=None, graph_store=None) -> HybridGraphRAG:
    """
    Factory function to create HybridGraphRAG instance.

    Args:
        rag_system: Optional Weaviate RAG system
        graph_store: Optional Neo4j graph store

    Returns:
        Configured HybridGraphRAG instance
    """
    # Auto-initialize if not provided
    if rag_system is None:
        try:
            from agenticqa.rag.config import create_rag_system
            rag_system = create_rag_system()
        except Exception as e:
            logger.warning(f"Could not initialize Weaviate RAG: {e}")

    if graph_store is None:
        try:
            from agenticqa.graph import DelegationGraphStore
            graph_store = DelegationGraphStore()
            graph_store.connect()
        except Exception as e:
            logger.warning(f"Could not initialize Neo4j: {e}")

    return HybridGraphRAG(rag_system=rag_system, graph_store=graph_store)

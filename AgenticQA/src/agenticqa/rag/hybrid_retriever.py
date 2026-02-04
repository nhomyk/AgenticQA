"""
Hybrid RAG Retriever - Combines Vector and Relational Stores

Architecture:
- Vector Store (Weaviate): Unstructured data, semantic search
- Relational Store (SQLite/PostgreSQL): Structured data, exact queries
- Provides fallback when Weaviate unavailable
- Optimizes cost (relational DB cheaper for structured data)
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging

from .weaviate_store import WeaviateVectorStore, VectorDocument
from .relational_store import RelationalStore, PostgreSQLStore, StructuredMetric
from .embeddings import Embedder


@dataclass
class HybridResult:
    """Result from hybrid search"""

    content: str
    source: str  # 'vector' or 'relational'
    confidence: float
    metadata: Dict[str, Any]


class HybridRAG:
    """
    Hybrid RAG system combining vector and relational databases.

    Smart routing:
    - Structured queries (metrics, counts) → Relational DB
    - Semantic queries (errors, patterns) → Vector DB
    - Fallback to relational if vector DB unavailable
    """

    def __init__(
        self,
        vector_store: Optional[WeaviateVectorStore] = None,
        relational_store: Optional[RelationalStore] = None,
        embedder: Optional[Embedder] = None,
        use_postgresql: bool = False
    ):
        """
        Initialize hybrid RAG.

        Args:
            vector_store: Weaviate vector store (optional)
            relational_store: Relational store (optional)
            embedder: Text embedder
            use_postgresql: Use PostgreSQL instead of SQLite
        """
        self.logger = logging.getLogger(__name__)

        # Vector store (optional - for semantic search)
        self.vector_store = vector_store
        self.vector_available = vector_store is not None

        # Relational store (always available - for structured queries)
        if relational_store is None:
            if use_postgresql:
                try:
                    self.relational_store = PostgreSQLStore()
                except Exception as e:
                    self.logger.warning(f"PostgreSQL unavailable: {e}. Falling back to SQLite")
                    self.relational_store = RelationalStore()
            else:
                self.relational_store = RelationalStore()
        else:
            self.relational_store = relational_store

        self.embedder = embedder

    def store_document(
        self,
        content: str,
        doc_type: str,
        metadata: Dict[str, Any],
        embedding: Optional[List[float]] = None
    ) -> str:
        """
        Store document in appropriate database(s).

        Smart routing:
        - Unstructured content → Vector store (if available)
        - Structured metrics → Relational store (always)
        """
        doc_id = None

        # Always extract and store structured metrics
        self._store_structured_data(content, doc_type, metadata)

        # Store in vector store if available (for semantic search)
        if self.vector_available and self.vector_store:
            try:
                doc_id = self.vector_store.add_document(
                    content=content,
                    embedding=embedding or [],
                    metadata=metadata,
                    doc_type=doc_type
                )
            except Exception as e:
                self.logger.warning(f"Vector store failed: {e}. Data stored in relational DB.")

        return doc_id or metadata.get('run_id', 'unknown')

    def _store_structured_data(
        self,
        content: str,
        doc_type: str,
        metadata: Dict[str, Any]
    ):
        """Extract and store structured metrics"""
        run_id = metadata.get('run_id', 'unknown')
        agent_type = metadata.get('agent_type', 'unknown')
        timestamp = metadata.get('timestamp', '')

        # Extract numerical metrics based on doc_type
        if doc_type == 'test_result':
            # Extract test counts
            tests_passed = metadata.get('tests_passed', 0)
            tests_failed = metadata.get('tests_failed', 0)
            total_tests = tests_passed + tests_failed

            if total_tests > 0:
                pass_rate = tests_passed / total_tests
                self.relational_store.store_metric(
                    run_id=run_id,
                    agent_type=agent_type,
                    metric_type='test_result',
                    metric_name='pass_rate',
                    metric_value=pass_rate,
                    metadata={'passed': tests_passed, 'failed': tests_failed},
                    timestamp=timestamp
                )

        elif doc_type == 'coverage_report':
            # Extract coverage percentage
            coverage_pct = metadata.get('coverage_pct', 0)
            self.relational_store.store_metric(
                run_id=run_id,
                agent_type=agent_type,
                metric_type='coverage',
                metric_name='line_coverage',
                metric_value=coverage_pct,
                metadata=metadata,
                timestamp=timestamp
            )

        elif doc_type == 'security_audit':
            # Extract vulnerability counts
            vuln_count = metadata.get('vulnerability_count', 0)
            self.relational_store.store_metric(
                run_id=run_id,
                agent_type=agent_type,
                metric_type='security',
                metric_name='vulnerability_count',
                metric_value=vuln_count,
                metadata=metadata,
                timestamp=timestamp
            )

        elif doc_type == 'accessibility_fix':
            # Extract fix success rate
            success = metadata.get('success', False)
            self.relational_store.store_execution(
                run_id=run_id,
                agent_type='compliance',
                action='accessibility_fix',
                outcome='success' if success else 'failure',
                success=success,
                metadata=metadata,
                timestamp=timestamp
            )

    def search(
        self,
        query: str,
        agent_type: str,
        k: int = 5,
        threshold: float = 0.7,
        prefer_relational: bool = False
    ) -> List[HybridResult]:
        """
        Hybrid search across both stores.

        Args:
            query: Search query
            agent_type: Agent type for filtering
            k: Number of results
            threshold: Similarity threshold
            prefer_relational: Prefer relational DB for structured queries

        Returns:
            List of hybrid results from both stores
        """
        results = []

        # Determine query type (structured vs semantic)
        is_structured_query = self._is_structured_query(query)

        # Try relational store first for structured queries
        if is_structured_query or prefer_relational:
            results.extend(self._search_relational(query, agent_type, k))

        # Try vector store for semantic queries (if available)
        if not is_structured_query and self.vector_available:
            try:
                vector_results = self._search_vector(query, agent_type, k, threshold)
                results.extend(vector_results)
            except Exception as e:
                self.logger.warning(f"Vector search failed: {e}. Using relational only.")

        # If no results and haven't tried relational yet, try it as fallback
        if not results and not (is_structured_query or prefer_relational):
            results.extend(self._search_relational(query, agent_type, k))

        return results[:k]

    def _is_structured_query(self, query: str) -> bool:
        """Detect if query is for structured data"""
        structured_keywords = [
            'coverage', 'percent', 'rate', 'count', 'total',
            'average', 'metric', 'statistics', 'trend',
            'how many', 'what is the', 'latest', 'recent'
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in structured_keywords)

    def _search_relational(
        self,
        query: str,
        agent_type: str,
        k: int
    ) -> List[HybridResult]:
        """Search relational store"""
        results = []

        # Example: Extract metric queries
        if 'coverage' in query.lower():
            metrics = self.relational_store.query_metrics(
                agent_type=agent_type,
                metric_type='coverage',
                limit=k
            )
            for metric in metrics:
                results.append(HybridResult(
                    content=f"Coverage: {metric.metric_value:.1f}% (run: {metric.run_id})",
                    source='relational',
                    confidence=1.0,  # Exact match
                    metadata=metric.metadata
                ))

        elif 'success rate' in query.lower() or 'pass rate' in query.lower():
            rate, successes, total = self.relational_store.get_success_rate(
                agent_type=agent_type,
                limit=k
            )
            results.append(HybridResult(
                content=f"Success rate: {rate:.1%} ({successes}/{total} successful)",
                source='relational',
                confidence=1.0,
                metadata={'rate': rate, 'successes': successes, 'total': total}
            ))

        return results

    def _search_vector(
        self,
        query: str,
        agent_type: str,
        k: int,
        threshold: float
    ) -> List[HybridResult]:
        """Search vector store"""
        if not self.vector_store or not self.embedder:
            return []

        # Get embedding for query
        embedding = self.embedder.embed(query)

        # Search vector store
        doc_results = self.vector_store.search(
            embedding=embedding,
            doc_type=None,  # Search all types
            k=k,
            threshold=threshold
        )

        return [
            HybridResult(
                content=doc.content,
                source='vector',
                confidence=similarity,
                metadata=doc.metadata
            )
            for doc, similarity in doc_results
        ]

    def get_agent_context(
        self,
        agent_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Augment agent context with both structured and semantic data.

        Combines:
        - Recent metrics from relational DB
        - Semantic patterns from vector DB
        """
        augmented = context.copy()

        # Add structured metrics
        metrics_summary = self._get_metrics_summary(agent_type)
        augmented['structured_metrics'] = metrics_summary

        # Add semantic patterns (if vector available)
        if self.vector_available:
            # Get relevant patterns based on context
            query = context.get('query', '') or context.get('error', '')
            if query:
                patterns = self.search(query, agent_type, k=3)
                augmented['semantic_patterns'] = [
                    {'content': r.content, 'confidence': r.confidence}
                    for r in patterns
                ]

        return augmented

    def augment_agent_context(
        self,
        agent_type: str,
        agent_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Augment agent context with RAG-retrieved insights (MultiAgentRAG compatible).

        This method provides the same interface as MultiAgentRAG.augment_agent_context()
        but uses hybrid retrieval (vector + relational).
        """
        return self.get_agent_context(agent_type, agent_context)

    def log_agent_execution(self, agent_type: str, execution_result: Dict[str, Any]):
        """
        Log agent execution to both vector and relational stores (MultiAgentRAG compatible).

        Smart storage:
        - Structured metrics → Relational DB
        - Unstructured content → Vector DB (if available)
        """
        # Determine document type based on execution result
        doc_type = execution_result.get('doc_type', 'execution_result')

        # Extract content and metadata
        content = execution_result.get('content', str(execution_result))
        metadata = execution_result.copy()

        # Add agent type to metadata
        metadata['agent_type'] = agent_type

        # Store using hybrid system (handles routing automatically)
        self.store_document(
            content=content,
            doc_type=doc_type,
            metadata=metadata
        )

    def _get_metrics_summary(self, agent_type: str) -> Dict[str, Any]:
        """Get summary of recent metrics"""
        summary = {}

        # Coverage stats (if applicable)
        if agent_type in ['qa', 'sdet']:
            coverage_metrics = self.relational_store.query_metrics(
                agent_type=agent_type,
                metric_type='coverage',
                limit=10
            )
            if coverage_metrics:
                recent_coverage = coverage_metrics[0].metric_value
                summary['recent_coverage'] = f"{recent_coverage:.1f}%"

        # Success rate
        rate, successes, total = self.relational_store.get_success_rate(agent_type, limit=50)
        summary['success_rate'] = f"{rate:.1%}"
        summary['recent_executions'] = total

        return summary

    def close(self):
        """Close all database connections"""
        if self.vector_store:
            try:
                self.vector_store.close()
            except Exception:
                pass

        if self.relational_store:
            self.relational_store.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

"""
RAG Retriever for Agent Insights

Retrieves relevant historical data from vector store to enhance agent decision-making.
Provides semantic search over test results, errors, compliance rules, and performance patterns.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from .vector_store import VectorStore, VectorDocument
from .embeddings import Embedder, EmbedderFactory


@dataclass
class RetrievalResult:
    """Result from RAG retrieval"""
    document: VectorDocument
    similarity: float
    relevance_score: float
    insight: str


class RAGRetriever:
    """Retrieves relevant context for agent decision-making"""

    def __init__(self, vector_store: VectorStore, embedder: Embedder = None):
        self.vector_store = vector_store
        self.embedder = embedder or EmbedderFactory.get_default()

    def retrieve_similar_tests(
        self,
        test_name: str,
        test_type: str,
        k: int = 5
    ) -> List[RetrievalResult]:
        """Retrieve similar test results"""
        # Create query embedding
        query = f"{test_name} {test_type}"
        embedding = self.embedder.embed(query)

        # Search vector store
        similar_docs = self.vector_store.search(
            embedding,
            doc_type="test_result",
            k=k,
            threshold=0.5
        )

        # Convert to retrieval results
        results = []
        for doc, similarity in similar_docs:
            result = RetrievalResult(
                document=doc,
                similarity=similarity,
                relevance_score=similarity,
                insight=self._generate_test_insight(doc)
            )
            results.append(result)

        return results

    def retrieve_similar_errors(
        self,
        error_type: str,
        message: str,
        k: int = 5
    ) -> List[RetrievalResult]:
        """Retrieve similar errors and their resolutions"""
        # Create query embedding
        query = f"{error_type} {message}"
        embedding = self.embedder.embed(query)

        # Search vector store
        similar_docs = self.vector_store.search(
            embedding,
            doc_type="error",
            k=k,
            threshold=0.5
        )

        # Convert to retrieval results
        results = []
        for doc, similarity in similar_docs:
            result = RetrievalResult(
                document=doc,
                similarity=similarity,
                relevance_score=similarity,
                insight=self._generate_error_insight(doc)
            )
            results.append(result)

        return results

    def retrieve_applicable_compliance_rules(
        self,
        context: str,
        regulations: List[str] = None,
        k: int = 10
    ) -> List[RetrievalResult]:
        """Retrieve applicable compliance rules"""
        # Create query embedding
        query = context
        if regulations:
            query += " " + " ".join(regulations)
        
        embedding = self.embedder.embed(query)

        # Search vector store
        similar_docs = self.vector_store.search(
            embedding,
            doc_type="compliance_rule",
            k=k,
            threshold=0.4  # Lower threshold for compliance (catch more)
        )

        # Convert to retrieval results
        results = []
        for doc, similarity in similar_docs:
            result = RetrievalResult(
                document=doc,
                similarity=similarity,
                relevance_score=similarity,
                insight=self._generate_compliance_insight(doc)
            )
            results.append(result)

        return results

    def retrieve_performance_optimization_patterns(
        self,
        operation: str,
        current_metrics: Dict[str, float],
        k: int = 5
    ) -> List[RetrievalResult]:
        """Retrieve similar performance patterns and optimizations"""
        # Create query embedding
        query = f"{operation} performance optimization"
        embedding = self.embedder.embed(query)

        # Search vector store
        similar_docs = self.vector_store.search(
            embedding,
            doc_type="performance_pattern",
            k=k,
            threshold=0.5
        )

        # Convert to retrieval results
        results = []
        for doc, similarity in similar_docs:
            result = RetrievalResult(
                document=doc,
                similarity=similarity,
                relevance_score=similarity,
                insight=self._generate_performance_insight(doc, current_metrics)
            )
            results.append(result)

        return results

    def get_agent_recommendations(
        self,
        agent_type: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get AI-informed recommendations for an agent"""
        recommendations = []

        if agent_type == "qa":
            # Get similar test failures
            test_results = self.retrieve_similar_tests(
                context.get("test_name", ""),
                context.get("test_type", "")
            )
            
            for result in test_results:
                if result.similarity > 0.7:
                    recommendations.append({
                        "type": "test_pattern",
                        "insight": result.insight,
                        "confidence": result.similarity,
                        "source": result.document.metadata
                    })

        elif agent_type == "performance":
            # Get similar performance patterns
            patterns = self.retrieve_performance_optimization_patterns(
                context.get("operation", ""),
                context.get("current_metrics", {})
            )
            
            for result in patterns:
                if result.similarity > 0.6:
                    recommendations.append({
                        "type": "optimization",
                        "insight": result.insight,
                        "confidence": result.similarity,
                        "source": result.document.metadata
                    })

        elif agent_type == "compliance":
            # Get applicable compliance rules
            rules = self.retrieve_applicable_compliance_rules(
                context.get("context", ""),
                context.get("regulations", [])
            )
            
            for result in rules:
                if result.similarity > 0.5:
                    recommendations.append({
                        "type": "compliance_rule",
                        "insight": result.insight,
                        "confidence": result.similarity,
                        "source": result.document.metadata
                    })

        elif agent_type == "devops":
            # Get similar deployment patterns and errors
            errors = self.retrieve_similar_errors(
                context.get("error_type", ""),
                context.get("message", "")
            )
            
            for result in errors:
                if result.similarity > 0.6:
                    recommendations.append({
                        "type": "error_resolution",
                        "insight": result.insight,
                        "confidence": result.similarity,
                        "source": result.document.metadata
                    })

        return recommendations

    @staticmethod
    def _generate_test_insight(doc: VectorDocument) -> str:
        """Generate insight from test result document"""
        metadata = doc.metadata
        status = metadata.get("status", "unknown")
        
        if status == "failed":
            return f"Similar test failed: {metadata.get('error_message', 'Unknown error')}. Root cause: {metadata.get('root_cause', 'TBD')}"
        elif status == "flaky":
            return f"Flaky test pattern: {metadata.get('flakiness_percent', 'unknown')}% failure rate. Recommendation: {metadata.get('recommendation', 'Stabilize')}"
        else:
            return f"Test passed in similar scenario. Pattern: {metadata.get('pattern', 'No pattern')}"

    @staticmethod
    def _generate_error_insight(doc: VectorDocument) -> str:
        """Generate insight from error document"""
        metadata = doc.metadata
        return f"Similar error occurred {metadata.get('frequency', '?')} times. Resolution: {metadata.get('resolution', 'Unknown')}"

    @staticmethod
    def _generate_compliance_insight(doc: VectorDocument) -> str:
        """Generate insight from compliance rule document"""
        metadata = doc.metadata
        return f"Requirement: {metadata.get('requirement', 'Unknown')}. Validation: {metadata.get('validation_method', 'Unknown')}"

    @staticmethod
    def _generate_performance_insight(doc: VectorDocument, current: Dict[str, float]) -> str:
        """Generate insight from performance pattern document"""
        metadata = doc.metadata
        baseline = metadata.get('baseline_ms', 0)
        suggestion = metadata.get('optimization_suggestion', 'Profile code')
        return f"Similar operation baseline: {baseline}ms. Suggestion: {suggestion}"


class MultiAgentRAG:
    """Orchestrates RAG across all agents"""

    def __init__(self, vector_store: VectorStore, embedder: Embedder = None):
        self.vector_store = vector_store
        self.embedder = embedder or EmbedderFactory.get_default()
        self.retriever = RAGRetriever(vector_store, embedder)

    def augment_agent_context(
        self,
        agent_type: str,
        agent_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Augment agent context with RAG-retrieved insights
        
        This is the key method: keeps deterministic decisions, adds semantic insights
        """
        # Get recommendations from RAG
        recommendations = self.retriever.get_agent_recommendations(agent_type, agent_context)

        # Add to context
        augmented_context = agent_context.copy()
        augmented_context["rag_recommendations"] = recommendations
        augmented_context["rag_insights_count"] = len(recommendations)

        # Add high-confidence insights
        high_confidence = [r for r in recommendations if r["confidence"] > 0.75]
        if high_confidence:
            augmented_context["high_confidence_insights"] = high_confidence

        return augmented_context

    def log_agent_execution(
        self,
        agent_type: str,
        execution_result: Dict[str, Any]
    ):
        """Log agent execution to vector store for future learning"""
        if agent_type == "qa":
            self._log_test_result(execution_result)
        elif agent_type == "performance":
            self._log_performance_pattern(execution_result)
        elif agent_type == "compliance":
            self._log_compliance_check(execution_result)
        elif agent_type == "devops":
            self._log_deployment_result(execution_result)

    def _log_test_result(self, result: Dict[str, Any]):
        """Log test result to vector store"""
        from .embeddings import TestResultEmbedder
        
        embedder = TestResultEmbedder(self.embedder)
        embedding = embedder.embed_test_result(result)

        self.vector_store.add_document(
            content=f"{result.get('test_name', '')} {result.get('status', '')}",
            embedding=embedding,
            metadata=result,
            doc_type="test_result"
        )

    def _log_performance_pattern(self, result: Dict[str, Any]):
        """Log performance pattern to vector store"""
        from .embeddings import PerformancePatternEmbedder
        
        embedder = PerformancePatternEmbedder(self.embedder)
        embedding = embedder.embed_pattern(result)

        self.vector_store.add_document(
            content=f"{result.get('operation', '')} performance {result.get('baseline_ms', '')}ms",
            embedding=embedding,
            metadata=result,
            doc_type="performance_pattern"
        )

    def _log_compliance_check(self, result: Dict[str, Any]):
        """Log compliance check to vector store"""
        from .embeddings import ComplianceRuleEmbedder
        
        embedder = ComplianceRuleEmbedder(self.embedder)
        embedding = embedder.embed_rule(result)

        self.vector_store.add_document(
            content=f"{result.get('rule_name', '')} {result.get('regulation', '')}",
            embedding=embedding,
            metadata=result,
            doc_type="compliance_rule"
        )

    def _log_deployment_result(self, result: Dict[str, Any]):
        """Log deployment result to vector store"""
        from .embeddings import ErrorEmbedder
        
        if result.get("status") == "failed":
            embedder = ErrorEmbedder(self.embedder)
            embedding = embedder.embed_error(result)

            self.vector_store.add_document(
                content=f"{result.get('error_type', '')} {result.get('message', '')}",
                embedding=embedding,
                metadata=result,
                doc_type="error"
            )

"""
Embeddings Generator for RAG

Creates embeddings from test results, errors, compliance rules, and performance data.
Uses simple hashing-based approach for lightweight, deterministic embeddings.
Can be extended with ML-based embeddings if needed.
"""

import hashlib
import json
from typing import List, Dict, Any
from abc import ABC, abstractmethod


class Embedder(ABC):
    """Base class for embedding generators"""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Generate embedding for text"""
        pass


class SimpleHashEmbedder(Embedder):
    """
    Lightweight embedder using hash-based features.
    Fast and deterministic, suitable for agent orchestration.
    
    Creates 768-dimensional vectors from text features:
    - Character n-grams
    - Word frequencies
    - Syntax patterns
    """

    def __init__(self, embedding_dim: int = 768):
        self.embedding_dim = embedding_dim

    def embed(self, text: str) -> List[float]:
        """Generate embedding from text"""
        # Normalize text
        text = text.lower().strip()
        
        # Extract features
        features = self._extract_features(text)
        
        # Convert to embedding
        embedding = self._features_to_embedding(features)
        
        return embedding

    def _extract_features(self, text: str) -> Dict[str, float]:
        """Extract features from text"""
        features = {}

        # Character n-grams
        for n in [2, 3, 4]:
            for i in range(len(text) - n + 1):
                ngram = text[i:i+n]
                features[f"char_{n}_{ngram}"] = features.get(f"char_{n}_{ngram}", 0) + 1

        # Word frequencies
        words = text.split()
        for word in words:
            features[f"word_{word}"] = features.get(f"word_{word}", 0) + 1

        # Syntax patterns
        if "error" in text:
            features["pattern_error"] = 1
        if "fail" in text:
            features["pattern_fail"] = 1
        if "pass" in text:
            features["pattern_pass"] = 1
        if "timeout" in text:
            features["pattern_timeout"] = 1
        if "compliance" in text or "require" in text:
            features["pattern_compliance"] = 1

        return features

    def _features_to_embedding(self, features: Dict[str, float]) -> List[float]:
        """Convert features to embedding vector"""
        # Use hash-based bucketing to convert features to fixed-dim vector
        embedding = [0.0] * self.embedding_dim

        for feature_name, count in features.items():
            # Hash feature to bucket
            hash_val = int(hashlib.md5(feature_name.encode()).hexdigest(), 16)
            bucket = hash_val % self.embedding_dim
            
            # Add count to bucket
            embedding[bucket] += count

        # Normalize
        max_val = max(embedding) if max(embedding) > 0 else 1
        embedding = [x / max_val for x in embedding]

        return embedding


class SemanticEmbedder(Embedder):
    """
    ML-based embedder for semantic understanding.
    
    Can use sentence-transformers for better semantic similarity.
    Falls back to SimpleHashEmbedder if transformers unavailable.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self._try_load_model()

        if self.model is None:
            # Fallback to simple embedder
            self.fallback = SimpleHashEmbedder()
            self._use_fallback = True
        else:
            self._use_fallback = False

    def embed(self, text: str) -> List[float]:
        """Generate semantic embedding"""
        if self._use_fallback:
            return self.fallback.embed(text)

        # Use actual embedder
        embedding = self.model.encode(text, convert_to_tensor=False)
        return embedding.tolist()

    def _try_load_model(self):
        """Try to load sentence-transformers model"""
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
        except ImportError:
            # Silently fall back if transformers not available
            pass


class EmbedderFactory:
    """Factory for creating embedders"""

    _embedder_instance = None

    @classmethod
    def get_embedder(cls, embedder_type: str = "simple") -> Embedder:
        """Get embedder instance"""
        if embedder_type == "simple":
            return SimpleHashEmbedder()
        elif embedder_type == "semantic":
            return SemanticEmbedder()
        else:
            raise ValueError(f"Unknown embedder type: {embedder_type}")

    @classmethod
    def set_default(cls, embedder: Embedder):
        """Set default embedder"""
        cls._embedder_instance = embedder

    @classmethod
    def get_default(cls) -> Embedder:
        """Get default embedder"""
        if cls._embedder_instance is None:
            cls._embedder_instance = SimpleHashEmbedder()
        return cls._embedder_instance


class TestResultEmbedder:
    """Embedder for test results"""

    def __init__(self, embedder: Embedder = None):
        self.embedder = embedder or EmbedderFactory.get_default()

    def embed_test_result(self, test_result: Dict[str, Any]) -> List[float]:
        """Embed a test result"""
        # Create a text representation
        text_parts = [
            test_result.get("test_name", ""),
            test_result.get("status", ""),
            test_result.get("error_message", ""),
            test_result.get("test_type", ""),
        ]
        
        text = " ".join([str(p) for p in text_parts if p])
        return self.embedder.embed(text)


class ErrorEmbedder:
    """Embedder for errors and exceptions"""

    def __init__(self, embedder: Embedder = None):
        self.embedder = embedder or EmbedderFactory.get_default()

    def embed_error(self, error_info: Dict[str, Any]) -> List[float]:
        """Embed an error"""
        text_parts = [
            error_info.get("error_type", ""),
            error_info.get("message", ""),
            error_info.get("stack_trace", ""),
            error_info.get("context", ""),
        ]

        text = " ".join([str(p) for p in text_parts if p])
        return self.embedder.embed(text)


class ComplianceRuleEmbedder:
    """Embedder for compliance rules"""

    def __init__(self, embedder: Embedder = None):
        self.embedder = embedder or EmbedderFactory.get_default()

    def embed_rule(self, rule: Dict[str, Any]) -> List[float]:
        """Embed a compliance rule"""
        text_parts = [
            rule.get("name", ""),
            rule.get("description", ""),
            rule.get("regulation", ""),
            rule.get("requirements", ""),
        ]

        text = " ".join([str(p) for p in text_parts if p])
        return self.embedder.embed(text)


class PerformancePatternEmbedder:
    """Embedder for performance patterns"""

    def __init__(self, embedder: Embedder = None):
        self.embedder = embedder or EmbedderFactory.get_default()

    def embed_pattern(self, pattern: Dict[str, Any]) -> List[float]:
        """Embed a performance pattern"""
        text_parts = [
            pattern.get("operation", ""),
            f"baseline: {pattern.get('baseline_ms', '')}",
            f"regression: {pattern.get('regression_percent', '')}",
            pattern.get("optimization_suggestion", ""),
        ]

        text = " ".join([str(p) for p in text_parts if p])
        return self.embedder.embed(text)

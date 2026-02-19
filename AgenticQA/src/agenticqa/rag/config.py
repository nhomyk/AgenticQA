"""
RAG Configuration Management

Handles environment-based initialization for both local development and cloud production.
Supports local Docker, Weaviate Cloud, and custom deployments.
"""

import os
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass


class DeploymentMode(Enum):
    """Deployment environment modes"""

    LOCAL = "local"  # Local Docker Weaviate
    CLOUD = "cloud"  # Weaviate Cloud
    CUSTOM = "custom"  # Custom Weaviate endpoint


class VectorProvider(Enum):
    """Supported vector database providers"""

    WEAVIATE = "weaviate"
    QDRANT = "qdrant"


@dataclass
class WeaviateConfig:
    """Configuration for Weaviate connection"""

    mode: DeploymentMode
    host: str
    port: Optional[int]
    api_key: Optional[str]
    collection_name: str
    use_https: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for WeaviateVectorStore"""
        if self.mode == DeploymentMode.LOCAL:
            return {
                "host": self.host,
                "port": self.port,
                "collection_name": self.collection_name,
                "api_key": None,
            }
        else:
            # Cloud or custom - pass host and API key
            # WeaviateVectorStore._connect() will handle building the URL
            return {
                "host": self.host,
                "port": None,  # Not used for cloud
                "collection_name": self.collection_name,
                "api_key": self.api_key,
            }


@dataclass
class QdrantConfig:
    """Configuration for Qdrant connection"""

    host: str
    port: int
    api_key: Optional[str]
    collection_name: str
    use_https: bool = False
    url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "collection_name": self.collection_name,
            "api_key": self.api_key,
            "use_https": self.use_https,
            "url": self.url,
        }


class RAGConfig:
    """
    RAG Configuration Factory

    Reads from environment variables to determine deployment mode and credentials.
    """

    # Environment variable names
    ENV_MODE = "AGENTICQA_RAG_MODE"
    ENV_WEAVIATE_HOST = "WEAVIATE_HOST"
    ENV_WEAVIATE_PORT = "WEAVIATE_PORT"
    ENV_WEAVIATE_API_KEY = "WEAVIATE_API_KEY"
    ENV_WEAVIATE_COLLECTION = "WEAVIATE_COLLECTION"
    ENV_HYBRID_RAG = "AGENTICQA_HYBRID_RAG"
    ENV_USE_POSTGRESQL = "AGENTICQA_USE_POSTGRESQL"
    ENV_VECTOR_PROVIDER = "AGENTICQA_VECTOR_PROVIDER"
    ENV_QDRANT_HOST = "QDRANT_HOST"
    ENV_QDRANT_PORT = "QDRANT_PORT"
    ENV_QDRANT_API_KEY = "QDRANT_API_KEY"
    ENV_QDRANT_COLLECTION = "QDRANT_COLLECTION"
    ENV_QDRANT_HTTPS = "QDRANT_USE_HTTPS"
    ENV_QDRANT_URL = "QDRANT_URL"
    ENV_VECTOR_DUAL_WRITE = "AGENTICQA_VECTOR_DUAL_WRITE"
    ENV_VECTOR_SECONDARY_PROVIDER = "AGENTICQA_VECTOR_SECONDARY_PROVIDER"
    ENV_VECTOR_AUTO_FALLBACK = "AGENTICQA_VECTOR_AUTO_FALLBACK"

    @staticmethod
    def get_vector_provider() -> VectorProvider:
        """Get vector DB provider from environment"""
        provider_str = os.getenv(RAGConfig.ENV_VECTOR_PROVIDER, "weaviate").lower()
        try:
            return VectorProvider(provider_str)
        except ValueError:
            return VectorProvider.WEAVIATE

    @staticmethod
    def get_deployment_mode() -> DeploymentMode:
        """Get deployment mode from environment"""
        mode_str = os.getenv(RAGConfig.ENV_MODE, "local").lower()
        try:
            return DeploymentMode(mode_str)
        except ValueError:
            return DeploymentMode.LOCAL

    @staticmethod
    def get_weaviate_config() -> WeaviateConfig:
        """
        Get Weaviate configuration from environment variables.

        Supports three modes:

        **Local Mode (Default):**
            - AGENTICQA_RAG_MODE=local
            - WEAVIATE_HOST=localhost (default)
            - WEAVIATE_PORT=8080 (default)

        **Cloud Mode (Weaviate Cloud):**
            - AGENTICQA_RAG_MODE=cloud
            - WEAVIATE_HOST=cluster-name.weaviate.network
            - WEAVIATE_API_KEY=your-api-key (required)

        **Custom Mode (Self-hosted or other endpoints):**
            - AGENTICQA_RAG_MODE=custom
            - WEAVIATE_HOST=your-host.example.com
            - WEAVIATE_PORT=8080 (optional)
            - WEAVIATE_API_KEY=your-api-key (if needed)

        Returns:
            WeaviateConfig with connection parameters

        Example:
            ```python
            config = RAGConfig.get_weaviate_config()
            from agenticqa.rag import WeaviateVectorStore

            store = WeaviateVectorStore(**config.to_dict())
            ```
        """
        mode = RAGConfig.get_deployment_mode()

        # Default values based on mode
        if mode == DeploymentMode.LOCAL:
            host = os.getenv(RAGConfig.ENV_WEAVIATE_HOST, "localhost")
            port = int(os.getenv(RAGConfig.ENV_WEAVIATE_PORT, "8080"))
            api_key = None
        else:
            # Cloud or custom - requires host
            host = os.getenv(RAGConfig.ENV_WEAVIATE_HOST)
            if not host:
                raise ValueError(
                    f"WEAVIATE_HOST is required for {mode.value} mode. "
                    f"Set environment variable: export WEAVIATE_HOST=your-host"
                )
            port = None  # Not used for cloud/custom
            api_key = os.getenv(RAGConfig.ENV_WEAVIATE_API_KEY)

        collection = os.getenv(RAGConfig.ENV_WEAVIATE_COLLECTION, "AgenticQADocuments")

        return WeaviateConfig(
            mode=mode,
            host=host,
            port=port,
            api_key=api_key,
            collection_name=collection,
            use_https=(mode in [DeploymentMode.CLOUD, DeploymentMode.CUSTOM]),
        )

    @staticmethod
    def get_qdrant_config() -> QdrantConfig:
        """Get Qdrant configuration from environment variables."""
        host = os.getenv(RAGConfig.ENV_QDRANT_HOST, "localhost")
        port = int(os.getenv(RAGConfig.ENV_QDRANT_PORT, "6333"))
        api_key = os.getenv(RAGConfig.ENV_QDRANT_API_KEY)
        collection = os.getenv(RAGConfig.ENV_QDRANT_COLLECTION, "AgenticQADocuments")
        use_https = os.getenv(RAGConfig.ENV_QDRANT_HTTPS, "false").lower() in [
            "true",
            "1",
            "yes",
        ]
        url = os.getenv(RAGConfig.ENV_QDRANT_URL)

        return QdrantConfig(
            host=host,
            port=port,
            api_key=api_key,
            collection_name=collection,
            use_https=use_https,
            url=url,
        )

    @staticmethod
    def validate_cloud_config() -> bool:
        """
        Validate cloud configuration is properly set.

        Returns:
            True if valid, False if issues found

        Raises:
            ValueError with detailed error message if configuration is invalid
        """
        mode = RAGConfig.get_deployment_mode()

        if mode == DeploymentMode.LOCAL:
            return True

        # Cloud or custom - must have host and API key
        host = os.getenv(RAGConfig.ENV_WEAVIATE_HOST)
        if not host:
            raise ValueError(
                f"Missing WEAVIATE_HOST for {mode.value} deployment. "
                f"Set: export WEAVIATE_HOST=cluster-name.weaviate.network"
            )

        if mode == DeploymentMode.CLOUD:
            api_key = os.getenv(RAGConfig.ENV_WEAVIATE_API_KEY)
            if not api_key:
                raise ValueError(
                    "Missing WEAVIATE_API_KEY for cloud deployment. "
                    "Set: export WEAVIATE_API_KEY=your-api-key"
                )

        return True

    @staticmethod
    def is_hybrid_rag_enabled() -> bool:
        """Check if hybrid RAG mode is enabled"""
        return os.getenv(RAGConfig.ENV_HYBRID_RAG, "false").lower() in ["true", "1", "yes"]

    @staticmethod
    def use_postgresql() -> bool:
        """Check if PostgreSQL should be used instead of SQLite"""
        return os.getenv(RAGConfig.ENV_USE_POSTGRESQL, "false").lower() in ["true", "1", "yes"]

    @staticmethod
    def is_dual_write_enabled() -> bool:
        """Check if dual-write replication is enabled."""
        return os.getenv(RAGConfig.ENV_VECTOR_DUAL_WRITE, "false").lower() in [
            "true",
            "1",
            "yes",
        ]

    @staticmethod
    def get_secondary_provider(primary: VectorProvider) -> Optional[VectorProvider]:
        """Get secondary provider for dual-write mode."""
        secondary_str = os.getenv(RAGConfig.ENV_VECTOR_SECONDARY_PROVIDER)

        if not secondary_str:
            return (
                VectorProvider.QDRANT
                if primary == VectorProvider.WEAVIATE
                else VectorProvider.WEAVIATE
            )

        try:
            secondary = VectorProvider(secondary_str.lower())
        except ValueError:
            return None

        if secondary == primary:
            return None

        return secondary

    @staticmethod
    def is_auto_fallback_enabled() -> bool:
        """Check if automatic provider fallback is enabled when primary is unavailable."""
        return os.getenv(RAGConfig.ENV_VECTOR_AUTO_FALLBACK, "true").lower() in [
            "true",
            "1",
            "yes",
        ]

    @staticmethod
    def print_config_summary() -> str:
        """
        Print configuration summary (safe, no secrets).

        Returns:
            String summary of current configuration
        """
        provider = RAGConfig.get_vector_provider()
        mode = RAGConfig.get_deployment_mode()
        hybrid_enabled = RAGConfig.is_hybrid_rag_enabled()
        use_pg = RAGConfig.use_postgresql()

        summary = f"""
RAG Configuration Summary
========================
Vector Provider: {provider.value.upper()}
    Dual Write: {'ENABLED' if RAGConfig.is_dual_write_enabled() else 'DISABLED'}
Mode: {mode.value.upper()}
Hybrid RAG: {'ENABLED' if hybrid_enabled else 'DISABLED'}

"""

        if provider == VectorProvider.WEAVIATE:
            config = RAGConfig.get_weaviate_config()
            summary += f"Collection: {config.collection_name}\n"
            if mode == DeploymentMode.LOCAL:
                summary += f"Host: {config.host}:{config.port}\n"
            else:
                summary += f"Host: {config.host}\n"
                summary += f"API Key: {'***' if config.api_key else 'Not Set'}\n"
        else:
            config = RAGConfig.get_qdrant_config()
            summary += f"Collection: {config.collection_name}\n"
            if config.url:
                summary += f"URL: {config.url}\n"
            else:
                summary += f"Host: {config.host}:{config.port}\n"
            summary += f"API Key: {'***' if config.api_key else 'Not Set'}\n"

        if hybrid_enabled:
            summary += f"\nRelational DB: {'PostgreSQL' if use_pg else 'SQLite'}\n"

        return summary


def create_vector_store_for_provider(provider: VectorProvider):
    """Create vector store instance for an explicit provider."""
    if provider == VectorProvider.QDRANT:
        from .qdrant_store import QdrantVectorStore

        config = RAGConfig.get_qdrant_config()
        return QdrantVectorStore(**config.to_dict())

    from .weaviate_store import WeaviateVectorStore

    RAGConfig.validate_cloud_config()
    config = RAGConfig.get_weaviate_config()
    return WeaviateVectorStore(**config.to_dict())


def create_vector_store():
    """Factory function to create vector store by provider."""
    provider = RAGConfig.get_vector_provider()
    selected_provider = provider

    try:
        primary_store = create_vector_store_for_provider(provider)
    except Exception as primary_exc:
        if not RAGConfig.is_auto_fallback_enabled():
            raise

        fallback_provider = (
            VectorProvider.QDRANT
            if provider == VectorProvider.WEAVIATE
            else VectorProvider.WEAVIATE
        )
        try:
            print(
                f"Warning: Primary vector store unavailable ({provider.value}): {primary_exc}. "
                f"Falling back to {fallback_provider.value}."
            )
            primary_store = create_vector_store_for_provider(fallback_provider)
            selected_provider = fallback_provider
        except Exception as fallback_exc:
            raise RuntimeError(
                "Failed to initialize vector store. "
                f"Primary ({provider.value}) error: {primary_exc}. "
                f"Fallback ({fallback_provider.value}) error: {fallback_exc}."
            )

    if not RAGConfig.is_dual_write_enabled():
        return primary_store

    secondary_provider = RAGConfig.get_secondary_provider(selected_provider)
    if secondary_provider is None:
        return primary_store

    try:
        secondary_store = create_vector_store_for_provider(secondary_provider)
    except Exception as exc:
        print(
            f"Warning: Secondary vector store unavailable ({secondary_provider.value}): {exc}. "
            "Continuing with primary store only."
        )
        return primary_store

    from .dual_write_store import DualWriteVectorStore

    return DualWriteVectorStore(
        primary_store=primary_store,
        secondary_store=secondary_store,
        primary_name=provider.value,
        secondary_name=secondary_provider.value,
    )


def create_rag_system():
    """
    Factory function to create RAG system with environment-based configuration.

    Returns:
        MultiAgentRAG or HybridRAG instance configured for current deployment mode

    Example:
        ```python
        # For local development
        export AGENTICQA_RAG_MODE=local
        rag = create_rag_system()

        # For cloud production
        export AGENTICQA_RAG_MODE=cloud
        export WEAVIATE_HOST=cluster-name.weaviate.network
        export WEAVIATE_API_KEY=your-api-key
        rag = create_rag_system()

        # For hybrid RAG (vector + relational)
        export AGENTICQA_HYBRID_RAG=true
        rag = create_rag_system()

        # For hybrid RAG with PostgreSQL
        export AGENTICQA_HYBRID_RAG=true
        export AGENTICQA_USE_POSTGRESQL=true
        rag = create_rag_system()
        ```
    """
    from .embeddings import EmbedderFactory

    # Create embedder (defaults to SimpleHashEmbedder)
    embedder = EmbedderFactory.get_default()

    # Check if hybrid RAG is enabled
    if RAGConfig.is_hybrid_rag_enabled():
        from .hybrid_retriever import HybridRAG
        from .relational_store import RelationalStore, PostgreSQLStore

        # Create vector store (optional - can be None if provider unavailable)
        try:
            vector_store = create_vector_store()
        except Exception as e:
            print(f"Warning: Vector store unavailable: {e}. Using relational DB only.")
            vector_store = None

        # Create relational store
        if RAGConfig.use_postgresql():
            try:
                relational_store = PostgreSQLStore()
            except Exception as e:
                print(f"Warning: PostgreSQL unavailable: {e}. Falling back to SQLite.")
                relational_store = RelationalStore()
        else:
            relational_store = RelationalStore()

        # Create and return hybrid RAG system
        return HybridRAG(
            vector_store=vector_store,
            relational_store=relational_store,
            embedder=embedder,
            use_postgresql=RAGConfig.use_postgresql()
        )
    else:
        # Standard RAG with vector store only
        from .retriever import MultiAgentRAG

        # Create vector store
        vector_store = create_vector_store()

        # Create and return standard RAG system
        return MultiAgentRAG(vector_store, embedder)

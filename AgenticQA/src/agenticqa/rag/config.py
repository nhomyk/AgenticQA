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
    def print_config_summary() -> str:
        """
        Print configuration summary (safe, no secrets).

        Returns:
            String summary of current configuration
        """
        mode = RAGConfig.get_deployment_mode()
        config = RAGConfig.get_weaviate_config()

        summary = f"""
RAG Configuration Summary
========================
Mode: {mode.value.upper()}
Collection: {config.collection_name}

"""

        if mode == DeploymentMode.LOCAL:
            summary += f"Host: {config.host}:{config.port}\n"
        else:
            summary += f"Host: {config.host}\n"
            summary += f"API Key: {'***' if config.api_key else 'Not Set'}\n"

        return summary


def create_rag_system():
    """
    Factory function to create RAG system with environment-based configuration.

    Returns:
        MultiAgentRAG instance configured for current deployment mode

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
        ```
    """
    from .weaviate_store import WeaviateVectorStore
    from .embeddings import EmbedderFactory
    from .retriever import MultiAgentRAG

    # Validate and get configuration
    RAGConfig.validate_cloud_config()
    config = RAGConfig.get_weaviate_config()

    # Create vector store
    vector_store = WeaviateVectorStore(**config.to_dict())

    # Create embedder (defaults to SimpleHashEmbedder)
    embedder = EmbedderFactory.get_default()

    # Create and return RAG system
    return MultiAgentRAG(vector_store, embedder)

"""Tests for vector provider routing and configuration."""

from unittest.mock import patch

from src.agenticqa.rag.config import RAGConfig, VectorProvider


class TestVectorProviderConfig:
    def test_default_provider_is_weaviate(self, monkeypatch):
        monkeypatch.delenv("AGENTICQA_VECTOR_PROVIDER", raising=False)
        assert RAGConfig.get_vector_provider() == VectorProvider.WEAVIATE

    def test_invalid_provider_falls_back_to_weaviate(self, monkeypatch):
        monkeypatch.setenv("AGENTICQA_VECTOR_PROVIDER", "unknown")
        assert RAGConfig.get_vector_provider() == VectorProvider.WEAVIATE

    def test_qdrant_config_reads_environment(self, monkeypatch):
        monkeypatch.setenv("QDRANT_HOST", "qdrant.local")
        monkeypatch.setenv("QDRANT_PORT", "6334")
        monkeypatch.setenv("QDRANT_API_KEY", "secret")
        monkeypatch.setenv("QDRANT_COLLECTION", "AgenticQADocuments")
        monkeypatch.setenv("QDRANT_USE_HTTPS", "true")

        config = RAGConfig.get_qdrant_config()

        assert config.host == "qdrant.local"
        assert config.port == 6334
        assert config.api_key == "secret"
        assert config.collection_name == "AgenticQADocuments"
        assert config.use_https is True

    def test_create_vector_store_uses_qdrant_provider(self, monkeypatch):
        monkeypatch.setenv("AGENTICQA_VECTOR_PROVIDER", "qdrant")

        with patch("src.agenticqa.rag.qdrant_store.QdrantVectorStore") as mocked_qdrant:
            from src.agenticqa.rag.config import create_vector_store

            create_vector_store()
            mocked_qdrant.assert_called_once()

    def test_create_vector_store_uses_weaviate_provider(self, monkeypatch):
        monkeypatch.setenv("AGENTICQA_VECTOR_PROVIDER", "weaviate")
        monkeypatch.setenv("AGENTICQA_RAG_MODE", "local")

        with patch("src.agenticqa.rag.weaviate_store.WeaviateVectorStore") as mocked_weaviate:
            from src.agenticqa.rag.config import create_vector_store

            create_vector_store()
            mocked_weaviate.assert_called_once()

    def test_create_vector_store_uses_dual_write_when_enabled(self, monkeypatch):
        monkeypatch.setenv("AGENTICQA_VECTOR_PROVIDER", "weaviate")
        monkeypatch.setenv("AGENTICQA_VECTOR_DUAL_WRITE", "true")
        monkeypatch.setenv("AGENTICQA_VECTOR_SECONDARY_PROVIDER", "qdrant")

        with patch("src.agenticqa.rag.config.create_vector_store_for_provider") as mocked_single:
            with patch("src.agenticqa.rag.dual_write_store.DualWriteVectorStore") as mocked_dual:
                from src.agenticqa.rag.config import create_vector_store

                mocked_single.side_effect = [object(), object()]
                create_vector_store()

                assert mocked_single.call_count == 2
                mocked_dual.assert_called_once()

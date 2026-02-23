import pytest

import agenticqa.rag.config as cfg


class _DummyStore:
    def __init__(self, name):
        self.name = name


def test_get_secondary_provider_and_invalid(monkeypatch):
    monkeypatch.delenv(cfg.RAGConfig.ENV_VECTOR_SECONDARY_PROVIDER, raising=False)
    assert cfg.RAGConfig.get_secondary_provider(cfg.VectorProvider.WEAVIATE) == cfg.VectorProvider.QDRANT

    monkeypatch.setenv(cfg.RAGConfig.ENV_VECTOR_SECONDARY_PROVIDER, "weaviate")
    assert cfg.RAGConfig.get_secondary_provider(cfg.VectorProvider.WEAVIATE) is None

    monkeypatch.setenv(cfg.RAGConfig.ENV_VECTOR_SECONDARY_PROVIDER, "invalid")
    assert cfg.RAGConfig.get_secondary_provider(cfg.VectorProvider.WEAVIATE) is None


def test_create_vector_store_auto_fallback_and_no_fallback(monkeypatch):
    monkeypatch.setattr(cfg.RAGConfig, "get_vector_provider", staticmethod(lambda: cfg.VectorProvider.WEAVIATE))

    calls = {"count": 0}

    def _factory(provider):
        calls["count"] += 1
        if provider == cfg.VectorProvider.WEAVIATE:
            raise RuntimeError("primary down")
        return _DummyStore("qdrant")

    monkeypatch.setattr(cfg, "create_vector_store_for_provider", _factory)
    monkeypatch.setattr(cfg.RAGConfig, "is_auto_fallback_enabled", staticmethod(lambda: True))
    monkeypatch.setattr(cfg.RAGConfig, "is_dual_write_enabled", staticmethod(lambda: False))

    store = cfg.create_vector_store()
    assert isinstance(store, _DummyStore)
    assert store.name == "qdrant"
    assert calls["count"] == 2

    monkeypatch.setattr(cfg.RAGConfig, "is_auto_fallback_enabled", staticmethod(lambda: False))
    with pytest.raises(RuntimeError):
        cfg.create_vector_store()


def test_create_vector_store_dual_write_paths(monkeypatch):
    monkeypatch.setattr(cfg.RAGConfig, "get_vector_provider", staticmethod(lambda: cfg.VectorProvider.WEAVIATE))
    monkeypatch.setattr(cfg.RAGConfig, "is_auto_fallback_enabled", staticmethod(lambda: True))
    monkeypatch.setattr(cfg.RAGConfig, "is_dual_write_enabled", staticmethod(lambda: True))

    primary = _DummyStore("primary")
    secondary = _DummyStore("secondary")

    monkeypatch.setattr(cfg, "create_vector_store_for_provider", lambda provider: primary if provider == cfg.VectorProvider.WEAVIATE else secondary)
    monkeypatch.setattr(cfg.RAGConfig, "get_secondary_provider", staticmethod(lambda p: cfg.VectorProvider.QDRANT))

    class _Dual:
        def __init__(self, primary_store, secondary_store, primary_name, secondary_name):
            self.primary_store = primary_store
            self.secondary_store = secondary_store
            self.primary_name = primary_name
            self.secondary_name = secondary_name

    import types
    fake_module = types.SimpleNamespace(DualWriteVectorStore=_Dual)
    monkeypatch.setitem(__import__("sys").modules, "agenticqa.rag.dual_write_store", fake_module)

    store = cfg.create_vector_store()
    assert isinstance(store, _Dual)

    # secondary unavailable should return primary
    def _factory_fail_secondary(provider):
        if provider == cfg.VectorProvider.WEAVIATE:
            return primary
        raise RuntimeError("secondary down")

    monkeypatch.setattr(cfg, "create_vector_store_for_provider", _factory_fail_secondary)
    store2 = cfg.create_vector_store()
    assert store2 is primary


def test_create_rag_system_hybrid_and_standard(monkeypatch):
    class _EmbedderFactory:
        @staticmethod
        def get_default():
            return "embedder"

    import types, sys
    monkeypatch.setitem(sys.modules, "agenticqa.rag.embeddings", types.SimpleNamespace(EmbedderFactory=_EmbedderFactory))

    monkeypatch.setattr(cfg.RAGConfig, "is_hybrid_rag_enabled", staticmethod(lambda: True))
    monkeypatch.setattr(cfg.RAGConfig, "use_postgresql", staticmethod(lambda: True))
    monkeypatch.setattr(cfg, "create_vector_store", lambda: (_ for _ in ()).throw(RuntimeError("no vector")))

    class _Rel:
        pass

    class _PG:
        def __init__(self):
            raise RuntimeError("pg down")

    class _Hybrid:
        def __init__(self, vector_store, relational_store, embedder, use_postgresql):
            self.vector_store = vector_store
            self.relational_store = relational_store
            self.embedder = embedder
            self.use_postgresql = use_postgresql

    monkeypatch.setitem(sys.modules, "agenticqa.rag.relational_store", types.SimpleNamespace(RelationalStore=_Rel, PostgreSQLStore=_PG))
    monkeypatch.setitem(sys.modules, "agenticqa.rag.hybrid_retriever", types.SimpleNamespace(HybridRAG=_Hybrid))

    rag = cfg.create_rag_system()
    assert isinstance(rag, _Hybrid)
    assert rag.vector_store is None

    # standard path
    monkeypatch.setattr(cfg.RAGConfig, "is_hybrid_rag_enabled", staticmethod(lambda: False))
    monkeypatch.setattr(cfg, "create_vector_store", lambda: "vector")

    class _Multi:
        def __init__(self, vector_store, embedder):
            self.vector_store = vector_store
            self.embedder = embedder

    monkeypatch.setitem(sys.modules, "agenticqa.rag.retriever", types.SimpleNamespace(MultiAgentRAG=_Multi))

    rag2 = cfg.create_rag_system()
    assert isinstance(rag2, _Multi)
    assert rag2.vector_store == "vector"


def test_validate_cloud_config_errors(monkeypatch):
    monkeypatch.setenv(cfg.RAGConfig.ENV_MODE, "cloud")
    monkeypatch.delenv(cfg.RAGConfig.ENV_WEAVIATE_HOST, raising=False)
    with pytest.raises(ValueError):
        cfg.RAGConfig.validate_cloud_config()

    monkeypatch.setenv(cfg.RAGConfig.ENV_WEAVIATE_HOST, "cluster.weaviate.network")
    monkeypatch.delenv(cfg.RAGConfig.ENV_WEAVIATE_API_KEY, raising=False)
    with pytest.raises(ValueError):
        cfg.RAGConfig.validate_cloud_config()

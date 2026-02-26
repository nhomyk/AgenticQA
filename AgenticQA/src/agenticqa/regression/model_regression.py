"""
LLM Model Regression Tester.

Captures golden snapshots of agent outputs and scores semantic drift when
the underlying model is swapped (e.g. Sonnet → Haiku, GPT-4o → GPT-4o-mini).

Embedding strategy (in priority order):
  1. fastembed (already a transitive dep via qdrant-client) — local, no API calls
  2. sklearn TF-IDF cosine — pure stdlib fallback, no network required

Snapshots are stored as TestArtifactStore artifacts with artifact_type="llm_golden".
The key is f"{agent_name}__{model_id}__{input_hash}".
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class GoldenSnapshot:
    agent_name: str
    model_id: str
    input_hash: str       # sha256[:16] of serialised input_data
    output_text: str
    embedding: List[float]
    timestamp: str
    run_id: str


@dataclass
class RegressionResult:
    agent_name: str
    baseline_model: str
    candidate_model: str
    similarity_score: float          # 0.0–1.0 cosine similarity
    regression_detected: bool        # True if similarity < threshold
    threshold_used: float
    baseline_snapshot: Optional[GoldenSnapshot]
    candidate_output: str


# ---------------------------------------------------------------------------
# Tester
# ---------------------------------------------------------------------------

class ModelRegressionTester:
    """
    Capture golden snapshots and compare model outputs semantically.

    Usage:
        tester = ModelRegressionTester()
        snap = tester.capture_golden("sre_agent", "claude-sonnet-4-6", input_data, output_text)
        result = tester.compare("sre_agent", "claude-sonnet-4-6", "claude-haiku-4-5", new_output, input_data)
    """

    DEFAULT_THRESHOLD = 0.75

    def __init__(self, store=None, threshold_calibrator=None):
        # Lazily import to avoid hard dependency at module level
        self._store = store
        self._calibrator = threshold_calibrator

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def capture_golden(
        self,
        agent_name: str,
        model_id: str,
        input_data: Any,
        output_text: str,
        run_id: str = "local",
    ) -> GoldenSnapshot:
        """Embed output_text and persist as a golden snapshot artifact."""
        input_hash = self._hash_input(input_data)
        embedding = self._embed(output_text)
        snap = GoldenSnapshot(
            agent_name=agent_name,
            model_id=model_id,
            input_hash=input_hash,
            output_text=output_text[:4000],
            embedding=embedding,
            timestamp=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
        )
        self._persist(snap)
        return snap

    def compare(
        self,
        agent_name: str,
        baseline_model: str,
        candidate_model: str,
        candidate_output: str,
        input_data: Any,
    ) -> RegressionResult:
        """Compare candidate output against stored golden snapshot."""
        input_hash = self._hash_input(input_data)
        key = f"{agent_name}__{baseline_model}__{input_hash}"
        baseline = self._load(key)

        threshold = self._get_threshold()

        if baseline is None:
            return RegressionResult(
                agent_name=agent_name,
                baseline_model=baseline_model,
                candidate_model=candidate_model,
                similarity_score=0.0,
                regression_detected=False,
                threshold_used=threshold,
                baseline_snapshot=None,
                candidate_output=candidate_output[:4000],
            )

        candidate_emb = self._embed(candidate_output)
        similarity = self._cosine(baseline.embedding, candidate_emb)

        return RegressionResult(
            agent_name=agent_name,
            baseline_model=baseline_model,
            candidate_model=candidate_model,
            similarity_score=round(similarity, 4),
            regression_detected=similarity < threshold,
            threshold_used=threshold,
            baseline_snapshot=baseline,
            candidate_output=candidate_output[:4000],
        )

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> List[float]:
        """Embed text. Tries fastembed → falls back to TF-IDF cosine vector."""
        try:
            return self._embed_fastembed(text)
        except Exception:
            return self._embed_tfidf(text)

    def _embed_fastembed(self, text: str) -> List[float]:
        from fastembed import TextEmbedding  # type: ignore
        model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        embeddings = list(model.embed([text[:512]]))
        vec = embeddings[0]
        return list(float(x) for x in vec)

    def _embed_tfidf(self, text: str) -> List[float]:
        """
        Lightweight TF-IDF embedding — no external deps.
        Tokenises into lowercased words, builds a 256-bucket hashed vector.
        """
        tokens = re.findall(r"\b[a-z]{2,}\b", text.lower())
        dim = 256
        vec = [0.0] * dim
        freq: Dict[str, int] = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1
        for word, count in freq.items():
            # FNV-like bucket hash
            bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % dim
            vec[bucket] += math.log(1 + count)
        # L2 normalise
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    # ------------------------------------------------------------------
    # Cosine similarity
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        if len(a) != len(b):
            # Pad shorter vector
            n = max(len(a), len(b))
            a = a + [0.0] * (n - len(a))
            b = b + [0.0] * (n - len(b))
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a)) or 1e-9
        norm_b = math.sqrt(sum(x * x for x in b)) or 1e-9
        return max(0.0, min(1.0, dot / (norm_a * norm_b)))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _artifact_key(self, snap: GoldenSnapshot) -> str:
        return f"{snap.agent_name}__{snap.model_id}__{snap.input_hash}"

    def _persist(self, snap: GoldenSnapshot) -> None:
        store = self._get_store()
        if store is None:
            return
        try:
            store.store_artifact(
                artifact_id=self._artifact_key(snap),
                artifact_type="llm_golden",
                data={
                    "agent_name": snap.agent_name,
                    "model_id": snap.model_id,
                    "input_hash": snap.input_hash,
                    "output_text": snap.output_text,
                    "embedding": snap.embedding,
                    "timestamp": snap.timestamp,
                    "run_id": snap.run_id,
                },
                tags=["llm_golden", snap.agent_name, snap.model_id],
                agent_type="regression",
            )
        except Exception:
            pass  # non-blocking

    def _load(self, key: str) -> Optional[GoldenSnapshot]:
        store = self._get_store()
        if store is None:
            return None
        try:
            raw = store.get_artifact(key)
            if raw is None:
                return None
            data = raw.get("data", raw)
            return GoldenSnapshot(
                agent_name=data["agent_name"],
                model_id=data["model_id"],
                input_hash=data["input_hash"],
                output_text=data.get("output_text", ""),
                embedding=data.get("embedding", []),
                timestamp=data.get("timestamp", ""),
                run_id=data.get("run_id", ""),
            )
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_store(self):
        if self._store is not None:
            return self._store
        try:
            from data_store.artifact_store import TestArtifactStore
            self._store = TestArtifactStore()
            return self._store
        except Exception:
            return None

    def _get_threshold(self) -> float:
        if self._calibrator is not None:
            try:
                return float(self._calibrator.get_threshold("regression"))
            except Exception:
                pass
        return self.DEFAULT_THRESHOLD

    @staticmethod
    def _hash_input(input_data: Any) -> str:
        try:
            serialised = json.dumps(input_data, sort_keys=True, default=str)
        except Exception:
            serialised = str(input_data)
        return hashlib.sha256(serialised.encode()).hexdigest()[:16]

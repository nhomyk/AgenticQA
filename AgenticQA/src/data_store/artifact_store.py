"""Test Artifact Store - Central repository for all test execution artifacts"""

import json
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class TestArtifactStore:
    """Central data store for all test/agent execution artifacts"""

    def __init__(self, base_path: str = ".test-artifact-store"):
        self.base_path = Path(base_path)
        self.raw_dir = self.base_path / "raw"
        self.metadata_dir = self.base_path / "metadata"
        self.patterns_dir = self.base_path / "patterns"
        self.validations_dir = self.base_path / "validations"
        self.index_file = self.base_path / "index.json"

        self._ensure_directories()

    def _ensure_directories(self):
        """Create all necessary directories"""
        for directory in [
            self.raw_dir,
            self.metadata_dir,
            self.patterns_dir,
            self.validations_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def store_artifact(
        self,
        artifact_data: Dict[str, Any],
        artifact_type: str,
        source: str,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Store artifact and return UUID"""
        artifact_id = str(uuid.uuid4())

        # Store raw artifact
        raw_path = self.raw_dir / f"{artifact_id}.json"
        with open(raw_path, "w") as f:
            json.dump(artifact_data, f, indent=2)

        # Store metadata
        metadata = {
            "artifact_id": artifact_id,
            "timestamp": datetime.utcnow().isoformat(),
            "source": source,
            "artifact_type": artifact_type,
            "tags": tags or [],
            "checksum": self._calculate_checksum(artifact_data),
            "size_bytes": raw_path.stat().st_size,
        }

        meta_path = self.metadata_dir / f"{artifact_id}-meta.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        # Update master index
        self._update_index(metadata)

        return artifact_id

    def _calculate_checksum(self, data: Dict) -> str:
        """Calculate SHA256 checksum for data integrity"""
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def _update_index(self, metadata: Dict):
        """Update master index with new artifact metadata"""
        if self.index_file.exists():
            with open(self.index_file, "r") as f:
                index = json.load(f)
        else:
            index = {"artifacts": []}

        index["artifacts"].append(metadata)
        index["last_updated"] = datetime.utcnow().isoformat()

        with open(self.index_file, "w") as f:
            json.dump(index, f, indent=2)

    def get_artifact(self, artifact_id: str) -> Dict[str, Any]:
        """Retrieve artifact by ID"""
        raw_path = self.raw_dir / f"{artifact_id}.json"
        if not raw_path.exists():
            raise FileNotFoundError(f"Artifact {artifact_id} not found")

        with open(raw_path, "r") as f:
            return json.load(f)

    def verify_artifact_integrity(self, artifact_id: str) -> bool:
        """Verify artifact hasn't been tampered with"""
        raw_path = self.raw_dir / f"{artifact_id}.json"
        meta_path = self.metadata_dir / f"{artifact_id}-meta.json"

        if not raw_path.exists() or not meta_path.exists():
            return False

        with open(raw_path, "r") as f:
            artifact_data = json.load(f)
        with open(meta_path, "r") as f:
            metadata = json.load(f)

        current_checksum = self._calculate_checksum(artifact_data)
        return current_checksum == metadata["checksum"]

    def search_artifacts(
        self,
        source: Optional[str] = None,
        artifact_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Search artifacts by metadata"""
        if not self.index_file.exists():
            return []

        with open(self.index_file, "r") as f:
            index = json.load(f)

        results = index["artifacts"]

        if source:
            results = [a for a in results if a["source"] == source]
        if artifact_type:
            results = [a for a in results if a["artifact_type"] == artifact_type]
        if tags:
            results = [a for a in results if any(t in a["tags"] for t in tags)]

        return results

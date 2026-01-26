"""
Snapshot Testing for AgenticQA Data Pipeline

Captures snapshots of agent outputs, data store artifacts, and pipeline results
to ensure consistency and detect unintended changes in data accuracy.

This is critical for ensuring data quality across deployments.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import asdict


class SnapshotManager:
    """Manages snapshot creation, storage, and comparison for pipeline data."""
    
    def __init__(self, snapshot_dir: str = ".snapshots"):
        """
        Initialize snapshot manager.
        
        Args:
            snapshot_dir: Directory to store snapshots
        """
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(exist_ok=True)
        self.snapshots: Dict[str, Dict[str, Any]] = {}
    
    def create_snapshot(self, name: str, data: Dict[str, Any]) -> str:
        """
        Create a snapshot of data.
        
        Args:
            name: Snapshot name/identifier
            data: Data to snapshot
            
        Returns:
            Snapshot hash
        """
        snapshot_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "name": name,
            "data": data,
            "hash": self._compute_hash(data),
        }
        
        self.snapshots[name] = snapshot_data
        self._save_snapshot(name, snapshot_data)
        
        return snapshot_data["hash"]
    
    def compare_snapshot(self, name: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare current data against stored snapshot.
        
        Args:
            name: Snapshot name
            current_data: Current data to compare
            
        Returns:
            Comparison result with match status and differences
        """
        stored = self._load_snapshot(name)
        
        if not stored:
            return {
                "status": "new",
                "message": f"Snapshot '{name}' does not exist. Creating new baseline.",
                "matches": False,
            }
        
        current_hash = self._compute_hash(current_data)
        stored_hash = stored["hash"]
        
        matches = current_hash == stored_hash
        
        return {
            "status": "match" if matches else "mismatch",
            "matches": matches,
            "current_hash": current_hash,
            "stored_hash": stored_hash,
            "stored_timestamp": stored["timestamp"],
            "differences": self._compute_differences(stored["data"], current_data) if not matches else None,
        }
    
    def _compute_hash(self, data: Dict[str, Any]) -> str:
        """Compute SHA256 hash of data."""
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def _compute_differences(self, stored: Dict, current: Dict) -> Dict[str, Any]:
        """Compute differences between two snapshots."""
        differences = {
            "only_in_stored": {},
            "only_in_current": {},
            "changed_values": {},
        }
        
        # Find keys only in stored
        for key in stored:
            if key not in current:
                differences["only_in_stored"][key] = stored[key]
        
        # Find keys only in current
        for key in current:
            if key not in stored:
                differences["only_in_current"][key] = current[key]
        
        # Find changed values
        for key in stored:
            if key in current and stored[key] != current[key]:
                differences["changed_values"][key] = {
                    "stored": stored[key],
                    "current": current[key],
                }
        
        return differences
    
    def _save_snapshot(self, name: str, snapshot_data: Dict[str, Any]) -> None:
        """Save snapshot to file."""
        filepath = self.snapshot_dir / f"{name}.json"
        with open(filepath, "w") as f:
            json.dump(snapshot_data, f, indent=2, default=str)
    
    def _load_snapshot(self, name: str) -> Dict[str, Any] | None:
        """Load snapshot from file."""
        filepath = self.snapshot_dir / f"{name}.json"
        if not filepath.exists():
            return None
        
        with open(filepath, "r") as f:
            return json.load(f)
    
    def get_all_snapshots(self) -> List[str]:
        """Get list of all snapshots."""
        return [f.stem for f in self.snapshot_dir.glob("*.json")]
    
    def delete_snapshot(self, name: str) -> bool:
        """Delete a snapshot."""
        filepath = self.snapshot_dir / f"{name}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

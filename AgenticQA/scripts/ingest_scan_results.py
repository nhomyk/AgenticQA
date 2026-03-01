#!/usr/bin/env python3
"""Ingest scan results from run_client_scan.py into the learning system.

Feeds scanner output into Weaviate (RAG) and the artifact store so the
learning loop benefits from every scan — CI or local.

Usage:
    python scripts/ingest_scan_results.py scan-results.json
    python scripts/ingest_scan_results.py scan-results.json --dry-run

CI integration:
    - name: Ingest scan results
      run: python scripts/ingest_scan_results.py scan-results.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))


def ingest(results_path: str, dry_run: bool = False) -> dict:
    """Ingest scan results into Weaviate + artifact store."""
    with open(results_path) as f:
        data = json.load(f)

    summary = data.get("summary", {})
    scanners = data.get("scanners", {})
    repo_path = summary.get("repo_path", "unknown")
    timestamp = datetime.now(timezone.utc).isoformat()
    ingested = 0
    errors = []

    # Map scanner names to agent types for routing
    scanner_to_agent = {
        "architecture": "compliance",
        "legal_risk": "compliance",
        "cve_reachability": "compliance",
        "hipaa": "compliance",
        "ai_model_sbom": "compliance",
        "ai_act": "compliance",
        "trust_graph": "red-team",
        "prompt_injection": "red-team",
        "mcp_security": "red-team",
        "data_flow": "red-team",
    }

    for scanner_name, scanner_data in scanners.items():
        if scanner_data.get("status") != "ok":
            continue

        agent_type = scanner_to_agent.get(scanner_name, "compliance")
        artifact = {
            "artifact_type": f"scan_{scanner_name}",
            "agent_type": agent_type,
            "scanner_name": scanner_name,
            "repo_path": repo_path,
            "timestamp": timestamp,
            "result": scanner_data.get("result", {}),
            "elapsed_s": scanner_data.get("elapsed_s", 0),
        }

        if dry_run:
            print(f"  [DRY RUN] Would ingest: {scanner_name} ({agent_type})")
            ingested += 1
            continue

        try:
            # Try Weaviate first
            try:
                from agenticqa.rag.retriever import RAGRetriever
                rag = RAGRetriever()
                text = json.dumps(scanner_data.get("result", {}))[:4000]
                rag.add_document(
                    text=text,
                    metadata={
                        "source": f"scan_{scanner_name}",
                        "agent_type": agent_type,
                        "repo_path": repo_path,
                        "timestamp": timestamp,
                    },
                )
            except Exception:
                pass  # Weaviate not available — use fallback

            # Artifact store (always available)
            store_dir = Path(".test-artifact-store")
            store_dir.mkdir(exist_ok=True)
            artifact_id = f"scan_{scanner_name}_{int(time.time())}"
            artifact_path = store_dir / f"{artifact_id}.json"
            artifact_path.write_text(json.dumps(artifact, indent=2))
            ingested += 1

        except Exception as exc:
            errors.append(f"{scanner_name}: {exc}")

    return {
        "ingested": ingested,
        "total_scanners": len(scanners),
        "errors": errors,
        "repo_path": repo_path,
    }


def main():
    parser = argparse.ArgumentParser(description="Ingest scan results into learning system")
    parser.add_argument("results_file", help="Path to scan-results.json from run_client_scan.py")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be ingested")
    args = parser.parse_args()

    if not Path(args.results_file).exists():
        print(f"Error: {args.results_file} not found", file=sys.stderr)
        sys.exit(1)

    result = ingest(args.results_file, dry_run=args.dry_run)
    print(f"\nIngested {result['ingested']}/{result['total_scanners']} scan results"
          f" from {result['repo_path']}")
    if result["errors"]:
        print(f"Errors: {'; '.join(result['errors'])}")
        sys.exit(1)


if __name__ == "__main__":
    main()

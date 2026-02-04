#!/usr/bin/env python3
"""
Store Accessibility Fix Results to Weaviate for Learning

This script is called after re-validation to store successful fixes
to Weaviate, enabling the learning loop.

Usage:
    python store_fix_results.py --fixes-applied 5 --errors-before 12 --errors-after 0 --run-id 12345
"""

import sys
import os
import json
import argparse
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from agents import ComplianceAgent


def main():
    parser = argparse.ArgumentParser(description='Store accessibility fix results for learning')
    parser.add_argument('--fixes-json', help='Path to JSON file with fixes applied')
    parser.add_argument('--fixes-applied', type=int, help='Number of fixes applied')
    parser.add_argument('--errors-before', type=int, required=True, help='Errors before fixes')
    parser.add_argument('--errors-after', type=int, required=True, help='Errors after fixes')
    parser.add_argument('--run-id', help='CI run ID', default=os.getenv('GITHUB_RUN_ID', 'local'))

    args = parser.parse_args()

    print("🧠 Storing Fix Results to Weaviate for Learning")
    print("=" * 60)

    # Initialize ComplianceAgent
    agent = ComplianceAgent()

    if not agent.rag:
        print("⚠️  Weaviate not available. Learning loop disabled.")
        print("   Configure Weaviate connection to enable learning.")
        return 0

    # Load fixes from JSON if provided
    fixes_applied = []
    if args.fixes_json and os.path.exists(args.fixes_json):
        with open(args.fixes_json, 'r') as f:
            data = json.load(f)
            fixes_applied = data.get('fixes', [])
    elif args.fixes_applied:
        # Create placeholder fixes (CI will provide actual data)
        for i in range(args.fixes_applied):
            fixes_applied.append({
                "type": "accessibility_fix",
                "file": "public/index.html"
            })

    # Store revalidation results
    print(f"\n📊 Validation Results:")
    print(f"  Fixes applied: {len(fixes_applied)}")
    print(f"  Errors before: {args.errors_before}")
    print(f"  Errors after:  {args.errors_after}")
    print(f"  Errors fixed:  {args.errors_before - args.errors_after}")
    print()

    agent.store_revalidation_results(
        fixes_applied=fixes_applied,
        errors_before=args.errors_before,
        errors_after=args.errors_after,
        run_id=args.run_id
    )

    print("\n✅ Fix results stored to Weaviate!")
    print("\n💡 Next runs will query these patterns for improved fixes.")
    print(f"   Run ID: {args.run_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Accessibility Auto-Fix Script

Uses the ComplianceAgent to automatically fix accessibility violations
found by Pa11y scans.

Usage:
    python fix_accessibility.py <pa11y-report.txt> <file1.html> [file2.html ...]

Example:
    python fix_accessibility.py pa11y-report.txt public/index.html
"""

import sys
import os
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from agents import ComplianceAgent


def main():
    if len(sys.argv) < 3:
        print("Usage: python fix_accessibility.py <pa11y-report.txt> <file1.html> [file2.html ...]")
        print("")
        print("Example:")
        print("  python fix_accessibility.py pa11y-report.txt public/index.html")
        sys.exit(1)

    pa11y_report = sys.argv[1]
    files_to_fix = sys.argv[2:]

    # Validate inputs
    if not os.path.exists(pa11y_report):
        print(f"❌ Pa11y report not found: {pa11y_report}")
        sys.exit(1)

    for file_path in files_to_fix:
        if not os.path.exists(file_path):
            print(f"⚠️  File not found (will skip): {file_path}")

    print("🔧 AgenticQA Accessibility Auto-Fix")
    print("=" * 50)
    print(f"📄 Pa11y Report: {pa11y_report}")
    print(f"🎯 Files to Fix: {', '.join(files_to_fix)}")
    print("")

    # Initialize ComplianceAgent with RAG disabled for faster execution
    # (Enable RAG in production for learning from fixes)
    agent = ComplianceAgent()
    print(f"✅ {agent.agent_name} initialized")
    print("")

    # Run accessibility auto-fix
    print("🚀 Running accessibility auto-fix...")
    print("")

    try:
        result = agent.fix_accessibility_violations(pa11y_report, files_to_fix)

        # Display results
        print("=" * 50)
        print("📊 Auto-Fix Results")
        print("=" * 50)
        print(f"Violations Found: {result['violations_found']}")
        print(f"Fixes Applied: {result['fixes_applied']}")
        print(f"Files Modified: {result['files_modified']}")
        print("")

        if result['fixes']:
            print("🔨 Fixes Applied:")
            print("")
            for fix in result['fixes']:
                print(f"  • {fix['file']}")
                print(f"    - Type: {fix['type']}")
                if fix['type'] == 'color_contrast':
                    print(f"    - Changed to: {fix['fix']}")
                elif fix['type'] in ['missing_label', 'missing_alt']:
                    print(f"    - Element: {fix['element']}")
                print("")

        print("✅ Accessibility auto-fix complete!")
        print("")
        print("💡 Next Steps:")
        print("  1. Review the changes in your files")
        print("  2. Re-run Pa11y to verify fixes: npm run test:pa11y")
        print("  3. Commit the accessibility improvements")
        print("")
        print("🧠 Learning:")
        print("  - All fixes are logged to Weaviate for RAG learning")
        print("  - Future runs will use these patterns to improve fix quality")

    except Exception as e:
        print(f"❌ Auto-fix failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

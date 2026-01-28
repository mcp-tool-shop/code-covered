"""
Code-Covered CLI

Find coverage gaps and suggest what tests to write.

Usage:
    code-covered coverage.json              # Analyze coverage gaps
    code-covered coverage.json -v           # Show full test templates
    code-covered coverage.json -o stubs.py  # Write test stubs to file
"""

import argparse
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


def cmd_gaps(args):
    """Find coverage gaps and suggest what tests to write."""
    from analyzer import find_coverage_gaps, print_coverage_gaps, CoverageParser

    coverage_path = Path(args.coverage_json)
    if not coverage_path.exists():
        print(f"Error: Coverage file not found: {coverage_path}")
        print("\nGenerate it with:")
        print("  pytest --cov=yourmodule --cov-report=json")
        return 1

    # Parse coverage report for summary
    try:
        parser = CoverageParser()
        report = parser.parse(str(coverage_path))
    except Exception as e:
        print(f"Error: Failed to parse coverage file: {e}")
        return 1

    print(f"\n{'='*60}")
    print("code-covered")
    print(f"{'='*60}")
    print(f"Coverage: {report.coverage_percent:.1f}% ({report.total_covered}/{report.total_covered + report.total_missing} lines)")

    files_with_gaps = sum(1 for f in report.files.values() if f.missing_lines)
    print(f"Files analyzed: {len(report.files)} ({files_with_gaps} with gaps)")

    # Find suggestions
    suggestions, warnings = find_coverage_gaps(
        str(coverage_path),
        source_root=args.source_root,
    )

    # Show warnings about files we couldn't process
    if warnings:
        print(f"\nWarnings: {len(warnings)} files could not be analyzed")
        if args.verbose:
            for w in warnings[:5]:
                print(f"  - {w}")
            if len(warnings) > 5:
                print(f"  ... and {len(warnings) - 5} more")

    # Apply filters
    if args.priority:
        suggestions = [s for s in suggestions if s.priority == args.priority]

    if args.limit:
        suggestions = suggestions[:args.limit]

    if not suggestions:
        print("\nNo coverage gaps found - great job!")
        return 0

    # Group by priority
    by_priority = {}
    for s in suggestions:
        by_priority.setdefault(s.priority, []).append(s)

    print(f"\nMissing tests: {len(suggestions)}")
    for priority in ["critical", "high", "medium", "low"]:
        count = len(by_priority.get(priority, []))
        if count:
            marker = {"critical": "!!", "high": "!", "medium": "-", "low": " "}[priority]
            print(f"  [{marker}] {priority.upper()}: {count}")

    # Output
    if args.verbose:
        print_coverage_gaps(suggestions)
    else:
        print("\nTop suggestions:")
        for i, s in enumerate(suggestions[:10], 1):
            marker = {"critical": "!!", "high": "! ", "medium": "  ", "low": "  "}.get(s.priority, "  ")
            print(f"  {i}. [{marker}] {s.test_name}")
            print(f"       {s.description}")

        if len(suggestions) > 10:
            print(f"\n  ... and {len(suggestions) - 10} more (use -v to see all)")

    # Write to file if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write('"""Auto-generated test stubs from coverage gaps."""\n\n')
            f.write("import pytest\n\n")
            for s in suggestions:
                f.write(f"# {s.description}\n")
                f.write(f"# Priority: {s.priority}\n")
                if s.setup_hints:
                    f.write(f"# Hints: {', '.join(s.setup_hints)}\n")
                f.write(s.code_template)
                f.write("\n\n")
        print(f"\nWrote {len(suggestions)} test stubs to {output_path}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="code-covered",
        description="Find coverage gaps and suggest what tests to write",
        epilog="Example: code-covered coverage.json -v"
    )

    parser.add_argument(
        "coverage_json",
        help="Path to coverage.json (from pytest --cov-report=json)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show full test templates for each gap"
    )
    parser.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="Write test stubs to file"
    )
    parser.add_argument(
        "--source-root",
        metavar="DIR",
        help="Root directory for source files (if different from coverage paths)"
    )
    parser.add_argument(
        "--priority",
        choices=["critical", "high", "medium", "low"],
        help="Filter by priority level"
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Limit number of suggestions"
    )

    args = parser.parse_args()

    # Handle the case where no args are provided
    if len(sys.argv) == 1:
        parser.print_help()
        print("\nQuick start:")
        print("  1. Run tests with coverage:")
        print("     pytest --cov=mymodule --cov-report=json")
        print("")
        print("  2. Find what tests you're missing:")
        print("     code-covered coverage.json")
        return 0

    return cmd_gaps(args)


if __name__ == "__main__":
    sys.exit(main())

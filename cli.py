"""
Code-Covered CLI

Commands:
    gaps      - Find coverage gaps and suggest missing tests
    analyze   - Static analysis for code issues
    generate  - Generate tests for code
"""

import argparse
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


def cmd_gaps(args):
    """Find coverage gaps and suggest what tests to write."""
    from analyzer.coverage_gaps import (
        find_coverage_gaps,
        print_coverage_gaps,
        CoverageParser,
    )

    coverage_path = Path(args.coverage_json)
    if not coverage_path.exists():
        logger.error(f"Coverage file not found: {coverage_path}")
        print("\nGenerate it with: pytest --cov=yourmodule --cov-report=json")
        return 1

    # Parse coverage report for summary
    try:
        parser = CoverageParser()
        report = parser.parse(str(coverage_path))
    except Exception as e:
        logger.error(f"Failed to parse coverage file: {e}")
        return 1

    print(f"\n{'='*60}")
    print("Code-Covered - Coverage Gap Finder")
    print(f"{'='*60}")
    print(f"Coverage: {report.coverage_percent:.1f}% ({report.total_covered}/{report.total_covered + report.total_missing} lines)")
    print(f"Files with gaps: {sum(1 for f in report.files.values() if f.missing_lines)}")

    # Find and print suggestions
    suggestions, warnings = find_coverage_gaps(
        str(coverage_path),
        source_root=args.source_root,
    )

    # Show any warnings about files we couldn't process
    if warnings and args.verbose:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings[:5]:
            print(f"  - {w}")
        if len(warnings) > 5:
            print(f"  ... and {len(warnings) - 5} more")

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

    print(f"\nFound {len(suggestions)} missing tests:")
    for priority in ["critical", "high", "medium", "low"]:
        count = len(by_priority.get(priority, []))
        if count:
            print(f"  - {priority.upper()}: {count}")

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

    # Output to file if requested
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


def cmd_analyze(args):
    """Run static analysis on code."""
    from analyzer.static_analyzer import StaticAnalyzer

    path = Path(args.path)
    if not path.exists():
        logger.error(f"Path not found: {path}")
        return 1

    analyzer = StaticAnalyzer()

    if path.is_file():
        issues = analyzer.analyze_file(path)
    else:
        issues = analyzer.analyze_directory(path, recursive=not args.no_recursive)

    # Filter by severity
    if args.severity:
        issues = [i for i in issues if i.severity == args.severity]

    if not issues:
        print("No issues found!")
        return 0

    # Group by file
    by_file = {}
    for issue in issues:
        by_file.setdefault(issue.file_path, []).append(issue)

    print(f"\n{'='*60}")
    print(f"Code-Covered - Static Analysis")
    print(f"{'='*60}")
    print(f"Found {len(issues)} issues in {len(by_file)} files\n")

    for file_path, file_issues in by_file.items():
        print(f"\n{file_path}")
        print("-" * min(len(str(file_path)), 60))

        for issue in file_issues:
            icon = {"error": "[!]", "warning": "[?]", "info": "[i]"}[issue.severity]
            print(f"  {icon} Line {issue.line_start}: {issue.type.name}")
            print(f"      {issue.message}")

            if args.verbose:
                print(f"\n{issue.code_snippet}\n")

    # Compute summary from collected issues
    errors = len([i for i in issues if i.severity == "error"])
    warnings = len([i for i in issues if i.severity == "warning"])
    infos = len([i for i in issues if i.severity == "info"])

    print(f"\n{'='*60}")
    print(f"Summary: {errors} errors, {warnings} warnings, {infos} info")

    return 1 if errors > 0 else 0


def cmd_generate(args):
    """Generate tests for code."""
    from analyzer.test_generator import TestGenerator

    path = Path(args.path)
    if not path.exists():
        logger.error(f"Path not found: {path}")
        return 1

    generator = TestGenerator()

    if path.is_file():
        tests = generator.generate_for_file(path)
        all_tests = {path: tests}
    else:
        all_tests = {}
        for py_file in path.glob("**/*.py" if not args.no_recursive else "*.py"):
            if "__pycache__" not in str(py_file) and "test_" not in py_file.name:
                tests = generator.generate_for_file(py_file)
                if tests:
                    all_tests[py_file] = tests

    if not all_tests:
        print("No functions found to generate tests for!")
        return 0

    total = sum(len(t) for t in all_tests.values())
    print(f"\n{'='*60}")
    print(f"Code-Covered - Test Generation")
    print(f"{'='*60}")
    print(f"Generated {total} tests for {len(all_tests)} files\n")

    if args.output:
        output_path = Path(args.output)
        if output_path.is_dir():
            for source, tests in all_tests.items():
                test_file = output_path / f"test_{source.stem}.py"
                generator.write_test_file(tests, test_file)
                print(f"  Wrote {len(tests)} tests to {test_file}")
        else:
            all_list = [t for tests in all_tests.values() for t in tests]
            generator.write_test_file(all_list, output_path)
            print(f"  Wrote {total} tests to {output_path}")
    else:
        for source, tests in all_tests.items():
            print(f"\n# Tests for {source}")
            print("=" * 60)
            print(generator.generate_test_content(tests))

    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="code-covered",
        description="Find coverage gaps and generate missing tests"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Gaps command (the main feature!)
    gaps_p = subparsers.add_parser(
        "gaps",
        help="Find coverage gaps and suggest missing tests",
        description="Analyzes coverage.json to find untested code and generates specific test suggestions"
    )
    gaps_p.add_argument("coverage_json", help="Path to coverage.json (from pytest --cov-report=json)")
    gaps_p.add_argument("-v", "--verbose", action="store_true", help="Show full test templates")
    gaps_p.add_argument("-o", "--output", help="Write test stubs to file")
    gaps_p.add_argument("--source-root", help="Root directory for source files")
    gaps_p.add_argument("--priority", choices=["critical", "high", "medium", "low"], help="Filter by priority")
    gaps_p.add_argument("--limit", type=int, help="Limit number of suggestions")
    gaps_p.set_defaults(func=cmd_gaps)

    # Analyze command
    analyze_p = subparsers.add_parser("analyze", help="Static analysis for code issues")
    analyze_p.add_argument("path", help="File or directory to analyze")
    analyze_p.add_argument("-v", "--verbose", action="store_true", help="Show code snippets")
    analyze_p.add_argument("--no-recursive", action="store_true")
    analyze_p.add_argument("--severity", choices=["error", "warning", "info"])
    analyze_p.set_defaults(func=cmd_analyze)

    # Generate command
    gen_p = subparsers.add_parser("generate", help="Generate tests for code")
    gen_p.add_argument("path", help="File or directory")
    gen_p.add_argument("-o", "--output", help="Output file or directory")
    gen_p.add_argument("--no-recursive", action="store_true")
    gen_p.set_defaults(func=cmd_generate)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print("\nQuick start:")
        print("  1. Run tests with coverage: pytest --cov=mymodule --cov-report=json")
        print("  2. Find missing tests:      code-covered gaps coverage.json")
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

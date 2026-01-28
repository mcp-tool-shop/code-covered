"""
Code-Covered Analyzer

Tells you WHAT tests to write, not just what's uncovered.

Core components:
- CoverageParser: Reads coverage.py JSON output
- GapAnalyzer: Maps uncovered lines to specific test suggestions
- GapSuggestionGenerator: Creates actionable test templates

Usage:
    from analyzer import find_coverage_gaps

    suggestions, warnings = find_coverage_gaps("coverage.json")
    for s in suggestions:
        print(f"{s.priority}: {s.test_name}")
"""

from .coverage_gaps import (
    CoverageParser,
    CoverageReport,
    FileCoverage,
    GapAnalyzer,
    GapSuggestion,
    GapSuggestionGenerator,
    UncoveredBlock,
    find_coverage_gaps,
    print_coverage_gaps,
)

__all__ = [
    # Main entry point
    "find_coverage_gaps",
    "print_coverage_gaps",
    # Data structures
    "CoverageParser",
    "CoverageReport",
    "FileCoverage",
    "GapAnalyzer",
    "GapSuggestion",
    "GapSuggestionGenerator",
    "UncoveredBlock",
]

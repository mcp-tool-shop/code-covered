"""
MCP Tool Handler for code_covered.gaps

Wraps the code-covered engine to provide an MCP-compatible interface.
Accepts coverage.json as inline JSON or artifact reference.
"""

from __future__ import annotations

import json
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Optional

# Import from the engine (sibling package)
from analyzer.coverage_gaps import (
    CoverageParser,
    GapSuggestion,
    GapAnalyzer,
    GapSuggestionGenerator,
)

# Priority scoring for threshold checks
PRIORITY_SCORE = {"critical": 3, "high": 2, "medium": 1, "low": 0}
PRIORITY_ORDER = ["critical", "high", "medium", "low"]


def handle(
    request: dict[str, Any],
    *,
    artifact_resolver: Optional[Callable[[str], bytes]] = None,
) -> dict[str, Any]:
    """
    MCP tool handler for code_covered.gaps.

    Args:
        request: Request dict matching the request schema.
        artifact_resolver: Optional callable to resolve artifact_id -> bytes.
            If not provided, falls back to locator-as-path.

    Returns:
        Response dict matching the response schema.
    """
    try:
        # 1. Load coverage data
        coverage_data = _load_coverage(
            request["coverage"],
            artifact_resolver=artifact_resolver,
        )
    except FileNotFoundError as e:
        return _error_response(f"Coverage file not found: {e}")
    except json.JSONDecodeError as e:
        return _error_response(f"Invalid JSON in coverage data: {e}")
    except ValueError as e:
        return _error_response(str(e))
    except Exception as e:
        return _error_response(f"Failed to load coverage: {e}")

    # 2. Parse and analyze
    try:
        suggestions, warnings = _analyze_coverage_data(
            coverage_data,
            repo_root=request.get("repo_root"),
        )
    except Exception as e:
        return _error_response(f"Analysis failed: {e}")

    # 3. Filter by priority if requested
    priority_filter = request.get("priority_filter")
    if priority_filter:
        min_score = PRIORITY_SCORE.get(priority_filter, 0)
        suggestions = [
            s for s in suggestions
            if PRIORITY_SCORE.get(s.priority, 0) >= min_score
        ]

    # 4. Count by priority (after filter, before limit)
    total_suggestions = len(suggestions)
    by_priority = {p: 0 for p in PRIORITY_ORDER}
    for s in suggestions:
        if s.priority in by_priority:
            by_priority[s.priority] += 1

    # 5. Compute exit code BEFORE limit (evaluate against filtered set)
    # This ensures CI gating sees all matching gaps, not just top N
    fail_on = request.get("fail_on", "none")
    exit_code = _compute_exit_code(suggestions, fail_on)

    # 6. Apply limit if requested (for output only, doesn't affect gating)
    limit = request.get("limit")
    if limit and limit > 0:
        suggestions = suggestions[:limit]

    # 7. Build result
    result = _build_result(
        coverage_data,
        suggestions,
        total_suggestions,
        by_priority,
    )

    # 8. Build response
    response: dict[str, Any] = {
        "exit_code": exit_code,
        "result": result,
        "warnings": sorted(warnings),
    }

    # 9. Add text output if requested
    if request.get("format") == "text":
        response["text"] = _format_text_output(result, suggestions)

    return response


def _load_coverage(
    coverage: Any,
    *,
    artifact_resolver: Optional[Callable[[str], bytes]] = None,
) -> dict[str, Any]:
    """
    Load coverage data from inline dict or artifact reference.

    Args:
        coverage: Either a parsed coverage.json dict or an artifact reference.
        artifact_resolver: Optional callable to resolve artifact_id -> bytes.

    Returns:
        Parsed coverage.json as dict.

    Raises:
        ValueError: If coverage format is invalid.
        FileNotFoundError: If locator path doesn't exist.
        json.JSONDecodeError: If content is not valid JSON.
    """
    if not isinstance(coverage, dict):
        raise ValueError("coverage must be an object")

    # Check if it's an artifact reference
    if "artifact_id" in coverage:
        # Try artifact resolver first
        if artifact_resolver is not None:
            raw = artifact_resolver(coverage["artifact_id"])
            return json.loads(raw.decode("utf-8"))

        # Fall back to locator as file path
        locator = coverage.get("locator")
        if not locator:
            raise ValueError(
                "artifact reference requires either artifact_resolver or locator"
            )

        with open(locator, "r", encoding="utf-8") as f:
            return json.load(f)

    # Otherwise treat as inline coverage data
    # Validate it looks like coverage.json
    if "files" not in coverage and "meta" not in coverage:
        raise ValueError(
            "coverage data must contain 'files' key (coverage.json format)"
        )

    return coverage


def _analyze_coverage_data(
    coverage_data: dict[str, Any],
    repo_root: Optional[str] = None,
) -> tuple[list[GapSuggestion], list[str]]:
    """
    Analyze coverage data and return suggestions.

    This reimplements find_coverage_gaps() logic but works with
    parsed JSON instead of a file path.

    Args:
        coverage_data: Parsed coverage.json dict.
        repo_root: Optional root for resolving source file paths.

    Returns:
        Tuple of (suggestions, warnings).
    """
    all_suggestions: list[GapSuggestion] = []
    warnings: list[str] = []

    files_data = coverage_data.get("files", {})

    for file_path, file_data in files_data.items():
        # Get coverage info
        missing_lines = set(file_data.get("missing_lines", []))
        if not missing_lines:
            continue

        # Resolve actual path
        actual_path = file_path
        if repo_root:
            actual_path = str(Path(repo_root) / file_path)

        # Try to read source file
        try:
            with open(actual_path, "r", encoding="utf-8", errors="replace") as f:
                source_code = f.read()
        except FileNotFoundError:
            warnings.append(f"Source file not found: {actual_path}")
            continue
        except PermissionError:
            warnings.append(f"Permission denied reading: {actual_path}")
            continue
        except Exception as e:
            warnings.append(f"Error reading {actual_path}: {e}")
            continue

        # Analyze and generate suggestions
        analyzer = GapAnalyzer(source_code, missing_lines)
        blocks = analyzer.analyze(file_path)

        generator = GapSuggestionGenerator()
        suggestions = generator.generate(blocks, file_path)
        all_suggestions.extend(suggestions)

    return all_suggestions, warnings


def _build_result(
    coverage_data: dict[str, Any],
    suggestions: list[GapSuggestion],
    total_suggestions: int,
    by_priority: dict[str, int],
) -> dict[str, Any]:
    """Build the result object for the response."""
    files_data = coverage_data.get("files", {})

    # Calculate coverage stats
    total_covered = 0
    total_missing = 0
    files_with_gaps = 0

    for file_data in files_data.values():
        executed = len(file_data.get("executed_lines", []))
        missing = len(file_data.get("missing_lines", []))
        total_covered += executed
        total_missing += missing
        if missing > 0:
            files_with_gaps += 1

    total_lines = total_covered + total_missing
    coverage_percent = (total_covered / total_lines * 100) if total_lines > 0 else 100.0

    return {
        "coverage_percent": round(coverage_percent, 2),
        "files_analyzed": len(files_data),
        "files_with_gaps": files_with_gaps,
        "total_suggestions": total_suggestions,
        "suggestions": [s.to_dict() for s in suggestions],
        "by_priority": by_priority,
    }


def _compute_exit_code(suggestions: list[GapSuggestion], fail_on: str) -> int:
    """
    Compute exit code based on suggestions and threshold.

    Args:
        suggestions: List of gap suggestions.
        fail_on: Threshold setting ("none", "critical", "high", "any").

    Returns:
        0 = success, 2 = threshold met.
    """
    if fail_on == "none":
        return 0

    if fail_on == "any" and suggestions:
        return 2

    threshold = PRIORITY_SCORE.get(fail_on, 0)
    for s in suggestions:
        score = PRIORITY_SCORE.get(s.priority, 0)
        if score >= threshold:
            return 2

    return 0


def _format_text_output(
    result: dict[str, Any],
    suggestions: list[GapSuggestion],
) -> str:
    """Format human-readable text output."""
    lines = []
    lines.append("=" * 60)
    lines.append("code-covered")
    lines.append("=" * 60)
    lines.append(
        f"Coverage: {result['coverage_percent']:.1f}% "
        f"({result['files_analyzed']} files analyzed)"
    )
    lines.append(f"Files with gaps: {result['files_with_gaps']}")
    lines.append("")

    by_priority = result.get("by_priority", {})
    lines.append(f"Missing tests: {result['total_suggestions']}")
    if by_priority.get("critical", 0) > 0:
        lines.append(f"  [!!] CRITICAL: {by_priority['critical']}")
    if by_priority.get("high", 0) > 0:
        lines.append(f"  [!]  HIGH: {by_priority['high']}")
    if by_priority.get("medium", 0) > 0:
        lines.append(f"  [  ] MEDIUM: {by_priority['medium']}")
    if by_priority.get("low", 0) > 0:
        lines.append(f"  [  ] LOW: {by_priority['low']}")
    lines.append("")

    if suggestions:
        lines.append("Top suggestions:")
        for i, s in enumerate(suggestions[:10], 1):
            marker = {
                "critical": "[!!]",
                "high": "[! ]",
                "medium": "[  ]",
                "low": "[  ]",
            }.get(s.priority, "[  ]")
            lines.append(f"  {i}. {marker} {s.test_name}")
            lines.append(f"       {s.description}")

        if len(suggestions) > 10:
            lines.append(f"  ... and {len(suggestions) - 10} more")

    return "\n".join(lines)


def _error_response(message: str) -> dict[str, Any]:
    """Build an error response."""
    return {
        "exit_code": 1,
        "result": {
            "coverage_percent": 0,
            "files_analyzed": 0,
            "files_with_gaps": 0,
            "total_suggestions": 0,
            "suggestions": [],
            "by_priority": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        },
        "warnings": [message],
    }

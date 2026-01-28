"""
Coverage Gap Finder - Maps uncovered lines to specific test suggestions.

The problem: coverage.py tells you "line 47 is uncovered" but not
"you need a test for validate_input() when input is empty".

This module bridges that gap by:
1. Reading coverage.py JSON output
2. Using AST to understand the uncovered code's context
3. Generating specific test suggestions with code templates

Usage:
    # Run coverage first
    pytest --cov=mymodule --cov-report=json

    # Then analyze
    code-covered gaps coverage.json

    # Or programmatically
    from analyzer.coverage_gaps import find_coverage_gaps
    suggestions, warnings = find_coverage_gaps("coverage.json")

Example:
    >>> suggestions, warnings = find_coverage_gaps("coverage.json")
    >>> for s in suggestions:
    ...     print(f"{s.priority}: {s.test_name}")
    critical: test_validator_validate_handles_exception
    high: test_parser_parse_when_condition_false
"""

import ast
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class UncoveredBlock:
    """A block of uncovered code with context."""

    file_path: str
    start_line: int
    end_line: int
    function_name: Optional[str] = None
    class_name: Optional[str] = None
    code_snippet: str = ""
    block_type: str = "unknown"  # branch, function, error_handler, etc.
    condition: Optional[str] = None  # The condition that wasn't tested


@dataclass
class GapSuggestion:
    """A specific test you should write to cover a gap."""

    test_name: str
    test_file: str
    description: str
    covers_lines: list[int]
    priority: str  # critical, high, medium, low
    code_template: str
    setup_hints: list[str] = field(default_factory=list)
    block_type: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "test_name": self.test_name,
            "test_file": self.test_file,
            "description": self.description,
            "covers_lines": self.covers_lines,
            "priority": self.priority,
            "code_template": self.code_template,
            "setup_hints": self.setup_hints,
            "block_type": self.block_type,
        }


@dataclass
class FileCoverage:
    """Coverage data for a single file."""

    path: str
    covered_lines: set[int]
    missing_lines: set[int]
    excluded_lines: set[int]
    missing_branches: list[tuple[int, int]]  # (from_line, to_line)

    @property
    def coverage_percent(self) -> float:
        total = len(self.covered_lines) + len(self.missing_lines)
        if total == 0:
            return 100.0
        return len(self.covered_lines) / total * 100


@dataclass
class CoverageReport:
    """Parsed coverage.py report."""

    files: dict[str, FileCoverage]
    total_covered: int = 0
    total_missing: int = 0

    @property
    def coverage_percent(self) -> float:
        total = self.total_covered + self.total_missing
        if total == 0:
            return 100.0
        return self.total_covered / total * 100


class CoverageParser:
    """Parse coverage.py JSON output."""

    def parse(self, json_path: str) -> CoverageReport:
        """
        Parse coverage.json file.

        Args:
            json_path: Path to coverage.json

        Returns:
            CoverageReport with file-level coverage data

        Raises:
            FileNotFoundError: If json_path doesn't exist
            json.JSONDecodeError: If file is not valid JSON
        """
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        files = {}
        total_covered = 0
        total_missing = 0

        for file_path, file_data in data.get("files", {}).items():
            # Get line data
            executed = set(file_data.get("executed_lines", []))
            missing = set(file_data.get("missing_lines", []))
            excluded = set(file_data.get("excluded_lines", []))

            # Get branch data if available
            missing_branches = []
            for branch_key, branch_data in file_data.get("missing_branches", {}).items():
                try:
                    from_line = int(branch_key)
                    for to_line in branch_data:
                        missing_branches.append((from_line, to_line))
                except (ValueError, TypeError):
                    pass

            files[file_path] = FileCoverage(
                path=file_path,
                covered_lines=executed,
                missing_lines=missing,
                excluded_lines=excluded,
                missing_branches=missing_branches,
            )

            total_covered += len(executed)
            total_missing += len(missing)

        return CoverageReport(
            files=files,
            total_covered=total_covered,
            total_missing=total_missing,
        )


class GapAnalyzer(ast.NodeVisitor):
    """Analyze AST to understand what uncovered code does."""

    def __init__(self, source_code: str, missing_lines: set[int]):
        self.source_code = source_code
        self.source_lines = source_code.splitlines()
        self.missing_lines = missing_lines
        self.uncovered_blocks: list[UncoveredBlock] = []

        # Context tracking
        self._current_class: Optional[str] = None
        self._current_function: Optional[str] = None
        self._current_file: str = ""
        self._seen_blocks: set[tuple[int, int]] = set()  # Avoid duplicates

    def analyze(self, file_path: str) -> list[UncoveredBlock]:
        """Analyze a file and return uncovered blocks with context."""
        self._current_file = file_path

        try:
            tree = ast.parse(self.source_code)
            self.visit(tree)
        except SyntaxError as e:
            logger.debug(f"Syntax error in {file_path}: {e}, falling back to line-based analysis")
            self._analyze_by_lines()

        return self.uncovered_blocks

    def _analyze_by_lines(self) -> None:
        """Fallback: analyze uncovered lines without AST."""
        sorted_missing = sorted(self.missing_lines)
        if not sorted_missing:
            return

        # Group consecutive lines
        groups: list[list[int]] = []
        current_group = [sorted_missing[0]]

        for line in sorted_missing[1:]:
            if line == current_group[-1] + 1:
                current_group.append(line)
            else:
                groups.append(current_group)
                current_group = [line]
        groups.append(current_group)

        for group in groups:
            snippet = self._get_code_snippet(group[0], group[-1])
            self.uncovered_blocks.append(UncoveredBlock(
                file_path=self._current_file,
                start_line=group[0],
                end_line=group[-1],
                code_snippet=snippet,
                block_type="code_block",
            ))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Track class context."""
        old_class = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Analyze function for uncovered code."""
        self._analyze_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Analyze async function for uncovered code."""
        self._analyze_function(node)

    def _analyze_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        """Analyze a function definition for uncovered blocks."""
        old_function = self._current_function
        self._current_function = node.name

        # Check if function body has uncovered lines
        end_line = node.end_lineno or node.lineno
        func_lines = set(range(node.lineno, end_line + 1))
        uncovered_in_func = func_lines & self.missing_lines

        if uncovered_in_func:
            # Walk function body to find specific uncovered constructs
            for child in ast.walk(node):
                self._analyze_node(child)

        self.generic_visit(node)
        self._current_function = old_function

    def _analyze_node(self, node: ast.AST) -> None:
        """Analyze a specific node for uncovered code."""
        if not hasattr(node, "lineno"):
            return

        line = node.lineno
        if line not in self.missing_lines:
            return

        # Avoid duplicate blocks
        end_line = getattr(node, "end_lineno", line) or line
        block_key = (line, end_line)
        if block_key in self._seen_blocks:
            return
        self._seen_blocks.add(block_key)

        if isinstance(node, ast.If):
            self._analyze_if(node)
        elif isinstance(node, ast.ExceptHandler):
            self._analyze_except(node)
        elif isinstance(node, ast.Return):
            self._analyze_return(node)
        elif isinstance(node, ast.Raise):
            self._analyze_raise(node)
        elif isinstance(node, (ast.For, ast.While)):
            self._analyze_loop(node)

    def _analyze_if(self, node: ast.If) -> None:
        """Analyze uncovered if branch."""
        condition = self._get_source_segment(node.test)

        if_body_lines = set()
        for child in node.body:
            if hasattr(child, "lineno"):
                if_body_lines.add(child.lineno)

        else_body_lines = set()
        for child in node.orelse:
            if hasattr(child, "lineno"):
                else_body_lines.add(child.lineno)

        if if_body_lines & self.missing_lines:
            end_line = max(if_body_lines) if if_body_lines else node.lineno
            self.uncovered_blocks.append(UncoveredBlock(
                file_path=self._current_file,
                start_line=node.lineno,
                end_line=end_line,
                function_name=self._current_function,
                class_name=self._current_class,
                code_snippet=self._get_code_snippet(node.lineno, end_line),
                block_type="if_true_branch",
                condition=f"when {condition} is True",
            ))

        if else_body_lines & self.missing_lines:
            start = min(else_body_lines)
            end = max(else_body_lines)
            self.uncovered_blocks.append(UncoveredBlock(
                file_path=self._current_file,
                start_line=start,
                end_line=end,
                function_name=self._current_function,
                class_name=self._current_class,
                code_snippet=self._get_code_snippet(start, end),
                block_type="if_false_branch",
                condition=f"when {condition} is False",
            ))

    def _analyze_except(self, node: ast.ExceptHandler) -> None:
        """Analyze uncovered exception handler."""
        exc_type = "Exception"
        if node.type:
            exc_type = self._get_source_segment(node.type)

        end_line = node.end_lineno or node.lineno
        self.uncovered_blocks.append(UncoveredBlock(
            file_path=self._current_file,
            start_line=node.lineno,
            end_line=end_line,
            function_name=self._current_function,
            class_name=self._current_class,
            code_snippet=self._get_code_snippet(node.lineno, end_line),
            block_type="exception_handler",
            condition=f"when {exc_type} is raised",
        ))

    def _analyze_return(self, node: ast.Return) -> None:
        """Analyze uncovered return statement."""
        value = "None"
        if node.value:
            value = self._get_source_segment(node.value)

        self.uncovered_blocks.append(UncoveredBlock(
            file_path=self._current_file,
            start_line=node.lineno,
            end_line=node.lineno,
            function_name=self._current_function,
            class_name=self._current_class,
            code_snippet=self._get_code_snippet(node.lineno, node.lineno),
            block_type="return_statement",
            condition=f"return {value}",
        ))

    def _analyze_raise(self, node: ast.Raise) -> None:
        """Analyze uncovered raise statement."""
        exc_type = "Exception"
        if node.exc:
            if isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name):
                exc_type = node.exc.func.id
            elif isinstance(node.exc, ast.Name):
                exc_type = node.exc.id

        self.uncovered_blocks.append(UncoveredBlock(
            file_path=self._current_file,
            start_line=node.lineno,
            end_line=node.lineno,
            function_name=self._current_function,
            class_name=self._current_class,
            code_snippet=self._get_code_snippet(node.lineno, node.lineno),
            block_type="raise_statement",
            condition=f"raise {exc_type}",
        ))

    def _analyze_loop(self, node: ast.For | ast.While) -> None:
        """Analyze uncovered loop."""
        end_line = node.end_lineno or node.lineno
        loop_type = "for" if isinstance(node, ast.For) else "while"

        self.uncovered_blocks.append(UncoveredBlock(
            file_path=self._current_file,
            start_line=node.lineno,
            end_line=end_line,
            function_name=self._current_function,
            class_name=self._current_class,
            code_snippet=self._get_code_snippet(node.lineno, end_line),
            block_type=f"{loop_type}_loop",
        ))

    def _get_source_segment(self, node: ast.AST) -> str:
        """Get source code for an AST node."""
        try:
            return ast.unparse(node)
        except Exception:
            return "..."

    def _get_code_snippet(self, start: int, end: int) -> str:
        """Get code snippet for line range (1-indexed)."""
        try:
            lines = self.source_lines[start - 1:end]
            return "\n".join(lines)
        except IndexError:
            return ""


class GapSuggestionGenerator:
    """Generate test suggestions from uncovered blocks."""

    # Regex compiled once at class level for performance
    _CAMEL_RE1 = re.compile(r"(.)([A-Z][a-z]+)")
    _CAMEL_RE2 = re.compile(r"([a-z0-9])([A-Z])")

    def generate(
        self,
        blocks: list[UncoveredBlock],
        file_path: str,
    ) -> list[GapSuggestion]:
        """Generate test suggestions for uncovered blocks."""
        suggestions = []

        for block in blocks:
            suggestion = self._create_suggestion(block, file_path)
            if suggestion:
                suggestions.append(suggestion)

        # Sort by priority, then file, then line for deterministic output
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        suggestions.sort(key=lambda s: (
            priority_order.get(s.priority, 4),
            s.test_file,
            s.covers_lines[0] if s.covers_lines else 0,
        ))

        return suggestions

    def _create_suggestion(
        self,
        block: UncoveredBlock,
        file_path: str,
    ) -> Optional[GapSuggestion]:
        """Create a test suggestion for an uncovered block."""
        test_name = self._generate_test_name(block)
        priority = self._determine_priority(block)
        template = self._generate_template(block)
        hints = self._generate_hints(block)
        test_file = self._suggest_test_file(file_path)

        return GapSuggestion(
            test_name=test_name,
            test_file=test_file,
            description=self._generate_description(block),
            covers_lines=list(range(block.start_line, block.end_line + 1)),
            priority=priority,
            code_template=template,
            setup_hints=hints,
            block_type=block.block_type,
        )

    def _generate_test_name(self, block: UncoveredBlock) -> str:
        """Generate a descriptive test name."""
        parts = ["test"]

        if block.class_name:
            parts.append(self._to_snake_case(block.class_name))

        if block.function_name:
            parts.append(block.function_name)

        type_suffixes = {
            "if_true_branch": "when_condition_true",
            "if_false_branch": "when_condition_false",
            "exception_handler": "handles_exception",
            "raise_statement": "raises_error",
            "return_statement": "returns_early",
            "for_loop": "iterates_items",
            "while_loop": "loops_until_done",
        }
        suffix = type_suffixes.get(block.block_type, "")
        if suffix:
            parts.append(suffix)

        return "_".join(parts)

    def _determine_priority(self, block: UncoveredBlock) -> str:
        """Determine priority based on block type."""
        critical_types = {"exception_handler", "raise_statement"}
        high_types = {"if_true_branch", "if_false_branch"}

        if block.block_type in critical_types:
            return "critical"
        elif block.block_type in high_types:
            return "high"
        elif block.function_name:
            return "medium"
        return "low"

    def _generate_template(self, block: UncoveredBlock) -> str:
        """Generate a test code template."""
        func = block.function_name or "function_under_test"
        cls = block.class_name

        if block.block_type == "exception_handler":
            return self._exception_test_template(func, cls, block)
        elif block.block_type == "raise_statement":
            return self._raise_test_template(func, cls, block)
        elif block.block_type in ("if_true_branch", "if_false_branch"):
            return self._branch_test_template(func, cls, block)
        else:
            return self._generic_test_template(func, cls, block)

    def _exception_test_template(
        self, func: str, cls: Optional[str], block: UncoveredBlock
    ) -> str:
        """Template for testing exception handlers."""
        exc_type = "Exception"
        if block.condition and "when " in block.condition:
            exc_type = block.condition.split("when ")[-1].replace(" is raised", "")

        if cls:
            return f'''def {self._generate_test_name(block)}():
    """Test that {cls}.{func} handles {exc_type}."""
    instance = {cls}()  # TODO: Add constructor args

    # Arrange: Set up conditions to trigger {exc_type}
    # TODO: Mock dependencies to raise {exc_type}

    # Act
    result = instance.{func}()  # TODO: Add args

    # Assert: Verify exception was handled correctly
    # TODO: Add assertions
'''
        return f'''def {self._generate_test_name(block)}():
    """Test that {func} handles {exc_type}."""
    # Arrange: Set up conditions to trigger {exc_type}
    # TODO: Mock dependencies to raise {exc_type}

    # Act
    result = {func}()  # TODO: Add args

    # Assert: Verify exception was handled correctly
    # TODO: Add assertions
'''

    def _raise_test_template(
        self, func: str, cls: Optional[str], block: UncoveredBlock
    ) -> str:
        """Template for testing raise statements."""
        exc_type = "Exception"
        if block.condition and "raise " in block.condition:
            exc_type = block.condition.split("raise ")[-1]

        if cls:
            return f'''def {self._generate_test_name(block)}():
    """Test that {cls}.{func} raises {exc_type}."""
    import pytest
    instance = {cls}()  # TODO: Add constructor args

    # Arrange: Set up invalid inputs
    # TODO: Determine what inputs trigger the error

    # Act & Assert
    with pytest.raises({exc_type}):
        instance.{func}()  # TODO: Add args that trigger error
'''
        return f'''def {self._generate_test_name(block)}():
    """Test that {func} raises {exc_type}."""
    import pytest

    # Arrange: Set up invalid inputs
    # TODO: Determine what inputs trigger the error

    # Act & Assert
    with pytest.raises({exc_type}):
        {func}()  # TODO: Add args that trigger error
'''

    def _branch_test_template(
        self, func: str, cls: Optional[str], block: UncoveredBlock
    ) -> str:
        """Template for testing conditional branches."""
        condition = block.condition or "the condition"

        if cls:
            return f'''def {self._generate_test_name(block)}():
    """Test {cls}.{func} {condition}."""
    instance = {cls}()  # TODO: Add constructor args

    # Arrange: Set up inputs so that {condition}
    # TODO: Determine inputs that satisfy this condition

    # Act
    result = instance.{func}()  # TODO: Add args

    # Assert
    # TODO: Verify behavior when {condition}
'''
        return f'''def {self._generate_test_name(block)}():
    """Test {func} {condition}."""
    # Arrange: Set up inputs so that {condition}
    # TODO: Determine inputs that satisfy this condition

    # Act
    result = {func}()  # TODO: Add args

    # Assert
    # TODO: Verify behavior when {condition}
'''

    def _generic_test_template(
        self, func: str, cls: Optional[str], block: UncoveredBlock
    ) -> str:
        """Generic test template."""
        if cls:
            return f'''def {self._generate_test_name(block)}():
    """Test {cls}.{func} (lines {block.start_line}-{block.end_line})."""
    instance = {cls}()  # TODO: Add constructor args

    # Arrange
    # TODO: Set up test data

    # Act
    result = instance.{func}()  # TODO: Add args

    # Assert
    # TODO: Add assertions
'''
        return f'''def {self._generate_test_name(block)}():
    """Test {func} (lines {block.start_line}-{block.end_line})."""
    # Arrange
    # TODO: Set up test data

    # Act
    result = {func}()  # TODO: Add args

    # Assert
    # TODO: Add assertions
'''

    def _generate_hints(self, block: UncoveredBlock) -> list[str]:
        """Generate setup hints based on the uncovered code."""
        hints = []
        snippet_lower = block.code_snippet.lower()

        if "request" in snippet_lower or "http" in snippet_lower:
            hints.append("Mock HTTP requests with responses or httpx")
        if "open(" in snippet_lower or "path" in snippet_lower:
            hints.append("Mock file operations with tmp_path fixture")
        if "await" in snippet_lower or "async" in snippet_lower:
            hints.append("Use @pytest.mark.asyncio decorator")
        if "database" in snippet_lower or "cursor" in snippet_lower or "session" in snippet_lower:
            hints.append("Mock database connections")
        if "datetime" in snippet_lower or "time." in snippet_lower:
            hints.append("Use freezegun or mock datetime.now()")
        if "random" in snippet_lower:
            hints.append("Seed random or mock random functions")
        if "environ" in snippet_lower or "getenv" in snippet_lower:
            hints.append("Use monkeypatch.setenv() for env vars")
        if "subprocess" in snippet_lower or "popen" in snippet_lower:
            hints.append("Mock subprocess calls")
        if "socket" in snippet_lower:
            hints.append("Mock socket connections")

        return hints

    def _generate_description(self, block: UncoveredBlock) -> str:
        """Generate a human-readable description."""
        parts = []

        if block.function_name:
            if block.class_name:
                parts.append(f"In {block.class_name}.{block.function_name}()")
            else:
                parts.append(f"In {block.function_name}()")

        parts.append(f"lines {block.start_line}-{block.end_line}")

        if block.condition:
            parts.append(f"- {block.condition}")

        return " ".join(parts)

    def _suggest_test_file(self, source_path: str) -> str:
        """Suggest a test file path that avoids collisions."""
        path = Path(source_path)

        # Include parent directory to avoid collisions
        # src/utils/validator.py -> tests/test_utils_validator.py
        # src/data/validator.py -> tests/test_data_validator.py
        parts = path.parts
        if len(parts) >= 2:
            parent = parts[-2]
            # Skip common non-informative parent names
            if parent not in ("src", "lib", ".", "app"):
                return f"tests/test_{parent}_{path.stem}.py"

        return f"tests/test_{path.stem}.py"

    def _to_snake_case(self, name: str) -> str:
        """Convert CamelCase to snake_case."""
        s1 = self._CAMEL_RE1.sub(r"\1_\2", name)
        return self._CAMEL_RE2.sub(r"\1_\2", s1).lower()


def find_coverage_gaps(
    coverage_json: str,
    source_root: Optional[str] = None,
) -> tuple[list[GapSuggestion], list[str]]:
    """
    Main entry point: Find what tests are missing based on coverage.

    Args:
        coverage_json: Path to coverage.json file
        source_root: Root directory for source files

    Returns:
        Tuple of (suggestions, warnings) where:
        - suggestions: List of test suggestions with templates
        - warnings: List of warning messages (e.g., files not found)

    Example:
        >>> suggestions, warnings = find_coverage_gaps("coverage.json")
        >>> print(f"Found {len(suggestions)} gaps, {len(warnings)} warnings")
    """
    parser = CoverageParser()
    report = parser.parse(coverage_json)

    all_suggestions: list[GapSuggestion] = []
    warnings: list[str] = []

    for file_path, file_cov in report.files.items():
        if not file_cov.missing_lines:
            continue

        # Resolve actual path
        actual_path = file_path
        if source_root:
            actual_path = str(Path(source_root) / file_path)

        # Try to read source file
        try:
            with open(actual_path, "r", encoding="utf-8", errors="replace") as f:
                source_code = f.read()
        except FileNotFoundError:
            warnings.append(f"Source file not found: {actual_path}")
            logger.warning(f"Source file not found: {actual_path}")
            continue
        except PermissionError:
            warnings.append(f"Permission denied reading: {actual_path}")
            logger.warning(f"Permission denied reading: {actual_path}")
            continue
        except Exception as e:
            warnings.append(f"Error reading {actual_path}: {e}")
            logger.warning(f"Error reading {actual_path}: {e}")
            continue

        # Analyze and generate suggestions
        analyzer = GapAnalyzer(source_code, file_cov.missing_lines)
        blocks = analyzer.analyze(file_path)

        generator = GapSuggestionGenerator()
        suggestions = generator.generate(blocks, file_path)
        all_suggestions.extend(suggestions)

    return all_suggestions, warnings


def print_coverage_gaps(suggestions: list[GapSuggestion]) -> None:
    """Pretty-print test suggestions to console."""
    if not suggestions:
        print("No coverage gaps found - great job!")
        return

    print(f"\n{'='*70}")
    print(f"COVERAGE GAPS: {len(suggestions)} tests needed")
    print(f"{'='*70}\n")

    for i, suggestion in enumerate(suggestions, 1):
        priority_marker = {
            "critical": "[!!]",
            "high": "[! ]",
            "medium": "[  ]",
            "low": "[  ]",
        }.get(suggestion.priority, "[  ]")

        print(f"{i}. {priority_marker} [{suggestion.priority.upper():8}] {suggestion.test_name}")
        print(f"   File: {suggestion.test_file}")
        print(f"   Covers: {suggestion.description}")

        if suggestion.setup_hints:
            print(f"   Hints: {', '.join(suggestion.setup_hints)}")

        print(f"\n   Template:")
        for line in suggestion.code_template.splitlines():
            print(f"   {line}")
        print()

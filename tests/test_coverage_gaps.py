"""Tests for analyzer.coverage_gaps module."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from analyzer.coverage_gaps import (
    CoverageParser,
    CoverageReport,
    FileCoverage,
    GapAnalyzer,
    GapSuggestionGenerator,
    UncoveredBlock,
    GapSuggestion,
    find_coverage_gaps,
)


class TestCoverageParser:
    """Tests for CoverageParser."""

    def test_parse_empty_coverage(self, tmp_path):
        """Test parsing coverage.json with no files."""
        coverage_file = tmp_path / "coverage.json"
        coverage_file.write_text(json.dumps({"files": {}}))

        parser = CoverageParser()
        report = parser.parse(str(coverage_file))

        assert report.total_covered == 0
        assert report.total_missing == 0
        assert len(report.files) == 0
        assert report.coverage_percent == 100.0

    def test_parse_basic_coverage(self, tmp_path):
        """Test parsing coverage.json with basic data."""
        coverage_data = {
            "files": {
                "src/module.py": {
                    "executed_lines": [1, 2, 3, 5, 6],
                    "missing_lines": [4, 7, 8],
                    "excluded_lines": [9],
                }
            }
        }
        coverage_file = tmp_path / "coverage.json"
        coverage_file.write_text(json.dumps(coverage_data))

        parser = CoverageParser()
        report = parser.parse(str(coverage_file))

        assert report.total_covered == 5
        assert report.total_missing == 3
        assert len(report.files) == 1
        assert "src/module.py" in report.files

        file_cov = report.files["src/module.py"]
        assert file_cov.covered_lines == {1, 2, 3, 5, 6}
        assert file_cov.missing_lines == {4, 7, 8}
        assert file_cov.excluded_lines == {9}

    def test_parse_with_branches(self, tmp_path):
        """Test parsing coverage.json with branch data."""
        coverage_data = {
            "files": {
                "src/module.py": {
                    "executed_lines": [1, 2],
                    "missing_lines": [3],
                    "excluded_lines": [],
                    "missing_branches": {
                        "2": [3, 5]
                    }
                }
            }
        }
        coverage_file = tmp_path / "coverage.json"
        coverage_file.write_text(json.dumps(coverage_data))

        parser = CoverageParser()
        report = parser.parse(str(coverage_file))

        file_cov = report.files["src/module.py"]
        assert file_cov.missing_branches == [(2, 3), (2, 5)]

    def test_parse_invalid_json(self, tmp_path):
        """Test parsing invalid JSON raises error."""
        coverage_file = tmp_path / "coverage.json"
        coverage_file.write_text("not valid json")

        parser = CoverageParser()
        with pytest.raises(json.JSONDecodeError):
            parser.parse(str(coverage_file))

    def test_parse_missing_file(self):
        """Test parsing non-existent file raises error."""
        parser = CoverageParser()
        with pytest.raises(FileNotFoundError):
            parser.parse("nonexistent.json")


class TestFileCoverage:
    """Tests for FileCoverage dataclass."""

    def test_coverage_percent_full(self):
        """Test 100% coverage."""
        fc = FileCoverage(
            path="test.py",
            covered_lines={1, 2, 3},
            missing_lines=set(),
            excluded_lines=set(),
            missing_branches=[],
        )
        assert fc.coverage_percent == 100.0

    def test_coverage_percent_partial(self):
        """Test partial coverage."""
        fc = FileCoverage(
            path="test.py",
            covered_lines={1, 2},
            missing_lines={3, 4},
            excluded_lines=set(),
            missing_branches=[],
        )
        assert fc.coverage_percent == 50.0

    def test_coverage_percent_empty(self):
        """Test empty file returns 100%."""
        fc = FileCoverage(
            path="test.py",
            covered_lines=set(),
            missing_lines=set(),
            excluded_lines=set(),
            missing_branches=[],
        )
        assert fc.coverage_percent == 100.0


class TestGapAnalyzer:
    """Tests for GapAnalyzer AST analysis."""

    def test_analyze_uncovered_if_branch(self):
        """Test detecting uncovered if branch."""
        source = '''def foo(x):
    if x > 0:
        return "positive"
    return "not positive"
'''
        analyzer = GapAnalyzer(source, missing_lines={3})
        blocks = analyzer.analyze("test.py")

        assert len(blocks) == 1
        assert blocks[0].block_type == "if_true_branch"
        assert blocks[0].function_name == "foo"
        assert "x > 0" in blocks[0].condition

    def test_analyze_uncovered_else_branch(self):
        """Test detecting uncovered else branch."""
        source = '''def foo(x):
    if x > 0:
        return "positive"
    else:
        return "not positive"
'''
        analyzer = GapAnalyzer(source, missing_lines={5})
        blocks = analyzer.analyze("test.py")

        assert len(blocks) == 1
        assert blocks[0].block_type == "if_false_branch"

    def test_analyze_uncovered_exception_handler(self):
        """Test detecting uncovered exception handler."""
        source = '''def foo():
    try:
        risky_call()
    except ValueError:
        handle_error()
'''
        analyzer = GapAnalyzer(source, missing_lines={5})
        blocks = analyzer.analyze("test.py")

        assert len(blocks) == 1
        assert blocks[0].block_type == "exception_handler"
        assert "ValueError" in blocks[0].condition

    def test_analyze_uncovered_raise(self):
        """Test detecting uncovered raise statement."""
        source = '''def foo(x):
    if x < 0:
        raise ValueError("negative")
    return x
'''
        analyzer = GapAnalyzer(source, missing_lines={3})
        blocks = analyzer.analyze("test.py")

        assert len(blocks) >= 1
        raise_blocks = [b for b in blocks if b.block_type == "raise_statement"]
        assert len(raise_blocks) == 1
        assert "ValueError" in raise_blocks[0].condition

    def test_analyze_uncovered_loop(self):
        """Test detecting uncovered loop."""
        source = '''def foo(items):
    for item in items:
        process(item)
'''
        analyzer = GapAnalyzer(source, missing_lines={3})
        blocks = analyzer.analyze("test.py")

        assert len(blocks) >= 1
        loop_blocks = [b for b in blocks if "loop" in b.block_type]
        assert len(loop_blocks) == 1
        assert loop_blocks[0].block_type == "for_loop"

    def test_analyze_with_class(self):
        """Test detecting uncovered code in class method."""
        source = '''class MyClass:
    def method(self, x):
        if x:
            return True
        return False
'''
        analyzer = GapAnalyzer(source, missing_lines={4})
        blocks = analyzer.analyze("test.py")

        assert len(blocks) == 1
        assert blocks[0].class_name == "MyClass"
        assert blocks[0].function_name == "method"

    def test_analyze_syntax_error_fallback(self):
        """Test fallback to line-based analysis on syntax error."""
        source = "def broken(\n"  # Invalid Python
        analyzer = GapAnalyzer(source, missing_lines={1})
        blocks = analyzer.analyze("test.py")

        # Should still return something via fallback
        assert len(blocks) == 1
        assert blocks[0].block_type == "code_block"

    def test_analyze_no_missing_lines(self):
        """Test with no missing lines."""
        source = '''def foo():
    return 42
'''
        analyzer = GapAnalyzer(source, missing_lines=set())
        blocks = analyzer.analyze("test.py")

        assert len(blocks) == 0


class TestGapSuggestionGenerator:
    """Tests for GapSuggestionGenerator."""

    def test_generate_test_name(self):
        """Test generating test names."""
        generator = GapSuggestionGenerator()
        block = UncoveredBlock(
            file_path="test.py",
            start_line=1,
            end_line=1,
            function_name="validate",
            class_name="Validator",
            block_type="exception_handler",
        )

        name = generator._generate_test_name(block)
        assert "test" in name
        assert "validator" in name
        assert "validate" in name
        assert "handles_exception" in name

    def test_priority_critical_for_exception(self):
        """Test critical priority for exception handlers."""
        generator = GapSuggestionGenerator()
        block = UncoveredBlock(
            file_path="test.py",
            start_line=1,
            end_line=1,
            block_type="exception_handler",
        )

        priority = generator._determine_priority(block)
        assert priority == "critical"

    def test_priority_critical_for_raise(self):
        """Test critical priority for raise statements."""
        generator = GapSuggestionGenerator()
        block = UncoveredBlock(
            file_path="test.py",
            start_line=1,
            end_line=1,
            block_type="raise_statement",
        )

        priority = generator._determine_priority(block)
        assert priority == "critical"

    def test_priority_high_for_branch(self):
        """Test high priority for conditional branches."""
        generator = GapSuggestionGenerator()
        block = UncoveredBlock(
            file_path="test.py",
            start_line=1,
            end_line=1,
            block_type="if_true_branch",
        )

        priority = generator._determine_priority(block)
        assert priority == "high"

    def test_suggest_test_file_avoids_collision(self):
        """Test that test file paths include parent directory."""
        generator = GapSuggestionGenerator()

        # Should include parent dir
        path1 = generator._suggest_test_file("utils/validator.py")
        path2 = generator._suggest_test_file("data/validator.py")

        assert path1 != path2
        assert "utils" in path1
        assert "data" in path2

    def test_suggest_test_file_skips_common_parents(self):
        """Test that common parent dirs like 'src' are skipped."""
        generator = GapSuggestionGenerator()

        path = generator._suggest_test_file("src/validator.py")
        assert path == "tests/test_validator.py"

    def test_generate_hints_http(self):
        """Test HTTP hints are generated."""
        generator = GapSuggestionGenerator()
        block = UncoveredBlock(
            file_path="test.py",
            start_line=1,
            end_line=1,
            code_snippet="response = requests.get(url)",
        )

        hints = generator._generate_hints(block)
        assert any("HTTP" in h or "http" in h for h in hints)

    def test_generate_hints_async(self):
        """Test async hints are generated."""
        generator = GapSuggestionGenerator()
        block = UncoveredBlock(
            file_path="test.py",
            start_line=1,
            end_line=1,
            code_snippet="await some_async_call()",
        )

        hints = generator._generate_hints(block)
        assert any("asyncio" in h for h in hints)

    def test_to_snake_case(self):
        """Test CamelCase to snake_case conversion."""
        generator = GapSuggestionGenerator()

        assert generator._to_snake_case("MyClass") == "my_class"
        assert generator._to_snake_case("HTTPHandler") == "http_handler"
        assert generator._to_snake_case("simple") == "simple"


class TestFindCoverageGaps:
    """Tests for the main find_coverage_gaps function."""

    def test_find_gaps_basic(self, tmp_path):
        """Test basic gap finding."""
        # Create source file
        source_file = tmp_path / "module.py"
        source_file.write_text('''def foo(x):
    if x > 0:
        return "positive"
    return "negative"
''')

        # Create coverage file
        coverage_data = {
            "files": {
                str(source_file): {
                    "executed_lines": [1, 2, 4],
                    "missing_lines": [3],
                    "excluded_lines": [],
                }
            }
        }
        coverage_file = tmp_path / "coverage.json"
        coverage_file.write_text(json.dumps(coverage_data))

        suggestions, warnings = find_coverage_gaps(str(coverage_file))

        assert len(warnings) == 0
        assert len(suggestions) >= 1
        assert suggestions[0].block_type == "if_true_branch"

    def test_find_gaps_missing_source(self, tmp_path):
        """Test warning when source file is missing."""
        coverage_data = {
            "files": {
                "nonexistent.py": {
                    "executed_lines": [1],
                    "missing_lines": [2],
                    "excluded_lines": [],
                }
            }
        }
        coverage_file = tmp_path / "coverage.json"
        coverage_file.write_text(json.dumps(coverage_data))

        suggestions, warnings = find_coverage_gaps(str(coverage_file))

        assert len(warnings) == 1
        assert "not found" in warnings[0]

    def test_find_gaps_with_source_root(self, tmp_path):
        """Test using source_root to locate files."""
        # Create source in subdirectory
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        source_file = src_dir / "module.py"
        source_file.write_text('''def foo():
    return 42
''')

        # Coverage uses relative path
        coverage_data = {
            "files": {
                "module.py": {
                    "executed_lines": [1],
                    "missing_lines": [2],
                    "excluded_lines": [],
                }
            }
        }
        coverage_file = tmp_path / "coverage.json"
        coverage_file.write_text(json.dumps(coverage_data))

        suggestions, warnings = find_coverage_gaps(
            str(coverage_file),
            source_root=str(src_dir),
        )

        assert len(warnings) == 0

    def test_find_gaps_empty_coverage(self, tmp_path):
        """Test with no missing lines."""
        coverage_data = {
            "files": {
                "module.py": {
                    "executed_lines": [1, 2, 3],
                    "missing_lines": [],
                    "excluded_lines": [],
                }
            }
        }
        coverage_file = tmp_path / "coverage.json"
        coverage_file.write_text(json.dumps(coverage_data))

        suggestions, warnings = find_coverage_gaps(str(coverage_file))

        assert len(suggestions) == 0
        assert len(warnings) == 0


class TestGapSuggestionDataclass:
    """Tests for GapSuggestion dataclass."""

    def test_to_dict(self):
        """Test converting suggestion to dict."""
        suggestion = GapSuggestion(
            test_name="test_foo",
            test_file="tests/test_module.py",
            description="In foo() lines 1-5",
            covers_lines=[1, 2, 3, 4, 5],
            priority="high",
            code_template="def test_foo(): pass",
            setup_hints=["Mock HTTP"],
            block_type="if_true_branch",
        )

        d = suggestion.to_dict()

        assert d["test_name"] == "test_foo"
        assert d["priority"] == "high"
        assert d["covers_lines"] == [1, 2, 3, 4, 5]
        assert "Mock HTTP" in d["setup_hints"]

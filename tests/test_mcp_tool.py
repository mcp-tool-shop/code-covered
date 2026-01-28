"""Tests for the MCP adapter (mcp_code_covered.tool)."""

import json
import shutil
import pytest
from pathlib import Path

from mcp_code_covered.tool import (
    handle,
    _load_coverage,
    _compute_exit_code,
    _error_response,
    PRIORITY_SCORE,
)
from analyzer.coverage_gaps import GapSuggestion

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "mcp"


class TestLoadCoverage:
    """Tests for _load_coverage helper."""

    def test_load_inline_coverage(self):
        """Test loading inline coverage data."""
        coverage_data = {
            "files": {
                "src/module.py": {
                    "executed_lines": [1, 2, 3],
                    "missing_lines": [4, 5],
                }
            }
        }
        result = _load_coverage(coverage_data)
        assert result == coverage_data

    def test_load_inline_coverage_with_meta(self):
        """Test loading inline coverage with meta key."""
        coverage_data = {
            "meta": {"version": "7.0"},
            "files": {},
        }
        result = _load_coverage(coverage_data)
        assert result == coverage_data

    def test_load_coverage_invalid_format(self):
        """Test loading invalid coverage data raises ValueError."""
        with pytest.raises(ValueError, match="must contain 'files' key"):
            _load_coverage({"invalid": "data"})

    def test_load_coverage_not_dict(self):
        """Test loading non-dict raises ValueError."""
        with pytest.raises(ValueError, match="must be an object"):
            _load_coverage("not a dict")

    def test_load_artifact_with_locator(self, tmp_path):
        """Test loading coverage from artifact with locator."""
        coverage_data = {
            "files": {"test.py": {"executed_lines": [1], "missing_lines": []}}
        }
        coverage_file = tmp_path / "coverage.json"
        coverage_file.write_text(json.dumps(coverage_data))

        artifact = {
            "artifact_id": "abc123",
            "media_type": "application/json",
            "locator": str(coverage_file),
        }
        result = _load_coverage(artifact)
        assert result == coverage_data

    def test_load_artifact_with_resolver(self):
        """Test loading coverage via artifact resolver."""
        coverage_data = {
            "files": {"test.py": {"executed_lines": [1], "missing_lines": []}}
        }

        def resolver(artifact_id: str) -> bytes:
            assert artifact_id == "abc123"
            return json.dumps(coverage_data).encode("utf-8")

        artifact = {
            "artifact_id": "abc123",
            "media_type": "application/json",
        }
        result = _load_coverage(artifact, artifact_resolver=resolver)
        assert result == coverage_data

    def test_load_artifact_missing_locator_and_resolver(self):
        """Test artifact without locator or resolver raises ValueError."""
        artifact = {
            "artifact_id": "abc123",
            "media_type": "application/json",
        }
        with pytest.raises(ValueError, match="requires either artifact_resolver or locator"):
            _load_coverage(artifact)

    def test_load_artifact_file_not_found(self, tmp_path):
        """Test artifact with non-existent locator raises FileNotFoundError."""
        artifact = {
            "artifact_id": "abc123",
            "media_type": "application/json",
            "locator": str(tmp_path / "nonexistent.json"),
        }
        with pytest.raises(FileNotFoundError):
            _load_coverage(artifact)


class TestComputeExitCode:
    """Tests for _compute_exit_code."""

    def _make_suggestion(self, priority: str) -> GapSuggestion:
        return GapSuggestion(
            test_name=f"test_{priority}",
            test_file="tests/test.py",
            description="Test description",
            covers_lines=[1],
            priority=priority,
            code_template="def test(): pass",
            setup_hints=[],
            block_type="code_block",
        )

    def test_exit_code_none_always_zero(self):
        """Test fail_on='none' always returns 0."""
        suggestions = [self._make_suggestion("critical")]
        assert _compute_exit_code(suggestions, "none") == 0

    def test_exit_code_any_with_suggestions(self):
        """Test fail_on='any' returns 2 when there are suggestions."""
        suggestions = [self._make_suggestion("low")]
        assert _compute_exit_code(suggestions, "any") == 2

    def test_exit_code_any_without_suggestions(self):
        """Test fail_on='any' returns 0 when no suggestions."""
        assert _compute_exit_code([], "any") == 0

    def test_exit_code_critical_threshold(self):
        """Test fail_on='critical' only fails on critical."""
        critical = [self._make_suggestion("critical")]
        high = [self._make_suggestion("high")]

        assert _compute_exit_code(critical, "critical") == 2
        assert _compute_exit_code(high, "critical") == 0

    def test_exit_code_high_threshold(self):
        """Test fail_on='high' fails on high or critical."""
        critical = [self._make_suggestion("critical")]
        high = [self._make_suggestion("high")]
        medium = [self._make_suggestion("medium")]

        assert _compute_exit_code(critical, "high") == 2
        assert _compute_exit_code(high, "high") == 2
        assert _compute_exit_code(medium, "high") == 0


class TestHandle:
    """Tests for the main handle function."""

    @pytest.fixture
    def sample_source(self, tmp_path):
        """Create a sample source file for testing."""
        source = tmp_path / "src" / "module.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("""
def process(data):
    if data is None:
        raise ValueError("data cannot be None")
    return data.strip()
""")
        return source

    @pytest.fixture
    def sample_coverage(self, sample_source):
        """Create sample coverage data."""
        return {
            "files": {
                str(sample_source): {
                    "executed_lines": [2, 5],
                    "missing_lines": [3, 4],
                    "excluded_lines": [],
                }
            }
        }

    def test_handle_inline_coverage(self, sample_coverage, sample_source):
        """Test handling inline coverage data."""
        request = {"coverage": sample_coverage}
        response = handle(request)

        assert response["exit_code"] == 0
        assert "result" in response
        assert response["result"]["files_analyzed"] == 1
        assert response["result"]["files_with_gaps"] == 1
        assert len(response["result"]["suggestions"]) > 0

    def test_handle_with_artifact_locator(self, sample_coverage, sample_source, tmp_path):
        """Test handling artifact reference with locator."""
        coverage_file = tmp_path / "coverage.json"
        coverage_file.write_text(json.dumps(sample_coverage))

        request = {
            "coverage": {
                "artifact_id": "test-artifact",
                "media_type": "application/json",
                "locator": str(coverage_file),
            }
        }
        response = handle(request)

        assert response["exit_code"] == 0
        assert response["result"]["files_analyzed"] == 1

    def test_handle_with_text_format(self, sample_coverage, sample_source):
        """Test requesting text format output."""
        request = {
            "coverage": sample_coverage,
            "format": "text",
        }
        response = handle(request)

        assert "text" in response
        assert "code-covered" in response["text"]
        assert "Coverage:" in response["text"]

    def test_handle_with_fail_on_critical(self, sample_coverage, sample_source):
        """Test fail_on='critical' sets correct exit code."""
        request = {
            "coverage": sample_coverage,
            "fail_on": "critical",
        }
        response = handle(request)

        # Should have critical suggestions (raise ValueError)
        has_critical = any(
            s["priority"] == "critical"
            for s in response["result"]["suggestions"]
        )
        if has_critical:
            assert response["exit_code"] == 2
        else:
            assert response["exit_code"] == 0

    def test_handle_with_priority_filter(self, sample_coverage, sample_source):
        """Test filtering by priority."""
        request = {
            "coverage": sample_coverage,
            "priority_filter": "critical",
        }
        response = handle(request)

        for s in response["result"]["suggestions"]:
            assert s["priority"] == "critical"

    def test_handle_with_limit(self, sample_coverage, sample_source):
        """Test limiting number of suggestions."""
        request = {
            "coverage": sample_coverage,
            "limit": 1,
        }
        response = handle(request)

        assert len(response["result"]["suggestions"]) <= 1
        # total_suggestions should reflect count before limit
        assert response["result"]["total_suggestions"] >= len(
            response["result"]["suggestions"]
        )

    def test_handle_invalid_coverage(self):
        """Test handling invalid coverage data."""
        request = {"coverage": {"invalid": "data"}}
        response = handle(request)

        assert response["exit_code"] == 1
        assert len(response["warnings"]) > 0
        assert "must contain 'files' key" in response["warnings"][0]

    def test_handle_missing_source_file(self, tmp_path):
        """Test handling when source file is missing."""
        coverage = {
            "files": {
                "nonexistent/module.py": {
                    "executed_lines": [1],
                    "missing_lines": [2],
                }
            }
        }
        request = {"coverage": coverage}
        response = handle(request)

        # Should succeed but with warnings
        assert response["exit_code"] == 0
        assert any("not found" in w for w in response["warnings"])

    def test_handle_empty_coverage(self):
        """Test handling empty coverage report."""
        request = {"coverage": {"files": {}}}
        response = handle(request)

        assert response["exit_code"] == 0
        assert response["result"]["files_analyzed"] == 0
        assert response["result"]["suggestions"] == []
        assert response["result"]["coverage_percent"] == 100.0

    def test_handle_determinism(self, sample_coverage, sample_source):
        """Test that same request produces identical results."""
        request = {"coverage": sample_coverage}

        response1 = handle(request)
        response2 = handle(request)

        # Results should be identical
        assert response1["result"] == response2["result"]
        assert response1["warnings"] == response2["warnings"]

    def test_handle_by_priority_counts(self, sample_coverage, sample_source):
        """Test by_priority counts are correct."""
        request = {"coverage": sample_coverage}
        response = handle(request)

        by_priority = response["result"]["by_priority"]
        suggestions = response["result"]["suggestions"]

        # Verify counts match actual suggestions
        for priority in ["critical", "high", "medium", "low"]:
            expected = sum(1 for s in suggestions if s["priority"] == priority)
            # Note: by_priority is counted before any limit
            assert by_priority[priority] >= expected


class TestErrorResponse:
    """Tests for _error_response helper."""

    def test_error_response_structure(self):
        """Test error response has correct structure."""
        response = _error_response("Test error message")

        assert response["exit_code"] == 1
        assert response["result"]["coverage_percent"] == 0
        assert response["result"]["files_analyzed"] == 0
        assert response["result"]["suggestions"] == []
        assert "Test error message" in response["warnings"]


class TestResponseSchema:
    """Tests to verify response matches schema expectations."""

    def test_response_has_required_fields(self, tmp_path):
        """Test response contains all required fields."""
        source = tmp_path / "test.py"
        source.write_text("x = 1")

        coverage = {
            "files": {
                str(source): {
                    "executed_lines": [1],
                    "missing_lines": [],
                }
            }
        }
        request = {"coverage": coverage}
        response = handle(request)

        # Required top-level fields
        assert "exit_code" in response
        assert "result" in response

        # Required result fields
        result = response["result"]
        assert "coverage_percent" in result
        assert "files_analyzed" in result
        assert "files_with_gaps" in result
        assert "total_suggestions" in result
        assert "suggestions" in result
        assert "by_priority" in result

    def test_suggestion_has_required_fields(self, tmp_path):
        """Test suggestions contain all required fields."""
        source = tmp_path / "test.py"
        source.write_text("""
def foo():
    if True:
        return 1
    return 2
""")
        coverage = {
            "files": {
                str(source): {
                    "executed_lines": [2, 3, 4],
                    "missing_lines": [5],
                }
            }
        }
        request = {"coverage": coverage}
        response = handle(request)

        for suggestion in response["result"]["suggestions"]:
            assert "test_name" in suggestion
            assert "test_file" in suggestion
            assert "description" in suggestion
            assert "covers_lines" in suggestion
            assert "priority" in suggestion
            assert "code_template" in suggestion
            assert "block_type" in suggestion


class TestGoldenFixture:
    """Golden fixture test to ensure MCP contract stability."""

    def test_golden_host_call(self, tmp_path):
        """
        End-to-end test simulating a real MCP host call.

        This test:
        1. Uses a fixed request/source fixture
        2. Verifies response structure matches expected contract
        3. Ensures deterministic output across runs
        """
        # Copy source fixture to temp location matching coverage paths
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        golden_source = FIXTURES_DIR / "golden_source.py"
        shutil.copy(golden_source, src_dir / "validator.py")

        # Load request fixture and update paths
        request = json.loads((FIXTURES_DIR / "golden_request.json").read_text())

        # Update coverage paths to point to temp location
        request["coverage"]["files"] = {
            str(src_dir / "validator.py"): request["coverage"]["files"]["src/validator.py"]
        }

        # Execute
        response = handle(request)

        # Verify contract
        assert response["exit_code"] in [0, 2]
        assert "result" in response
        assert "warnings" in response
        assert isinstance(response["warnings"], list)

        result = response["result"]
        assert "coverage_percent" in result
        assert "files_analyzed" in result
        assert "files_with_gaps" in result
        assert "total_suggestions" in result
        assert "suggestions" in result
        assert "by_priority" in result

        # Verify determinism: run twice, same result
        response2 = handle(request)
        assert response["result"] == response2["result"]
        assert response["warnings"] == response2["warnings"]

        # Verify exit code reflects critical gaps
        has_critical = result["by_priority"]["critical"] > 0
        if request.get("fail_on") == "critical" and has_critical:
            assert response["exit_code"] == 2


class TestFailOnLimitInteraction:
    """Tests for fail_on and limit interaction (gating contract)."""

    @pytest.fixture
    def multi_gap_source(self, tmp_path):
        """Create source with multiple gap types."""
        source = tmp_path / "multi.py"
        source.write_text("""
def process(data):
    if data is None:
        raise ValueError("no data")
    if not data:
        return []
    for item in data:
        yield item
""")
        return source

    @pytest.fixture
    def multi_gap_coverage(self, multi_gap_source):
        """Coverage with multiple gap priorities."""
        return {
            "files": {
                str(multi_gap_source): {
                    "executed_lines": [2, 5, 7],
                    "missing_lines": [3, 4, 6, 8],  # raise, if-true, return, for-loop
                }
            }
        }

    def test_fail_on_evaluates_before_limit(self, multi_gap_coverage):
        """
        Verify fail_on is evaluated BEFORE limit is applied.

        This ensures CI gating sees all filtered gaps, not just top N.
        """
        # Get all suggestions first
        full_request = {"coverage": multi_gap_coverage, "fail_on": "any"}
        full_response = handle(full_request)
        total_gaps = full_response["result"]["total_suggestions"]

        # Now request with limit=1 but fail_on="any"
        limited_request = {
            "coverage": multi_gap_coverage,
            "fail_on": "any",
            "limit": 1,
        }
        limited_response = handle(limited_request)

        # Should still fail even though only 1 suggestion returned
        assert limited_response["exit_code"] == 2
        assert len(limited_response["result"]["suggestions"]) == 1
        # total_suggestions should reflect pre-limit count
        assert limited_response["result"]["total_suggestions"] == total_gaps

    def test_fail_on_respects_priority_filter(self, multi_gap_coverage):
        """
        Verify fail_on respects priority_filter.

        If user filters to high+ only, fail_on should only see high+ gaps.
        """
        # Filter to high only (excludes medium/low)
        request = {
            "coverage": multi_gap_coverage,
            "priority_filter": "high",
            "fail_on": "any",
        }
        response = handle(request)

        # Should only see high+ suggestions
        for s in response["result"]["suggestions"]:
            assert s["priority"] in ["critical", "high"]

        # Exit code reflects filtered set
        if response["result"]["total_suggestions"] > 0:
            assert response["exit_code"] == 2
        else:
            assert response["exit_code"] == 0

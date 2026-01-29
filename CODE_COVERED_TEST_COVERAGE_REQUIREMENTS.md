# Code-Covered Test Coverage Requirements

**Goal**: Achieve 100% test coverage across all modules

**Current Status**:
- Source modules: 4 files (cli.py, analyzer/coverage_gaps.py, mcp_code_covered/tool.py + __init__ files)
- Test files: 3 files (test_cli.py, test_coverage_gaps.py, test_mcp_tool.py)
- **Estimated coverage**: ~75-80% (good foundation, missing edge cases and error scenarios)

---

## Module: `cli.py` (170 lines)

### Currently Tested
- ✅ Help text displayed with no args
- ✅ Missing coverage file error
- ✅ JSON output format
- ✅ Output file creation

### Missing Tests (Priority: MEDIUM)

#### 1. Verbose Output Mode
**Lines**: 65-74

```python
def test_verbose_shows_full_templates():
    """Test --verbose displays complete test templates."""
    # With --verbose flag
    # Should show full code_template for each suggestion

def test_non_verbose_shows_summary():
    """Test default mode shows abbreviated output."""
    # Without --verbose
    # Should show "... and N more (use -v to see all)"
```

#### 2. Priority Filtering
**Lines**: 52-54

```python
def test_priority_filter_critical():
    """Test --priority=critical filters suggestions."""
    # Only critical priority suggestions shown

def test_priority_filter_high():
    """Test --priority=high includes high and critical."""
    # Should show high and critical

def test_priority_filter_low():
    """Test --priority=low shows all priorities."""
    # All suggestions included
```

#### 3. Limit Flag
**Lines**: 55-56

```python
def test_limit_flag_reduces_output():
    """Test --limit flag caps number of suggestions."""
    # 50 suggestions, --limit=10
    # Should show only 10

def test_limit_with_priority():
    """Test --limit applies after priority filter."""
    # --priority=critical --limit=5
    # Should limit to 5 critical suggestions
```

#### 4. Source Root Path Resolution
**Lines**: 43-46

```python
def test_source_root_resolves_relative_paths():
    """Test --source-root correctly locates source files."""
    # Coverage uses relative paths
    # --source-root makes them absolute

def test_source_root_with_nested_structure():
    """Test source-root with deep directory structure."""
    # src/package/subpackage/module.py
    # Should resolve correctly
```

#### 5. Warning Display
**Lines**: 65-74

```python
def test_warnings_shown_when_files_not_found():
    """Test warnings displayed for missing source files."""
    # Coverage references files that don't exist
    # Should show warning list

def test_warnings_limited_without_verbose():
    """Test warnings capped at 5 without -v."""
    # 10 warnings, no -v
    # Should show first 5 + "... and 5 more"

def test_warnings_all_shown_with_verbose():
    """Test all warnings shown with -v."""
    # 10 warnings, with -v
    # Should show all 10
```

#### 6. Coverage Summary Display
**Lines**: 60-64

```python
def test_coverage_summary_formatting():
    """Test coverage percentage and line counts displayed."""
    # Should show coverage %, lines covered/total

def test_files_with_gaps_count():
    """Test files with gaps vs total files."""
    # Should show "5 files (2 with gaps)"

def test_perfect_coverage_message():
    """Test message when coverage is 100%."""
    # All lines covered
    # Should show "No coverage gaps found"
```

#### 7. Error Handling
**Lines**: 48-52, 57-59

```python
def test_invalid_json_in_coverage():
    """Test error when coverage.json is malformed."""
    # Invalid JSON
    # Should show parse error

def test_invalid_coverage_structure():
    """Test error when coverage.json missing required fields."""
    # Valid JSON but wrong schema
    # Should show structure error

def test_permission_denied_source_file():
    """Test handling of inaccessible source files."""
    # Source file not readable
    # Should add to warnings, not crash

def test_permission_denied_output_file():
    """Test error when output file can't be written."""
    # -o flag to read-only location
    # Should show clear error message
```

#### 8. Output File Writing
**Lines**: 115-125

```python
def test_output_file_includes_all_suggestions():
    """Test -o writes all suggestions regardless of display limit."""
    # 50 suggestions, display shows 10
    # Output file should have all 50

def test_output_file_includes_metadata():
    """Test output file has priority and hints comments."""
    # Each test stub has priority and hints

def test_output_file_imports():
    """Test output file has pytest import."""
    # Should include "import pytest"

def test_output_file_overwrites_existing():
    """Test -o overwrites existing file."""
    # Existing file at output path
    # Should be replaced
```

---

## Module: `analyzer/coverage_gaps.py` (900+ lines)

### Currently Tested
- ✅ CoverageParser basic parsing
- ✅ Branch data parsing
- ✅ GapAnalyzer basic AST analysis
- ✅ Exception handler detection
- ✅ Raise statement detection
- ✅ Priority assignment
- ✅ Test name generation
- ✅ find_coverage_gaps main function
- ✅ Golden output validation

### Missing Tests (Priority: HIGH)

#### 1. CoverageParser Edge Cases
**Lines**: 95-130

```python
def test_parse_coverage_with_no_totals():
    """Test parsing when totals field is missing."""
    # Coverage file without totals
    # Should compute from file data

def test_parse_coverage_multiple_files():
    """Test parsing coverage for many files."""
    # 100+ files in coverage report
    # Should handle efficiently

def test_parse_coverage_with_unicode_paths():
    """Test parsing with unicode in file paths."""
    # Paths with emoji or non-ASCII
    # Should not crash

def test_parse_coverage_with_windows_paths():
    """Test parsing with backslash paths."""
    # Windows-style paths: C:\path\to\file.py
    # Should handle correctly

def test_parse_coverage_percentage_rounding():
    """Test coverage percentage rounds correctly."""
    # 33.333...% coverage
    # Should round appropriately
```

#### 2. GapAnalyzer AST Edge Cases
**Lines**: 133-258

```python
def test_analyze_nested_if_statements():
    """Test analyzing deeply nested conditionals."""
    # if inside if inside if
    # Should track all branches

def test_analyze_complex_boolean_conditions():
    """Test analyzing compound boolean expressions."""
    # if x > 0 and y < 10 or z == 5:
    # Should capture full condition

def test_analyze_list_comprehension():
    """Test analyzing uncovered list comprehension."""
    # [x for x in items if condition]
    # Should detect uncovered parts

def test_analyze_lambda_function():
    """Test analyzing uncovered lambda."""
    # lambda x: x + 1
    # Should handle gracefully

def test_analyze_decorator():
    """Test analyzing uncovered decorator."""
    # @decorator def foo():
    # Should handle decorator line

def test_analyze_context_manager():
    """Test analyzing uncovered with statement."""
    # with open(...) as f:
    # Should detect uncovered context manager

def test_analyze_async_context_manager():
    """Test analyzing uncovered async with."""
    # async with resource:
    # Should detect correctly

def test_analyze_match_statement():
    """Test analyzing uncovered match/case (Python 3.10+)."""
    # match value: case pattern:
    # Should handle pattern matching

def test_analyze_walrus_operator():
    """Test analyzing uncovered walrus operator."""
    # if (n := len(data)) > 10:
    # Should capture condition

def test_analyze_type_hints():
    """Test analyzer handles type hints gracefully."""
    # def foo(x: int) -> str:
    # Type hints shouldn't break analysis

def test_analyze_multiline_string():
    """Test analyzer handles docstrings and multiline strings."""
    # Triple-quoted strings
    # Should not confuse line tracking
```

#### 3. GapAnalyzer Block Detection
**Lines**: 260-358

```python
def test_analyze_consecutive_missing_lines():
    """Test grouping consecutive missing lines."""
    # Lines 5-10 all missing
    # Should group as single block

def test_analyze_scattered_missing_lines():
    """Test handling scattered missing lines."""
    # Lines 5, 8, 12, 18 missing
    # Should create separate blocks

def test_analyze_duplicate_block_prevention():
    """Test analyzer doesn't create duplicate blocks."""
    # Same code block detected multiple ways
    # Should deduplicate

def test_analyze_whole_function_uncovered():
    """Test analyzing completely uncovered function."""
    # Function never called
    # Should detect as single block

def test_analyze_partial_function_uncovered():
    """Test analyzing partially covered function."""
    # Function called but some branches missed
    # Should detect only uncovered parts
```

#### 4. Exception Handler Analysis
**Lines**: 305-322

```python
def test_analyze_bare_except():
    """Test analyzing bare except clause."""
    # except:  (no exception type)
    # Should handle gracefully

def test_analyze_multiple_exception_types():
    """Test analyzing except with multiple types."""
    # except (ValueError, TypeError):
    # Should capture both types

def test_analyze_exception_with_as():
    """Test analyzing except with variable binding."""
    # except ValueError as e:
    # Should include variable name

def test_analyze_nested_try_except():
    """Test analyzing nested exception handlers."""
    # try within try
    # Should track both levels

def test_analyze_try_except_else():
    """Test analyzing else clause of try."""
    # try: ... except: ... else:
    # Should detect uncovered else

def test_analyze_try_except_finally():
    """Test analyzing finally clause."""
    # try: ... except: ... finally:
    # Should detect uncovered finally
```

#### 5. Loop Analysis
**Lines**: 359-373

```python
def test_analyze_while_loop_condition():
    """Test analyzing while loop condition."""
    # while condition:
    # Should capture condition text

def test_analyze_for_loop_with_enumerate():
    """Test analyzing for loop with enumerate."""
    # for i, item in enumerate(items):
    # Should handle unpacking

def test_analyze_nested_loops():
    """Test analyzing nested loops."""
    # for in for
    # Should track both loops

def test_analyze_loop_else_clause():
    """Test analyzing else clause of loop."""
    # for: ... else:
    # Should detect uncovered else

def test_analyze_break_continue():
    """Test analyzing break/continue statements."""
    # Uncovered break or continue
    # Should detect as control flow
```

#### 6. GapSuggestionGenerator Templates
**Lines**: 426-625

```python
def test_template_with_mock_requirements():
    """Test template includes mock hints."""
    # Code uses requests.get()
    # Template should suggest mocking

def test_template_with_async_decorator():
    """Test async template has @pytest.mark.asyncio."""
    # Async function
    # Template should include decorator

def test_template_with_fixture_usage():
    """Test template suggests appropriate fixtures."""
    # Code uses files
    # Template should mention tmp_path

def test_template_with_parametrize():
    """Test template for multiple test cases."""
    # Multiple branches to test
    # Could suggest @pytest.mark.parametrize

def test_template_imports_in_function():
    """Test template doesn't duplicate imports."""
    # Multiple suggestions needing pytest.raises
    # Should not import pytest multiple times per test
```

#### 7. Test Name Generation
**Lines**: 563-584

```python
def test_generate_name_max_length():
    """Test test name doesn't exceed reasonable length."""
    # Very long class/function names
    # Should abbreviate or cap length

def test_generate_name_special_characters():
    """Test test name handles special chars."""
    # Function name with underscores, numbers
    # Should produce valid Python identifier

def test_generate_name_private_functions():
    """Test test name for private functions."""
    # _private_func or __dunder_func__
    # Should include underscores appropriately

def test_generate_name_property():
    """Test test name for property method."""
    # @property decorated method
    # Should indicate it's a property test

def test_generate_name_staticmethod():
    """Test test name for staticmethod."""
    # @staticmethod
    # Should handle appropriately
```

#### 8. Priority Determination
**Lines**: 586-595

```python
def test_priority_assigns_medium_for_regular_code():
    """Test medium priority for general code blocks."""
    # Regular function body
    # Should be medium

def test_priority_escalates_for_security_keywords():
    """Test critical priority for security-related code."""
    # Code with "password", "token", "auth"
    # Should escalate priority

def test_priority_for_configuration_code():
    """Test appropriate priority for config."""
    # Config loading code
    # Should be appropriate priority
```

#### 9. Hint Generation
**Lines**: 689-719

```python
def test_hints_for_datetime():
    """Test hints suggest freezegun for datetime."""
    # Code uses datetime.now()
    # Should suggest freezegun or mock

def test_hints_for_random():
    """Test hints suggest seeding random."""
    # Code uses random.randint()
    # Should suggest seeding

def test_hints_for_subprocess():
    """Test hints suggest mocking subprocess."""
    # Code uses subprocess.run()
    # Should suggest mocking

def test_hints_for_database():
    """Test hints suggest mocking database."""
    # Code uses "session" or "cursor"
    # Should suggest mocking DB

def test_hints_for_network():
    """Test hints suggest mocking network."""
    # Code uses socket, urllib
    # Should suggest mocking

def test_hints_combined():
    """Test multiple hints for complex code."""
    # Code uses async + files + HTTP
    # Should suggest all relevant hints
```

#### 10. find_coverage_gaps Edge Cases
**Lines**: 726-799

```python
def test_find_gaps_with_symlinks():
    """Test finding gaps when source uses symlinks."""
    # Coverage paths through symlinks
    # Should resolve to real files

def test_find_gaps_with_relative_coverage_paths():
    """Test handling relative paths in coverage."""
    # Coverage uses ./src/module.py
    # Should resolve correctly

def test_find_gaps_with_absolute_coverage_paths():
    """Test handling absolute paths in coverage."""
    # Coverage uses /full/path/to/module.py
    # Should work without source_root

def test_find_gaps_encoding_errors():
    """Test handling files with encoding issues."""
    # Source file not UTF-8
    # Should handle or warn gracefully

def test_find_gaps_binary_files():
    """Test handling when coverage references binary."""
    # Coverage includes .so or .pyd
    # Should skip with warning

def test_find_gaps_empty_source_files():
    """Test handling empty source files."""
    # File exists but is empty
    # Should handle gracefully

def test_find_gaps_large_source_files():
    """Test performance with large files."""
    # 10,000+ line source file
    # Should complete reasonably fast
```

---

## Module: `mcp_code_covered/tool.py` (346 lines)

### Currently Tested
- ❌ Very minimal testing (test_mcp_tool.py likely basic)

### Missing Tests (Priority: CRITICAL - MCP interface)

#### 1. MCP Request Handling
**Lines**: 28-70 (`handle` function)

```python
def test_handle_with_inline_json():
    """Test handle with coverage data as inline JSON."""
    # Request with coverage as dict
    # Should parse and analyze

def test_handle_with_artifact_id():
    """Test handle with artifact reference."""
    # Request with artifact_id
    # Should call artifact_resolver

def test_handle_with_file_path():
    """Test handle with file path locator."""
    # Request with path as locator
    # Should read file from disk

def test_handle_missing_coverage_key():
    """Test error when coverage key missing."""
    # Request without "coverage"
    # Should return error response

def test_handle_invalid_json():
    """Test error when coverage JSON is invalid."""
    # Malformed JSON in coverage
    # Should return error response

def test_handle_file_not_found():
    """Test error when coverage file doesn't exist."""
    # Path to non-existent file
    # Should return error response
```

#### 2. Coverage Loading
**Lines**: Likely 72-100 (`_load_coverage`)

```python
def test_load_coverage_from_dict():
    """Test loading coverage from inline dict."""
    # Coverage already parsed
    # Should use directly

def test_load_coverage_from_json_string():
    """Test loading coverage from JSON string."""
    # Coverage as JSON string
    # Should parse

def test_load_coverage_artifact_resolver():
    """Test using artifact_resolver callback."""
    # Mock artifact_resolver
    # Should call with artifact_id

def test_load_coverage_fallback_to_path():
    """Test fallback when no resolver provided."""
    # No artifact_resolver
    # Should treat as file path

def test_load_coverage_artifact_not_found():
    """Test error when artifact resolver returns None."""
    # Resolver can't find artifact
    # Should error clearly
```

#### 3. Analysis Orchestration
**Lines**: Likely 102-130 (`_analyze_coverage_data`)

```python
def test_analyze_with_repo_root():
    """Test analysis with repo_root parameter."""
    # repo_root helps locate files
    # Should pass to analyzer

def test_analyze_without_repo_root():
    """Test analysis without repo_root."""
    # Should work with absolute paths

def test_analyze_returns_suggestions_and_warnings():
    """Test analysis returns both outputs."""
    # Should return tuple (suggestions, warnings)

def test_analyze_handles_syntax_errors():
    """Test analysis continues on parse errors."""
    # Source file has syntax error
    # Should return warning, not crash
```

#### 4. Priority Filtering
**Lines**: Likely 132-145

```python
def test_priority_filter_none():
    """Test no filtering when priority_filter not set."""
    # No filter
    # All suggestions returned

def test_priority_filter_critical():
    """Test filtering to critical only."""
    # priority_filter="critical"
    # Only critical returned

def test_priority_filter_high():
    """Test filtering to high and above."""
    # priority_filter="high"
    # Critical and high returned

def test_priority_filter_invalid():
    """Test handling invalid priority value."""
    # priority_filter="invalid"
    # Should handle gracefully
```

#### 5. Exit Code Computation
**Lines**: Likely 147-165 (`_compute_exit_code`)

```python
def test_exit_code_none():
    """Test exit code 0 with fail_on=none."""
    # Gaps exist but fail_on="none"
    # exit_code=0

def test_exit_code_any():
    """Test exit code 1 with fail_on=any."""
    # Any gaps exist
    # exit_code=1

def test_exit_code_critical():
    """Test exit code for fail_on=critical."""
    # Only non-critical gaps
    # exit_code=0
    # Critical gaps exist
    # exit_code=1

def test_exit_code_high():
    """Test exit code for fail_on=high."""
    # Medium/low gaps
    # exit_code=0
    # High or critical gaps
    # exit_code=1

def test_exit_code_computed_before_limit():
    """Test exit code sees all gaps not just limited."""
    # 100 critical gaps, limit=10
    # exit_code should still be 1
```

#### 6. Limit Application
**Lines**: Likely 167-172

```python
def test_limit_applies_after_filter():
    """Test limit applied to filtered results."""
    # Filter to critical, then limit
    # Should see top N critical

def test_limit_does_not_affect_counts():
    """Test total_suggestions shows full count."""
    # 100 suggestions, limit=10
    # total_suggestions=100, returned=10

def test_limit_zero():
    """Test limit=0 behavior."""
    # Should show all or none? Document

def test_limit_negative():
    """Test negative limit."""
    # Should ignore or error? Document
```

#### 7. Response Building
**Lines**: Likely 174-200 (`_build_result`)

```python
def test_result_includes_all_fields():
    """Test response has all required fields."""
    # Check schema compliance

def test_result_coverage_stats():
    """Test coverage statistics in response."""
    # Should include coverage_percent, files analyzed

def test_result_priority_counts():
    """Test by_priority counts in response."""
    # Should show count per priority level

def test_result_warnings_list():
    """Test warnings included in response."""
    # Warnings should be in response

def test_result_suggestions_format():
    """Test suggestions follow schema."""
    # Each suggestion has required fields

def test_result_exit_code_present():
    """Test exit_code in response."""
    # For CI/CD gating
```

#### 8. Error Response
**Lines**: Likely 202-210 (`_error_response`)

```python
def test_error_response_format():
    """Test error response follows schema."""
    # Should have error field

def test_error_response_includes_message():
    """Test error includes helpful message."""
    # Message should explain what went wrong

def test_error_response_exit_code():
    """Test error response has non-zero exit code."""
    # Errors should fail CI

def test_error_response_no_suggestions():
    """Test error response has no suggestions."""
    # Should not include partial results
```

#### 9. Integration with Analyzer
**Lines**: End-to-end

```python
def test_full_mcp_workflow():
    """Test complete MCP request -> response flow."""
    # Valid request
    # Should return valid response with suggestions

def test_mcp_with_no_gaps():
    """Test MCP response when coverage is 100%."""
    # Perfect coverage
    # Should return success with 0 suggestions

def test_mcp_performance():
    """Test MCP response time is reasonable."""
    # Large codebase
    # Should complete in <5 seconds
```

---

## Integration Tests

### Missing Tests (Priority: HIGH)

```python
# test_end_to_end.py

def test_cli_to_mcp_consistency():
    """Test CLI and MCP produce same suggestions."""
    # Same coverage input
    # Both interfaces should agree on gaps

def test_golden_workflow():
    """Test realistic user workflow end-to-end."""
    # 1. Generate coverage
    # 2. Run code-covered
    # 3. Write test stubs
    # 4. Tests should be runnable

def test_incremental_coverage_improvement():
    """Test iterative coverage improvement."""
    # 1. Initial coverage 50%
    # 2. Fix suggested tests
    # 3. Re-run, coverage improves
    # 4. New suggestions appear

def test_multiple_files_workflow():
    """Test analyzing project with many files."""
    # 10+ source files
    # Should handle all efficiently

def test_with_real_pytest_output():
    """Test with actual pytest --cov output."""
    # Real coverage.json from pytest
    # Should parse and analyze correctly
```

---

## Test Coverage Summary

### Total Tests Needed: ~100 tests

**By Priority:**
- 🔴 **CRITICAL**: 20 tests (MCP interface, error handling, security)
- 🟠 **HIGH**: 40 tests (AST edge cases, complex analysis scenarios)
- 🟡 **MEDIUM**: 30 tests (CLI options, output formatting)
- 🟢 **LOW**: 10 tests (Performance, large-scale)

**By Module:**
- `cli.py`: ~25 tests (CLI options, output modes)
- `analyzer/coverage_gaps.py`: ~50 tests (largest module, complex AST logic)
- `mcp_code_covered/tool.py`: ~25 tests (MCP interface, critical for external use)
- Integration: ~10 tests (end-to-end workflows)

---

## Implementation Order Recommendation

1. **Week 1**: MCP tool.py tests (critical for external users) - 25 tests
2. **Week 2**: Analyzer AST edge cases (core logic) - 30 tests
3. **Week 3**: Analyzer hints, templates, and edge cases - 20 tests
4. **Week 4**: CLI options and output modes - 15 tests
5. **Week 5**: Integration tests and polish - 10 tests

---

## Notes for Your Coders

- All test files should use `pytest` framework
- Use `tmp_path` fixture for file operations (auto-cleanup)
- Create helper functions for common setup (e.g., `_write_coverage_json`, `_write_source_file`)
- Test both success paths AND failure paths for every function
- For AST tests, include actual Python source code snippets
- Mock external dependencies (file I/O, network) where appropriate
- Use `capsys` fixture to capture and test stdout/stderr output
- Test edge cases: empty inputs, unicode, very long strings, etc.
- Aim for descriptive test names that explain the scenario
- Include docstrings explaining what's being tested and why
- Group related tests in classes for organization
- Use `@pytest.mark.parametrize` for testing multiple similar cases
- **Golden tests**: Lock down expected output format to prevent accidental UX changes
- Remember: **test the behavior, not the implementation**

---

## Special Testing Considerations

### AST Testing Strategy
- Use actual Python source code strings (not mocked AST)
- Test Python 3.10+, 3.11, 3.12 specific syntax if supported
- Include malformed code to test fallback paths
- Test deeply nested structures (nested loops, nested ifs)

### Coverage JSON Formats
- Test with coverage.py v6.x and v7.x formats (if different)
- Test with missing optional fields
- Test with extra fields (forward compatibility)

### MCP Interface
- Follow MCP protocol schemas strictly
- Test schema validation
- Test backward compatibility if schema evolves
- Performance matters: users run this in CI/CD

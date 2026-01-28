# code-covered

[![PyPI version](https://img.shields.io/pypi/v/code-covered.svg)](https://pypi.org/project/code-covered/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Find coverage gaps and suggest what tests to write.**

Coverage tools tell you *what* lines aren't tested. `code-covered` tells you *what tests to write*.

## The Problem

```
$ pytest --cov=myapp
Name                 Stmts   Miss  Cover
----------------------------------------
myapp/validator.py      47     12    74%
```

74% coverage. 12 lines missing. But *which* 12 lines? And what tests would cover them?

## The Solution

```
$ code-covered coverage.json

============================================================
code-covered
============================================================
Coverage: 74.5% (35/47 lines)
Files analyzed: 1 (1 with gaps)

Missing tests: 4
  [!!] CRITICAL: 2
  [!]  HIGH: 2

Top suggestions:
  1. [!!] test_validator_validate_input_handles_exception
       In validate_input() lines 23-27 - when ValueError is raised

  2. [!!] test_validator_parse_data_raises_error
       In parse_data() lines 45-45 - raise ParseError

  3. [! ] test_validator_validate_input_when_condition_false
       In validate_input() lines 31-33 - when len(data) == 0 is False

  4. [! ] test_validator_process_when_condition_true
       In process() lines 52-55 - when config.strict is True
```

## Installation

```bash
pip install code-covered
```

## Quick Start

```bash
# 1. Run your tests with coverage JSON output
pytest --cov=myapp --cov-report=json

# 2. Find what tests you're missing
code-covered coverage.json

# 3. Generate test stubs
code-covered coverage.json -o tests/test_gaps.py
```

## Features

### Priority Levels

| Priority | What it means | Example |
|----------|---------------|---------|
| **Critical** | Exception handlers, raise statements | `except ValueError:` never triggered |
| **High** | Conditional branches | `if x > 0:` branch never taken |
| **Medium** | Function bodies, loops | Loop body never entered |
| **Low** | Other uncovered code | Module-level statements |

### Test Templates

Each suggestion includes a ready-to-use test template:

```python
def test_validate_input_handles_exception():
    """Test that validate_input handles ValueError."""
    # Arrange: Set up conditions to trigger ValueError
    # TODO: Mock dependencies to raise ValueError

    # Act
    result = validate_input()  # TODO: Add args

    # Assert: Verify exception was handled correctly
    # TODO: Add assertions
```

### Setup Hints

Detects common patterns and suggests what to mock:

```
Hints: Mock HTTP requests with responses or httpx, Use @pytest.mark.asyncio decorator
```

## CLI Reference

```bash
# Basic usage
code-covered coverage.json

# Show full templates
code-covered coverage.json -v

# Filter by priority
code-covered coverage.json --priority critical

# Limit results
code-covered coverage.json --limit 5

# Write test stubs to file
code-covered coverage.json -o tests/test_missing.py

# Specify source root (if coverage paths are relative)
code-covered coverage.json --source-root ./src

# JSON output for CI pipelines
code-covered coverage.json --format json
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (gaps found or no gaps) |
| 1 | Error (file not found, parse error) |

### JSON Output

Use `--format json` for CI integration:

```json
{
  "coverage_percent": 74.5,
  "files_analyzed": 3,
  "files_with_gaps": 1,
  "suggestions": [
    {
      "test_name": "test_validator_validate_input_handles_exception",
      "test_file": "tests/test_validator.py",
      "description": "In validate_input() lines 23-27 - when ValueError is raised",
      "covers_lines": [23, 24, 25, 26, 27],
      "priority": "critical",
      "code_template": "def test_...",
      "setup_hints": ["Mock HTTP requests"],
      "block_type": "exception_handler"
    }
  ],
  "warnings": []
}
```

## Python API

```python
from analyzer import find_coverage_gaps, print_coverage_gaps

# Find gaps
suggestions, warnings = find_coverage_gaps("coverage.json")

# Print formatted output
print_coverage_gaps(suggestions)

# Or process programmatically
for s in suggestions:
    print(f"{s.priority}: {s.test_name}")
    print(f"  Covers lines {s.covers_lines}")
    print(f"  Template:\n{s.code_template}")
```

## How It Works

1. **Parse coverage.json** - Reads the JSON report from `pytest-cov`
2. **AST Analysis** - Parses source files to understand code structure
3. **Context Detection** - Identifies what each uncovered block does:
   - Is it an exception handler?
   - Is it a conditional branch?
   - What function/class is it in?
4. **Template Generation** - Creates specific test templates based on context
5. **Prioritization** - Ranks by importance (error paths > branches > other)

## License

MIT

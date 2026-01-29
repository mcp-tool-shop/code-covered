# Contributing to code-covered

Thank you for considering contributing to code-covered! We welcome contributions from the community.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/mcp-tool-shop/code-covered.git
   cd code-covered
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install in development mode**
   ```bash
   pip install -e ".[dev]"
   ```

## Running Tests

```bash
# Run all tests
pytest -v

# Run with coverage
pytest --cov=analyzer --cov=mcp_code_covered --cov=cli --cov-report=term-missing

# Run a specific test file
pytest tests/test_analyzer.py -v
```

## Code Quality

Before submitting a PR, ensure your code passes all checks:

```bash
# Run linting
ruff check analyzer mcp_code_covered cli.py tests

# Run type checking
pyright analyzer mcp_code_covered cli.py tests

# Run security audit
pip-audit
```

## Code Style

- **Line length**: Maximum 100 characters
- **Python version**: Code must support Python 3.10+
- **Type hints**: Use type hints where appropriate
- **Formatting**: Follow PEP 8 guidelines (enforced by ruff)
- **Imports**: Use absolute imports, sorted by ruff/isort

## Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clear, descriptive commit messages
   - Add tests for new functionality
   - Update documentation as needed

3. **Ensure all checks pass**
   - All tests must pass
   - Code coverage should not decrease
   - Linting and type checking must pass
   - No security vulnerabilities

4. **Submit your PR**
   - Provide a clear description of the changes
   - Reference any related issues
   - Ensure CI passes

## PR Checklist

- [ ] Tests added/updated and passing
- [ ] Documentation updated (if applicable)
- [ ] Code linted with ruff
- [ ] Type checking passes with pyright
- [ ] No security vulnerabilities found
- [ ] Commit messages are clear and descriptive

## Reporting Bugs

- Use the GitHub issue tracker
- Include Python version and OS
- Provide a minimal reproducible example
- Include relevant error messages and stack traces

## Feature Requests

We welcome feature requests! Please:
- Search existing issues first
- Clearly describe the use case
- Explain how it aligns with the project goals

## Questions?

Feel free to open an issue for questions or discussion.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

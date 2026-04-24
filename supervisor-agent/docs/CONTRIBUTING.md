# Contributing to Supervisor Agent

## Code Style

This project follows the guidelines in [`.github/instructions/CLAUDE.instructions.md`](../.github/instructions/CLAUDE.instructions.md).

Key principles:
1. **Think Before Coding** - State assumptions, surface tradeoffs
2. **Simplicity First** - Minimum code, nothing speculative
3. **Surgical Changes** - Touch only what you must
4. **Goal-Driven Execution** - Define success criteria

## Development Setup

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate it: `source venv/bin/activate`
4. Install dev dependencies: `pip install -e ".[dev]"`

## Running Tests

```bash
pytest
pytest --cov  # With coverage
```

## Code Quality

```bash
# Format code
black src tests
isort src tests

# Lint
ruff check src tests

# Type check
mypy src

# Run all checks
black src tests && isort src tests && ruff check src tests && mypy src && pytest
```

## Submitting Changes

1. Create a feature branch
2. Make focused, surgical changes
3. Ensure tests pass
4. Submit a pull request

## Questions?

Refer to the coding instructions in `.github/instructions/CLAUDE.instructions.md`

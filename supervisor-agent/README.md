# Supervisor Agent

An async supervisor agent framework using FastAPI and LangChain.

## Features

- **FastAPI**: Modern async web framework
- **LangChain**: Agent framework for building LLM-powered applications
- **Pydantic**: Data validation using Python type annotations
- **Async/await**: Full async support throughout
- **Testing**: Comprehensive test suite with pytest

## Quick Start

### Prerequisites

- Python 3.11+
- pip or uv package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/supervisor-agent.git
cd supervisor-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
```

### Running the Agent

```bash
uvicorn supervisor_agent.main:app --reload
```

The API will be available at `http://localhost:8000`

### Running Tests

```bash
pytest
pytest --cov  # With coverage report
```

## Project Structure

```
supervisor-agent/
├── src/
│   └── supervisor_agent/
│       ├── __init__.py
│       ├── main.py           # FastAPI app entry point
│       ├── agent.py          # Core agent logic
│       ├── config.py         # Configuration management
│       └── models.py         # Pydantic models
├── tests/
│   ├── __init__.py
│   └── test_agent.py         # Agent tests
├── docs/
├── pyproject.toml            # Project configuration
├── README.md
└── .gitignore
```

## Configuration

Configure the agent using environment variables or a `.env` file:

```env
OPENAI_API_KEY=your_key_here
LOG_LEVEL=INFO
```

## Development

Code style is enforced using:
- `black` for formatting
- `ruff` for linting
- `mypy` for type checking

Run formatters:

```bash
black src tests
isort src tests
ruff check --fix src tests
```

## License

MIT

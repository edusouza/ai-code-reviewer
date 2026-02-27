# AI Code Reviewer Test Suite

Comprehensive test suite for the AI Code Reviewer application.

## Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── pytest.ini              # pytest configuration
├── unit/                   # Unit tests
│   ├── providers/          # Provider adapter tests
│   │   ├── test_github.py
│   │   ├── test_gitlab.py
│   │   └── test_bitbucket.py
│   ├── agents/             # Agent tests
│   │   ├── test_security.py
│   │   ├── test_style.py
│   │   └── test_logic.py
│   ├── test_agents_parser.py
│   └── test_suggestions.py
├── integration/            # Integration tests
│   ├── test_workflow.py
│   └── test_providers.py
└── fixtures/               # Test fixtures
    ├── sample_pr.json
    ├── sample_agents.md
    └── sample_diff.txt
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run only unit tests
```bash
pytest -m unit
```

### Run only integration tests
```bash
pytest -m integration
```

### Run tests with coverage
```bash
pytest --cov=src --cov-report=html
```

### Run tests for specific provider
```bash
pytest -m provider
```

### Run tests for specific agent
```bash
pytest -m agent
```

### Run slow tests separately
```bash
pytest -m slow
```

## Test Coverage

The test suite aims for 80%+ code coverage across:

- **Provider Adapters**: Signature verification, event parsing, API interactions
- **Review Agents**: Pattern matching, suggestion generation, LLM integration
- **Suggestion Processing**: Deduplication, filtering, ranking
- **Configuration Parsing**: AGENTS.md parsing, rule extraction
- **Workflow**: State management, node transitions, error handling

## Key Features

### Provider Tests
- Signature verification (HMAC, tokens)
- Webhook payload parsing
- Event normalization across providers
- API mocking for external calls
- Error handling scenarios

### Agent Tests
- Security vulnerability detection
- Style and formatting checks
- Logic error identification
- Pattern-based analysis
- LLM fallback handling

### Integration Tests
- End-to-end workflow validation
- Provider API integration
- State machine transitions
- Error recovery paths

### Fixtures
- Sample webhook payloads for all providers
- Sample code diffs with various issues
- Sample AGENTS.md configurations
- Mock LLM responses

## Writing Tests

### Adding Unit Tests

```python
import pytest
from unittest.mock import Mock, patch

@pytest.mark.unit
class TestMyFeature:
    def test_feature_works(self):
        # Test implementation
        pass
    
    @pytest.mark.asyncio
    async def test_async_feature(self):
        # Async test
        pass
```

### Using Fixtures

```python
def test_with_fixtures(sample_pr_event, sample_chunk):
    # Use fixtures from conftest.py
    assert sample_pr_event.provider == "github"
```

### Mocking External Calls

```python
from unittest.mock import Mock, AsyncMock, patch

@pytest.mark.asyncio
async def test_api_call():
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.get = AsyncMock(return_value=mock_response)
        
        # Test code that makes API call
```

## Continuous Integration

Tests are designed to run in CI/CD pipelines:

1. **Fast Feedback**: Unit tests run first (~30 seconds)
2. **Full Validation**: Integration tests run after (~2 minutes)
3. **Coverage Reporting**: HTML reports generated for review
4. **Quality Gates**: 80% coverage minimum enforced

## Troubleshooting

### Import Errors
Make sure `src/` is in your Python path:
```bash
export PYTHONPATH="${PYTHONPATH}:./src"
```

### Async Test Failures
Use `@pytest.mark.asyncio` decorator on async test functions.

### Coverage Issues
Run with verbose output to see missing coverage:
```bash
pytest --cov=src --cov-report=term-missing -v
```

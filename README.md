# AI Code Reviewer

[![CI](https://github.com/edusouza/ai-code-reviewer/actions/workflows/ci.yml/badge.svg)](https://github.com/edusouza/ai-code-reviewer/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/edusouza/ai-code-reviewer/branch/main/graph/badge.svg)](https://codecov.io/gh/edusouza/ai-code-reviewer)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-009688.svg)](https://fastapi.tiangolo.com/)

An intelligent, AI-powered code review system that provides automated pull request reviews using Large Language Models (LLMs). Supports GitHub, GitLab, and Bitbucket with multi-agent analysis, continuous learning, and cost optimization.

## Features

- **Multi-Provider Support**: Works with GitHub, GitLab, and Bitbucket repositories
- **Intelligent Analysis**: Multiple specialized agents (Style, Security, Logic, Patterns)
- **LLM Router**: Automatically selects the best model based on PR complexity
- **Cost Optimization**: Token-aware routing and budget controls
- **Continuous Learning**: Improves from developer feedback
- **Rich Suggestions**: Severity levels with actionability scores
- **Observability**: Built-in metrics, tracing, and analytics
- **Configurable**: Per-repository customization via `AGENTS.md`

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Git Provider  │────▶│  Webhook API    │────▶│  Review Worker  │
│ (GitHub/GitLab) │     │   (FastAPI)     │     │  (Pub/Sub)      │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                              ┌─────────────────────────┼─────────────────────────┐
                              ▼                         ▼                         ▼
                    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
                    │  Style Agent    │    │ Security Agent  │    │  Logic Agent    │
                    └─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                         │                         │
                              └─────────────────────────┼─────────────────────────┘
                                                        ▼
                                           ┌─────────────────┐
                                           │   LLM Router    │
                                           │  (Vertex AI)    │
                                           └─────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Google Cloud Platform account
- Git provider account (GitHub, GitLab, or Bitbucket)

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/ai-code-reviewer.git
   cd ai-code-reviewer
   ```

2. **Set up environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Run with Docker Compose**
   ```bash
   docker-compose up
   ```

4. **Or run locally**
   ```bash
   pip install -r requirements.txt
   cd src && python main.py
   ```

5. **Test the health endpoint**
   ```bash
   curl http://localhost:8080/health
   ```

### Production Deployment

See [docs/deployment.md](docs/deployment.md) for detailed deployment instructions to Google Cloud Run.

## Configuration

Create an `AGENTS.md` file in your repository root to customize review behavior:

```markdown
## Review Preferences
- Focus areas: performance, security
- Ignore: tests/, docs/
- Max suggestions per file: 5

## Style Guide
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use f-strings for string formatting

## Security Priorities
- Check for SQL injection in database queries
- Validate all user inputs
- No hardcoded secrets or credentials
```

See [docs/agents.md](docs/agents.md) for complete configuration reference.

## Directory Structure

```
ai-code-reviewer/
├── src/                      # Source code
│   ├── agents/              # Review agents (Style, Security, Logic, Patterns)
│   ├── api/                 # FastAPI endpoints (webhooks, health)
│   ├── config/              # Configuration and settings
│   ├── cost/                # Cost optimization and tracking
│   ├── feedback/            # Feedback processing and learning
│   ├── llm/                 # LLM client and router
│   ├── models/              # Data models and events
│   ├── observability/       # Metrics, tracing, logging
│   ├── providers/           # Git provider integrations
│   ├── suggestions/         # Suggestion processing
│   ├── workers/             # Background workers
│   └── main.py             # Application entry point
├── infrastructure/          # Terraform configurations
│   └── terraform/          # GCP infrastructure
├── docs/                   # Documentation
├── scripts/                # Deployment scripts
├── tests/                  # Test suite
├── Dockerfile             # Container image
├── docker-compose.yml     # Local development
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## How It Works

1. **Webhook Reception**: Receives PR events from git providers via webhooks
2. **Event Processing**: Publishes events to Cloud Pub/Sub for async processing
3. **Change Extraction**: Fetches PR diff and changed files from provider
4. **Multi-Agent Analysis**: Specialized agents analyze different aspects:
   - **Style Agent**: Code style, formatting, conventions
   - **Security Agent**: Security vulnerabilities and best practices
   - **Logic Agent**: Logic errors, edge cases, algorithmic issues
   - **Pattern Agent**: Design patterns, code smells, best practices
5. **LLM Routing**: Intelligent model selection based on complexity and cost
6. **Suggestion Deduplication**: Removes duplicate or overlapping suggestions
7. **PR Comments**: Posts suggestions as PR comments with severity badges
8. **Feedback Loop**: Learns from developer interactions to improve

## Cost Management

Built-in cost optimization features:
- **Token-aware routing**: Routes simple PRs to cheaper models
- **Budget controls**: Daily/weekly spending limits with alerts
- **Cost tracking**: Per-PR and aggregate cost monitoring
- **Optimization recommendations**: Suggests cost-saving improvements

## Observability

- **Metrics**: Prometheus-compatible metrics for monitoring
- **Tracing**: OpenTelemetry integration for request tracing
- **Logging**: Structured JSON logging
- **Analytics**: BigQuery integration for long-term analysis
- **Langfuse**: Optional LLM observability and prompt management

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 📖 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/edusouza/ai-code-reviewer/issues)
- 💬 [Discussions](https://github.com/edusouza/ai-code-reviewer/discussions)

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Powered by [Google Vertex AI](https://cloud.google.com/vertex-ai)
- Architecture inspired by modern LLM application patterns

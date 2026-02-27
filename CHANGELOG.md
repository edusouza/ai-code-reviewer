# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial support for GitHub, GitLab, and Bitbucket webhooks
- Multi-agent AI review system with 4 specialized agents:
  - Security agent for vulnerability detection
  - Style agent for code formatting and conventions
  - Logic agent for bug detection and edge cases
  - Pattern agent for repository-specific patterns
- LangGraph workflow orchestration with checkpoint persistence
- AGENTS.md configuration support for repository-specific rules
- Self-hosted LangFuse observability with tracing and metrics
- Blue-green deployment strategy with canary testing
- Cost optimization with budget management and large PR handling
- Learning system with developer feedback and pattern extraction
- Comprehensive test suite with 200+ tests
- Terraform infrastructure as code for GCP deployment
- Full documentation including deployment guide and troubleshooting

### Security
- HMAC signature verification for all webhook providers
- Secret Manager integration for secure credential storage
- Service account isolation with minimal permissions

## [0.1.0] - 2025-02-27

### Added
- Initial release of AI Code Reviewer
- Complete implementation of core functionality
- Full test coverage and documentation
- Production-ready infrastructure templates

[Unreleased]: https://github.com/edusouza/ai-code-reviewer/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/edusouza/ai-code-reviewer/releases/tag/v0.1.0

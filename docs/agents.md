# AGENTS.md Reference

The `AGENTS.md` file allows you to customize AI Code Reviewer behavior for each repository. Place this file in your repository root.

## Overview

`AGENTS.md` uses a simple Markdown format with specific sections. The AI Code Reviewer parses this file to understand your team's preferences and coding standards.

## Available Sections

### 1. Review Preferences

Configure general review behavior.

```markdown
## Review Preferences

- Focus areas: performance, security, maintainability
- Ignore patterns: tests/, docs/, *.min.js
- Max suggestions per file: 10
- Max suggestions total: 50
- Severity threshold: suggestion
- Enable all agents: true
- Require tests for new features: true
- Check documentation for public APIs: true
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `Focus areas` | Priority areas for review | `all` |
| `Ignore patterns` | Files/patterns to skip | See defaults |
| `Max suggestions per file` | Limit per file | 10 |
| `Max suggestions total` | Overall limit | 50 |
| `Severity threshold` | Minimum severity to report | `suggestion` |
| `Enable all agents` | Run all agents | true |
| `Require tests` | Flag PRs without tests | true |
| `Check documentation` | Verify API docs | true |

### 2. Style Guide

Define coding standards for different languages.

```markdown
## Style Guide

### Python
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use f-strings for string formatting
- Naming conventions:
  - Functions: snake_case
  - Classes: PascalCase
  - Constants: UPPER_SNAKE_CASE
- Use docstrings in Google style

### JavaScript/TypeScript
- Maximum line length: 100 characters
- Use semicolons: true
- Prefer const over let/var
- Prefer arrow functions
- Naming conventions:
  - Functions: camelCase
  - Classes: PascalCase
  - Constants: UPPER_SNAKE_CASE
```

**Supported Languages:**
- Python
- JavaScript
- TypeScript
- Java
- Go
- Ruby
- Rust

### 3. Security Priorities

Define security concerns by priority level.

```markdown
## Security Priorities

### High
- SQL injection vulnerabilities
- Command injection vulnerabilities
- Path traversal vulnerabilities
- Hardcoded secrets or credentials
- Insecure deserialization

### Medium
- Cross-site scripting (XSS) vulnerabilities
- CSRF vulnerabilities
- Insecure file uploads
- Weak cryptographic implementations

### Low
- Information disclosure in comments
- Verbose error messages
- Missing security headers
```

### 4. Code Patterns

Document good and anti-patterns for your codebase.

```markdown
## Code Patterns

### Python Good Patterns
- Use context managers (with statements)
- Prefer composition over inheritance
- Use dataclasses for simple data structures
- Use enum for fixed sets of values

### Python Anti-Patterns
- Using mutable default arguments
- Catching bare 'except:' clauses
- Using 'is' for string/number comparison
- Reassigning built-in names

### JavaScript Good Patterns
- Use async/await instead of callbacks
- Use destructuring for cleaner code
- Use optional chaining (?.) and nullish coalescing (??)

### JavaScript Anti-Patterns
- Using var instead of let/const
- Implicit type coercion (== instead of ===)
- Modifying built-in prototypes
```

### 5. Ignore Patterns

Specify files and patterns to exclude from review.

```markdown
## Ignore Patterns

# Generated files
*.min.js
*.min.css
*.map
bundle.js
vendor/**

# Dependencies
node_modules/**
.venv/**
venv/**
__pycache__/**

# Lock files
package-lock.json
yarn.lock
poetry.lock

# Test data
**/fixtures/**
**/testdata/**
**/mocks/**

# Documentation
*.md
docs/**

# Binary files
*.png
*.jpg
*.pdf
```

### 6. Agent Configuration

Fine-tune individual agent behavior.

```markdown
## Agent Configuration

### Style Agent
- Enabled: true
- Strict mode: false
- Check imports: true
- Check formatting: true

### Security Agent
- Enabled: true
- Sensitivity: high
- Check dependencies: true
- Check secrets: true

### Logic Agent
- Enabled: true
- Check edge cases: true
- Check error handling: true
- Check null safety: true

### Pattern Agent
- Enabled: true
- Check design patterns: true
- Check code smells: true
- Check performance: true
```

### 7. LLM Preferences

Control LLM behavior and model selection.

```markdown
## LLM Preferences

- Preferred model: gemini-pro
- Fallback model: gemini-pro-vision
- Temperature: 0.3
- Max tokens: 2000
- Response format: structured
```

### 8. Custom Rules

Add repository-specific rules.

```markdown
## Custom Rules

### Database
- Always use parameterized queries
- Use connection pooling
- Close connections in finally blocks

### API Design
- REST endpoints should use proper HTTP methods
- Include pagination for list endpoints
- Return consistent error formats

### Testing
- All new features must have unit tests
- Integration tests for external dependencies
- Mock external services in unit tests
```

## Complete Example

```markdown
# AI Code Reviewer Configuration

## Review Preferences
- Focus areas: performance, security, maintainability
- Ignore patterns: tests/fixtures/, *.generated.ts
- Max suggestions per file: 8
- Max suggestions total: 40
- Severity threshold: warning
- Require tests for new features: true
- Check documentation for public APIs: true

## Style Guide

### Python
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use f-strings for string formatting
- Use docstrings in Google style
- Naming conventions:
  - Functions: snake_case
  - Classes: PascalCase
  - Constants: UPPER_SNAKE_CASE

### TypeScript
- Maximum line length: 100 characters
- Use semicolons: true
- Prefer const over let
- Prefer interfaces over types
- Naming conventions:
  - Functions: camelCase
  - Classes: PascalCase
  - Interfaces: PascalCase
  - Types: PascalCase

## Security Priorities

### High
- SQL injection vulnerabilities
- Hardcoded secrets or credentials
- Authentication bypass vulnerabilities

### Medium
- Cross-site scripting (XSS)
- CSRF vulnerabilities
- Missing input validation

## Code Patterns

### Python Good Patterns
- Use context managers for resources
- Prefer composition over inheritance
- Use dataclasses for data structures

### Python Anti-Patterns
- Mutable default arguments
- Bare except clauses
- Global variables

## Ignore Patterns

# Dependencies
node_modules/**
.venv/**
__pycache__/**

# Generated files
*.min.js
*.generated.ts

# Test fixtures
**/fixtures/**
**/testdata/**

## Custom Rules

### Performance
- Use database indexes for frequently queried columns
- Cache expensive computations
- Use bulk operations for batch processing

### Security
- All user input must be validated
- Use prepared statements for SQL
- Sanitize output to prevent XSS
```

## Best Practices

1. **Keep it Concise**: Focus on what makes your codebase unique
2. **Be Specific**: Use concrete examples when possible
3. **Update Regularly**: Review and update as your standards evolve
4. **Team Consensus**: Ensure rules reflect team agreements
5. **Start Simple**: Begin with basics and add complexity over time

## Validation

The AI Code Reviewer validates your `AGENTS.md` on startup. Invalid configurations will:
- Log a warning with details
- Fall back to default configuration
- Continue operating with defaults

Check logs for validation messages when first deploying.

## Migration from Other Tools

If migrating from other code review tools:

1. **ESLint/Prettier**: Copy rules to Style Guide section
2. **Bandit**: Map security rules to Security Priorities
3. **Custom Scripts**: Convert to Custom Rules section
4. **Code Owners**: Use ignore patterns for special files

## Tips

- Use comments (`#`) for notes and explanations
- Organize by priority (most important first)
- Link to external documentation when helpful
- Version your AGENTS.md with your codebase
- Test changes with a few PRs before rolling out

## Support

For questions about configuration:
- Check the [examples directory](../examples/)
- Review [troubleshooting guide](troubleshooting.md)
- Join [GitHub Discussions](https://github.com/yourusername/ai-code-reviewer/discussions)

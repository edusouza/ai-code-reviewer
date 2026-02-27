# AI Code Review Configuration

## Style Rules

### Python
- Max line length: 120
- Use type hints: yes
- Naming conventions:
  - functions: snake_case
  - classes: PascalCase
  - constants: UPPER_CASE

### JavaScript/TypeScript
- Max line length: 100
- Use semicolons: yes
- Prefer const over let/var

## Security Priorities

### High
- SQL injection vulnerabilities
- Hardcoded credentials
- XSS vulnerabilities

### Medium
- Insecure hash algorithms
- Disabled SSL verification

### Low
- Information disclosure in comments

## Ignore Patterns
- tests/**
- **/*.test.js
- **/node_modules/**
- **/.git/**

## Code Patterns

### Good Patterns
- Use dependency injection
- Validate all inputs
- Handle errors explicitly

### Anti-Patterns
- Magic numbers
- Deep nesting (>3 levels)
- Catch-all exceptions

## Review Settings
- Max suggestions per file: 10
- Total max suggestions: 50
- Severity threshold: suggestion
- Require tests for new features: yes
- Check documentation for public APIs: yes

## Custom Rules

### No Console in Production
Avoid console.log statements in production code.

### Prefer Async/Await
Use async/await instead of raw promises.

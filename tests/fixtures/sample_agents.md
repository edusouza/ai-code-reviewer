# AI Code Review Configuration

## Overview

This document defines the coding standards and review preferences for our project.

## Style Rules

### Python
- Max line length: 120 characters
- Use type hints: yes
- Follow PEP 8 guidelines

#### Naming Conventions
- Functions: snake_case
- Classes: PascalCase
- Constants: UPPER_CASE
- Private methods: _leading_underscore

#### Preferred Patterns
- Use dataclasses for simple data containers
- Prefer composition over inheritance
- Use context managers for resource management

### JavaScript/TypeScript
- Max line length: 100 characters
- Use semicolons: yes
- Quote style: single

#### Preferred Patterns
- Use const/let instead of var
- Prefer async/await over promises
- Use destructuring for object properties

## Security Priorities

### High (Must Fix)
- SQL injection vulnerabilities
- Hardcoded credentials/passwords
- XSS vulnerabilities
- Insecure deserialization
- Command injection

### Medium (Should Fix)
- Insecure hash algorithms (MD5, SHA1)
- Disabled SSL verification
- Weak cryptography
- Path traversal vulnerabilities

### Low (Consider Fixing)
- Information disclosure in comments
- Missing security headers
- Verbose error messages

## Ignore Patterns

The following files and directories are excluded from code review:

- tests/**
- **/*.test.js
- **/*.test.ts
- **/*.spec.py
- **/node_modules/**
- **/.git/**
- **/dist/**
- **/build/**
- **/__pycache__/**
- **/*.min.js
- **/*.min.css

## Code Patterns

### Python

#### Good Patterns
- Use list comprehensions for simple transformations
- Use generators for large datasets
- Explicit is better than implicit
- Flat is better than nested

#### Anti-Patterns
- Mutable default arguments
- Bare except clauses
- Using `is` for equality comparisons
- Deep nesting (>3 levels)

### JavaScript

#### Good Patterns
- Use strict equality (===)
- Handle promise rejections
- Use template literals for string interpolation
- Destructure function parameters

#### Anti-Patterns
- Using eval()
- Modifying prototypes
- Creating globals
- Callback hell

## Review Settings

- Max suggestions per file: 10
- Total max suggestions: 50
- Severity threshold: suggestion
- Require tests for new features: yes
- Check documentation for public APIs: yes
- Auto-approve formatting-only changes: no

## Custom Rules

### No Print Statements in Production
Avoid using print() statements in production code. Use logging instead.

Example:
```python
# Bad
print("Processing user input")

# Good
import logging
logger = logging.getLogger(__name__)
logger.info("Processing user input")
```

### API Response Validation
Always validate API responses before processing.

Example:
```python
# Bad
data = response.json()
process(data["field"])

# Good
data = response.json()
if "field" in data:
    process(data["field"])
else:
    handle_missing_field()
```

### Error Handling
Always include meaningful error messages and handle exceptions appropriately.

Example:
```python
# Bad
try:
    result = process(data)
except:
    pass

# Good
try:
    result = process(data)
except ValueError as e:
    logger.error(f"Invalid data format: {e}")
    raise CustomError(f"Failed to process data: {e}") from e
```

## Review Process

1. Automated checks run first
2. Security agent reviews for vulnerabilities
3. Style agent checks formatting and conventions
4. Logic agent checks for bugs and issues
5. LLM judge validates suggestions
6. Comments are posted to the PR

## Contact

For questions about these guidelines, contact the dev team at dev@example.com

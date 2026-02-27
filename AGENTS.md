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

### Fix Problems, Don't Mask Them
**IMPORTANT**: When fixing issues, you MUST address the root cause, not just suppress warnings or work around the symptoms:
- Do NOT use `# noqa` or similar suppressions unless absolutely necessary and justified
- Do NOT downgrade dependencies or versions to avoid compatibility issues - upgrade/fix the issue instead
- Do NOT lower test coverage thresholds to make builds pass - add proper tests
- Do NOT use `|| true` to ignore command failures
- Always prefer actual solutions over workarounds
- If a linter error occurs, fix the underlying code issue, not the linter warning
- If tests fail due to missing coverage, write tests for the uncovered code
- If dependencies are incompatible, update them properly rather than downgrading

### Pre-commit Quality Checks
**MANDATORY**: You MUST run linters BEFORE every commit. EVERY time you modify code, run these commands:
```bash
ruff check src/ tests/
mypy src/ --strict
```
- **NO EXCEPTIONS**: Even for a single line change
- Fix ALL errors before committing
- If any tool fails, fix the underlying issue - don't ignore or workaround
- Treat linter/type errors as blockers, not suggestions

**Quick Fix for Ruff Errors**: To automatically fix many common ruff issues, use:
```bash
ruff check src/ tests/ --fix
```
- Review all changes before committing
- Some issues may still require manual fixes

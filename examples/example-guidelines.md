# Example Guidelines File

> This is an example of a guidelines file you'd put in `.claude/guidelines/`
> Copy this to `.claude/guidelines/your-project-standards.md` and customize

---

## Code Standards

### Python Style
- Use snake_case for functions and variables
- Use PascalCase for class names
- Maximum line length: 120 characters
- Always use type hints for function parameters and returns
- Docstrings required for all public functions

### JavaScript/TypeScript Style
- Use camelCase for functions and variables
- Use PascalCase for classes and components
- Prefer `const` over `let`, never use `var`
- Use async/await over .then() chains
- ESLint + Prettier for formatting

### File Organization
- One class per file
- Test files next to source: `foo.py` / `foo_test.py`
- Constants in UPPER_SNAKE_CASE

---

## API Standards

### REST Conventions
- Use plural nouns: `/users`, `/orders`, not `/user`, `/order`
- Use HTTP verbs correctly: GET (read), POST (create), PUT (update), DELETE (remove)
- Return appropriate status codes:
  - 200: Success
  - 201: Created
  - 400: Bad request
  - 401: Unauthorized
  - 404: Not found
  - 500: Server error

### Response Format
All API responses should follow this structure:
```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

Or for errors:
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Email is required"
  }
}
```

### Authentication
- Use JWT tokens for API authentication
- Tokens expire after 24 hours
- Refresh tokens valid for 7 days
- Never log tokens or include in error messages

---

## Security Standards

### Secrets Management
- NO hardcoded secrets in code
- Use environment variables for all credentials
- .env files must be in .gitignore
- Use secret scanning in CI pipeline

### Input Validation
- Validate ALL user input on the server
- Sanitize HTML/Markdown input
- Use parameterized queries for SQL (no string concatenation)
- Rate limit API endpoints (100 req/min default)

### Forbidden Patterns
These should be flagged as issues:
- `eval()` or `exec()` with user input
- SQL queries built with string concatenation
- Disabled CORS for production
- `console.log()` with sensitive data

---

## Testing Standards

### Coverage Requirements
- Minimum 80% code coverage
- 100% coverage for security-critical code
- All public functions must have tests

### Test Types
1. **Unit tests**: Test individual functions
2. **Integration tests**: Test API endpoints
3. **E2E tests**: Test critical user flows

### Test Naming
```python
def test_user_creation_with_valid_email_succeeds():
    ...

def test_user_creation_with_invalid_email_fails():
    ...
```

---

## Documentation Standards

### Required Documentation
- README.md in every module
- API documentation (OpenAPI/Swagger)
- Inline comments for complex logic only
- CHANGELOG.md updated with each release

### README Structure
1. What it does (1-2 sentences)
2. How to install
3. How to use (quick example)
4. Configuration options
5. API reference (if applicable)

---

## Git Workflow

### Branch Naming
- `feature/add-user-auth`
- `bugfix/fix-login-error`
- `hotfix/security-patch`

### Commit Messages
```
type: short description

Longer explanation if needed.

Fixes #123
```

Types: feat, fix, docs, style, refactor, test, chore

### Pull Request Requirements
- Must pass all CI checks
- Requires 1 approval
- Squash merge to main

---

## How Hunters Use This File

Issue hunters will read this file and look for violations:

1. **Code not matching style rules** -> Create issue
2. **APIs not following conventions** -> Create issue
3. **Missing tests** -> Create issue
4. **Security violations** -> Create HIGH severity issue
5. **Missing documentation** -> Create issue

Example: If a hunter finds `var x = 5` in JavaScript code, that violates the "never use var" rule above, so they'd create an issue.

---

## How to Customize

1. Copy this file to `.claude/guidelines/your-standards.md`
2. Delete sections that don't apply to your project
3. Add sections specific to your tech stack
4. Update the rules to match YOUR preferences
5. Tell hunters to read this file before hunting

The more specific your guidelines, the better the hunters can find real issues.

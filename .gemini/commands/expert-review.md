Request expert review of recent changes from multiple perspectives.

## Context

Reference `.gemini/rules/` for API standards.

## Review Process

Launch these reviewers:

### 1. Code Reviewer (@code-reviewer)

- Security and JWT auth patterns
- FastAPI dependency injection
- Code quality (no print(), proper exceptions, logging)

### 2. Verify API (@verify-api)

- Run tests and confirm they pass
- Check endpoints return expected models
- Check DB connection handling

## Output Format

```markdown
## Expert Review Summary

### Critical Issues (Must Fix)

- **[Reviewer]** [file:line]: Issue -> Fix

### Important Issues (Should Fix)

- **[Reviewer]** [file:line]: Issue -> Recommendation

### Verification

| Check              | Status | Notes |
| ------------------ | ------ | ----- |
| Dependency Inj.    | PASS   |       |
| Security/Auth      | PASS   |       |
| API Responses      | PASS   |       |
| Tests pass         | PASS   |       |
```

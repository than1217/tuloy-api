Create a commit for staged/unstaged changes.

First, gather context:

```bash
echo "=== Git Status ===" && git status --short
echo "=== Current Branch ===" && git branch --show-current
echo "=== Recent Commits (for style reference) ===" && git log --oneline -5
echo "=== Changes Summary ===" && git diff --stat HEAD
```

Then:

1. Review changes and identify what was modified
2. Stage relevant files (exclude `.env`, credentials, `__pycache__`, `*.pyc`)
3. Write a conventional commit message following this format:
   - `feat(scope): description` - New feature
   - `fix(scope): description` - Bug fix
   - `chore(scope): description` - Maintenance
   - `docs(scope): description` - Documentation
   - `refactor(scope): description` - Code refactoring
   - `test(scope): description` - Tests
4. Use standard message format for the commit message
5. No AI attribution: no `Co-Authored-By` trailer, no "Generated with..." line
6. Run `git status` after commit to verify success

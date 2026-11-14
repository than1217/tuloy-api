Execute a full implementation based on the plan discussed above. Work autonomously until complete.

## Prime Directive

**COMPLETE IMPLEMENTATION ONLY** - No stubs, no placeholders, no "TODO" comments, no "implement later". Every function
must be fully working. Every test must be real. Every feature must be verified.

If you cannot complete something, STOP and explain why - do not leave partial work.

## Phase 1: Analyze & Organize

Review the plan from our conversation above. Break the work into:

1. **Parallel tasks** - Independent work that can be done simultaneously
2. **Sequential tasks** - Work that depends on previous steps
3. **Verification points** - Where to test before proceeding

```
Example structure:
├── PARALLEL: Create Pydantic schemas (app/schemas/)
├── PARALLEL: Create DB functions (app/db/)
├── SEQUENTIAL: Create route handlers (app/api/routes/)
├── SEQUENTIAL: Create pytest tests (tests/)
├── VERIFY: Run pytest
├── SEQUENTIAL: Fix any issues found
└── VERIFY: Final verification
```

## Phase 2: Implement with Subagents

For complex features, delegate to specialized subagents:

- **@fastapi-developer** - Core implementation work

Launch parallel work simultaneously when tasks are independent.

### Implementation Standards

Follow `.gemini/rules/`:

- No bare except:, no print(), proper logging
- FastAPI dependency injection for DB and Auth
- Parameterized DB queries (no SQL injection)
- Tests: Write real tests, not stubs

## Phase 3: Self-Verify

After implementation, run verification:

```bash
# Lint and test check
pytest
```

**If tests fail**: Fix the issues immediately. Do not proceed until green.

## Phase 4: Simplify

Invoke @code-simplifier to review and clean up the implementation:

- Remove unnecessary complexity
- Improve readability
- Eliminate duplication

## Phase 5: Expert Review

Run expert reviews:

1. **@code-reviewer** - Security, dependencies, FastAPI best practices
2. **@verify-api** - Final end-to-end verification

Address any Critical or Important issues found.

## Phase 6: Final Verification

```bash
# Final test run
pytest

# Verify clean status
git status
git diff --stat
```

## Completion Criteria

Before reporting done, confirm:

- [ ] All planned features implemented (no stubs)
- [ ] All tests pass
- [ ] API runs without errors
- [ ] Expert reviews addressed
- [ ] Code is clean and readable

## Progress Updates

Every 15-20 minutes of work, provide a brief status:

- What's completed
- What's in progress
- Any blockers

## If Blocked

If you encounter a blocker you cannot resolve:

1. Document what you tried
2. Explain the specific issue
3. Suggest alternatives
4. Ask for guidance

Do NOT leave work in a broken state. Either complete it or roll back.

---

**START NOW**: Review the plan above and begin Phase 1.

Verify test integrity after recent changes. Use this after subagent implementations or before committing test file
changes.

## Process

### Step 1: Identify Changed Test Files

```bash
# Find test files modified in recent commits
git diff --name-only HEAD~3 | grep -E "tests/.*\.py$" | sort -u
```

### Step 2: Compare Test Counts

For each modified test file:

```bash
# Count test methods in current version
grep -c "def test_" <file>

# Count test methods before changes
git show HEAD~1:<file> 2>/dev/null | grep -c "def test_" || echo "0 (new file)"

# Count assert statements
grep -c "self.assert\|assert " <file>
```

### Step 3: Generate Report

## Output Format

```markdown
## Test Integrity Report

### Summary

| Metric            | Before | After | Change |
| ----------------- | ------ | ----- | ------ |
| Test files        | X      | Y     | +/-    |
| Test methods      | X      | Y     | +/-    |
| Assert statements | X      | Y     | +/-    |

### Changed Files

| File            | Tests Before | Tests After | Asserts Before | Asserts After | Status     |
| --------------- | ------------ | ----------- | -------------- | ------------- | ---------- |
| path/to/test.py | 10           | 8           | 25             | 20            | ⚠️ REDUCED |

### Detailed Changes

#### ⚠️ Tests Removed

- `test_method_name` in `path/to/test.py`

#### ✅ Tests Added

- `test_new_method` in `path/to/test.py`
```

## Red Flags (MUST report and get confirmation)

- **Test file deleted** - List the file and all tests it contained
- **Test method removed** - List exact method name and file
- **Assert count decreased significantly** - More than 20% reduction
- **Test class removed** - List the class and all its methods

## Response Required

If ANY red flags are found:

1. **STOP** - Do not proceed automatically
2. **List all removals** with exact file:line references
3. **Ask explicitly**: "These tests were removed. Please confirm this is intentional before proceeding."
4. **Wait for confirmation** - Do not assume approval

## When to Use

- After `/implement` completes
- Before `/commit` when test files changed
- After any subagent (@fastapi-developer, @code-simplifier) modifies tests
- When reviewing PR changes

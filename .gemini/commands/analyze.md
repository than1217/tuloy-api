Deep analysis mode - understand before acting. Use when you need to "take a step back" and analyze without implementing.

## Rules

- **NO file edits** - Read and analyze only
- **NO implementations** - Recommendations only
- **Reference evidence** - Always cite file:line for claims

## Analysis Types

### 1. Error Analysis

When given logs or error messages:

1. Parse the error type and location
2. Trace the code path that led to the error
3. Identify root cause vs symptoms
4. List related code that might be affected

**Output format:**

```markdown
## Error Analysis

### Error Type

[ErrorClass]: [message]

### Location

`file.py:123` in `method_name()`

### Root Cause

[Explanation with code reference]

### Call Stack Analysis

1. `file1.py:10` → calls `method_a()`
2. `file2.py:25` → calls `method_b()`
3. `file3.py:123` → **ERROR HERE**

### Related Code

- `other_file.py:45` - Similar pattern, might have same issue
- `another.py:78` - Depends on this code

### Recommendations

1. [Specific fix with file:line reference]
2. [Alternative approach if applicable]
```

### 2. Code Analysis

When asked to understand existing implementation:

1. Identify the main entry points
2. Trace data flow through the code
3. Document dependencies and side effects
4. Note patterns and anti-patterns

**Output format:**

```markdown
## Code Analysis: [Feature/Module]

### Entry Points

- `file.py:method()` - Main entry for [purpose]

### Data Flow

1. Input received at `file.py:10`
2. Processed by `processor.py:25`
3. Stored via `storage.py:50`

### Dependencies

- Requires: `module_a`, `module_b`
- Used by: `module_c`

### Patterns Used

- [Pattern name]: `file.py:line`

### Concerns

- [Potential issue]: `file.py:line`
```

### 3. Gap Analysis

When comparing current vs desired state:

1. Document current behavior
2. Document desired behavior
3. Identify specific gaps
4. Estimate scope of changes

**Output format:**

```markdown
## Gap Analysis: [Feature]

### Current State

- [Behavior 1]: `file.py:line`
- [Behavior 2]: `file.py:line`

### Desired State

- [Requirement 1]
- [Requirement 2]

### Gaps

| Gap     | Current   | Desired   | Files Affected |
| ------- | --------- | --------- | -------------- |
| [Gap 1] | [Current] | [Desired] | file.py        |

### Scope Estimate

- Files to modify: X
- New files needed: Y
- Tests to update: Z
```

## When to Use

- Before implementing complex features (use Plan mode for planning, `/analyze` for deep dives)
- When debugging unclear errors
- To understand unfamiliar code before modifying
- When asked to "take a step back"

## After Analysis

Provide clear recommendations, then ask:

- "Ready to implement?" → Exit analysis, start coding
- "Need more analysis?" → Continue in analysis mode
- "Enter Plan mode?" → Switch to full planning workflow

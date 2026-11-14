Create a Pull Request for the current branch.

First, gather context:

```bash
echo "=== Current Branch ===" && git branch --show-current
echo "=== Base Branch ===" && git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main"
echo "=== Commits on This Branch ===" && git log --oneline $(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "origin/main")..HEAD 2>/dev/null || git log --oneline -10
echo "=== Remote Status ===" && git remote -v | head -1
echo "=== Push Status ===" && git status -sb | head -1
```

Then:

1. Push branch if needed: `git push -u origin $(git branch --show-current)`
2. Create PR using `gh pr create` with:

   - **Title**: Brief description (imperative mood)
   - **Body**:

     ```
     ## Summary
     - Bullet points of changes

     ## Test plan
     - [ ] How to verify the changes work
     ```

3. No AI attribution in the title or body: no "Generated with..." footer, no mention of AI assistants
4. Return the PR URL when done

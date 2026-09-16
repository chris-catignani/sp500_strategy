Read [AGENTS.md](AGENTS.md) for project conventions, architecture, and invariants before making changes.

## Delegating implementation to Antigravity (`agy`)

Subagents exist to save context, so the split is: **they generate, you verify.**

**Delegate:** implementing a task from a precise written spec; reviewing a diff against a checklist. Both work well.
**Keep:** investigation, premise-checking, and final verification of any number that ships. Subagents execute specs literally but do not question them, and they confabulate figures.

**Dispatch:**
```
agy --model gemini-3.8-flash-high --mode accept-edits --print-timeout 25m --print="..."
```
- Say **"read AGENTS.md first"** rather than restating conventions — it already is the conventions file.
- Say **"run every command in the FOREGROUND; do NOT launch background tasks, including a baseline test run."** Omit this and the agent will background the test suite, wait, and lose the turn with work uncommitted. Recover by resuming with `agy --continue` — the working tree keeps the work.
- Hand over **file paths, not pasted content** (brief in, report out, diff to review). Never paste a whole plan or prior-task history.
- Ask for a terse return: status, commit SHA, one-line test summary, concerns. **Full output goes to a file**, which you read only if there are findings.
- Model tier: cheapest when the brief contains the code to write; `-high` for judgment; step up for a whole-branch review.
- `~/.gemini/antigravity-cli/settings.json` must allow `command(python3)` and list this repo in `trustedWorkspaces`, or every tool call is auto-denied in headless mode.

**Verification rule:** anything a subagent writes into a doc, a dataset, or a PR body gets checked at source before it ships. A fabricated dollar figure once reached `DATA_PROVENANCE.md` formatted to look sourced. Grep the filing; don't trust the prose.

**Don't** re-verify code behaviour a reviewer already traced to `file:line` — that is the duplication to cut, not the number-checking.

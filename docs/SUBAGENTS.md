# Delegating implementation to subagents

How to hand implementation work to Antigravity (`agy`) subagents in this repo, and the
failure modes that cost turns. Written from running issues #36 and #48 this way.

## The split

**Subagents generate; the controller verifies.**

- **Delegate**: implementing a task from a precise written spec, and reviewing a diff
  against a checklist. Both work well.
- **Keep**: investigation, premise-checking, and final verification of any figure that
  ships. Subagents execute specs literally without questioning them, and they confabulate
  numbers — one invented a dollar total and wrote it into `DATA_PROVENANCE.md` formatted
  to look sourced.

Across #36 the subagents implemented 15 filings' worth of extraction correctly and caught
two real defects in review, but found none of the six discoveries that made the work
valuable. Those came from the controller prototyping against the data.

## Dispatch

```
agy --model gemini-3.8-flash-high --mode accept-edits --print-timeout 25m --print="..."
```

- Point at **`AGENTS.md`** rather than restating project conventions — it already is the
  conventions file, so this is free and stays current.
- Hand over **file paths, not pasted content**: brief in, report out, diff to review.
  Never paste a whole plan or prior-task history into a prompt.
- Ask for a **terse return** — status, commit SHA, one-line test summary, concerns — with
  the full report written to a file. Read the file only when there are findings.
- **Model tier**: cheapest when the brief contains the code to write; `-high` for
  judgment; step up for a whole-branch review.

## Failure modes

These are silent. Each one ends the turn with no output and no commit, and none of them
announce what went wrong.

**Quoted shell arguments are auto-denied.** `grep -n 'fiscal' f` kills the turn;
`grep -n fiscal f` is fine. This looks random until you probe for it. Tell the agent
explicitly not to quote arguments, and give it single-word grep targets. For line ranges,
tell it to use its file-read tool with offset/limit rather than `sed -n A,Bp`.

**Backgrounded commands hang the turn.** The agent will launch the test suite as a
background task, wait for it, and expire — five times across #36 and #48, including once
before making any edit. Say *"run every command in the FOREGROUND; do NOT launch
background tasks, including a baseline test run."* The work survives in the working tree:
recover with `agy --continue` telling it the suite result and asking only for the report
and commit.

**Code-writing tasks died where a research task succeeded.** Under issue #55, three
consecutive attempts at a roster-extraction task ended silently — no output, no files, no
commit — while a research brief that only fetched URLs and wrote one JSON file succeeded
under the same model, settings and permissions. The third attempt explicitly forbade
`python3 -c` and inline quoting and still died, so **the cause was not established**. The
work was brought back in-house rather than spend further turns on it.

What this is worth: quoting remains the documented prime suspect, and a brief should still
tell the agent to write a script to a file and run it as `python3 file.py` with no
arguments. But do not assume that instruction is sufficient. Budget a fixed number of
attempts for a code-writing delegation and take the work back when they are spent, rather
than diagnosing an opaque failure one turn at a time.

**Files outside the workspace may be unreadable.** Keep briefs and reports inside the repo
(`.superpowers/` is gitignored) rather than in a system scratch directory.

## Permissions

`~/.gemini/antigravity-cli/settings.json` must list this repo under `trustedWorkspaces`
and allow the commands the agent needs under `permissions.allow`. At minimum:
`command(python3)`, `command(git)`, `command(grep)`, `command(sed)`, `command(ls)`,
`command(cat)`, `command(find)`, `command(wc)`.

A missing rule produces the same silent turn-death as the failure modes above, so when a
turn dies with no output, suspect quoting first and permissions second. To find the
culprit, have the agent run candidate commands one at a time and append the result to a
log file with its *file-write* tool after each — a denial kills the turn, so the log's
last line names the command before the one that failed.

Headless mode cannot prompt, and `--dangerously-skip-permissions` is blocked by Claude
Code's own classifier, so the allow-list is the only route.

## Verification rule

Anything a subagent writes into a doc, a dataset, or a PR body gets checked at source
before it ships. Grep the filing; do not trust the prose.

Do **not** re-verify code behaviour a reviewer already traced to `file:line` — that is the
duplication worth cutting, not the number-checking.

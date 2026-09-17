# Delegating implementation to subagents

How to hand implementation work to an Antigravity subagent in this repo. Written from
running issues #36, #48, #55 and #73 this way.

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

Delegation runs through the **Antigravity UI**, not a CLI. The controller does not launch
the agent; it hands the human a prompt to paste. Everything runs on `gemini-3.8-high`, so
there is no model tier to choose.

**Put the substance in a file, paste a pointer.** Copy/paste into the UI mangles
formatting — tables, fenced blocks and nested lists do not survive reliably. So:

1. Write the brief to `.superpowers/briefs/<issue>-<slug>.md` (gitignored, but inside the
   workspace so the agent can read it).
2. Hand over a **short, plain, single-paragraph** prompt that names the brief path and
   nothing else structural. No tables, no code fences, no markdown that has to survive
   the clipboard.
3. Let the agent read the brief from disk, where the formatting is intact.

This also keeps prompts cheap to revise: edit the file, tell the agent to re-read it.

Inside the brief:

- Point at **`AGENTS.md`** rather than restating project conventions — it already is the
  conventions file, so this is free and stays current.
- Hand over **file paths, not pasted content**: brief in, report out, diff to review.
  Never paste a whole plan or prior-task history.
- State which decisions are **already made** and must not be relitigated, and which
  questions are **out of scope** because the controller is handling them. A subagent
  handed an open question will answer it, confidently and often wrongly.
- Forbid asserting any number the agent would have to invent rather than read. Tell it to
  report blocked instead of guessing.

## Returning work

- **Code tasks**: the agent edits the working tree directly. Ask for a terse return —
  status, commit SHA, one-line test summary, concerns — and review the diff.
- **Research and review tasks**: have it **write the output to a file** in the repo
  (`.superpowers/reports/`) rather than to the chat. The findings survive the clipboard
  intact, and the human pastes back only the summary lines. Read the file when there are
  findings.

Ask for the terse return in an explicit, short list of lines. A free-form summary pasted
back loses its structure the same way the prompt does.

## Working alongside the agent

**Never stage with `git add -A` while an agent may be running.** Stage by name. Under #55
a scratch file reached `main` this way and needed a follow-up commit to remove. The agent
shares the working tree; anything it drops there is a candidate for an unwanted commit.

## Verification rule

Anything a subagent writes into a doc, a dataset, or a PR body gets checked at source
before it ships. Grep the filing; do not trust the prose.

Do **not** re-verify code behaviour a reviewer already traced to `file:line` — that is the
duplication worth cutting, not the number-checking.

## Why not the CLI

Earlier work here drove Antigravity headlessly via `agy --print`. That mode produced a
family of silent turn-deaths — quoted shell arguments auto-denied, backgrounded commands
hanging the turn, empty stdout on turns that had in fact done the work, a permissions
allow-list that could only be edited by hand because headless mode cannot prompt. Several
turns were written off as failures while still running, and their edits landed in the
working tree afterwards.

None of these occur through the UI, which can prompt and shows its own progress. They were
artifacts of headless dispatch, not of the agent. Recorded here so the CLI is not
reintroduced as an equivalent path; the detail is in this file's git history.

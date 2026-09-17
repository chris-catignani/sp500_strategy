# Delegating implementation to subagents

How to hand implementation work to an Antigravity subagent in this repo. Written from
running issues #36, #48, #55, #73 and #76 this way.

## The split

**Subagents generate; the controller verifies.**

- **Delegate**: implementing a task from a precise written spec, and reviewing a diff
  against a checklist. Both work well.
- **Keep**: investigation, premise-checking, and final verification of any figure that
  ships. Subagents execute specs literally without questioning them, and they confabulate
  numbers — one invented a dollar total and wrote it into `DATA_PROVENANCE.md` formatted
  to look sourced. They also mis-read them in ways that survive a spot-check; see the
  verification rule below, which is the part of this document most worth reading.

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

### Spot-checking does not scale, and does not catch the real failure mode

Under #76 an agent extracted dividends from 168 filings and returned a clean status line.
About **a third of the published numbers were wrong**. AT&T's FY1994 report states
`Dividends declared .33 .33 .33 .33`; the output had Q1 through Q3 right at `0.33` and Q4 at
`327.0`. Seventy-five dividend values exceeded \$5 a quarter and sixty-two high/low pairs
were inverted.

Note what that is and is not. It was **not** invention — every figure came out of the right
document, and carried the right accession. It was a real number read from the **wrong cell**,
published under a field name asserting what it was. That is worse than an obvious fabrication,
because nothing about it looks wrong: the citation checks out, and the first three values you
spot-check are correct.

So the controller's check cannot be attentional. It has to be **mechanical**:

- **Gate every extracted figure against a second figure the same document states**, and
  withhold whatever fails. For dividends that is the annual per-share total against the sum
  of four quarters; for rosters it is the filing's own stated total (`DATA_PROVENANCE.md`
  4.3.10). Then apply the rule that section already sets — *reconcile, or withhold the
  year* — rather than publishing with a caveat.
- **Add structural rejects that need no second source**: a high below its low, a close
  outside its own band, a per-share dividend worth a quarter of the share price. Each is
  impossible rather than merely unlikely, and each caught real damage here.
- **Ask for the range, not a sample.** Min, max and count per field finds this in one look.
  The 335-row output had a 32% failure rate that any bounds check would have surfaced
  immediately.

Applying the gate cut 335 published quarters to 64. **Take the smaller number.** Lower
coverage that can be trusted beats broader coverage that cannot, and the withheld rows stay
visible as withheld rather than disappearing.

### A clean summary next to bad ratios is itself a signal

That same return read `CONCERNS: none` beside a 49% refusal rate and twelve of twenty-seven
reconciliations failing. The agent was not hiding anything; it had no sense of which numbers
were surprising. So **ask for concerns explicitly** — "say what looks wrong to you, even if
you could not fix it" — and read an unqualified all-clear alongside poor ratios as a prompt
to go look yourself.

### Check what the agent's code depends on

The same task shipped a script and seven tests that read their input from a path under
`.superpowers/`, which is **gitignored**. Everything passed locally, because the controller
had the file; on a fresh clone and in CI every test in the class would have errored in
`setUpClass`. A brief lives in `.superpowers/`; anything the repo runs must not. Before
committing a subagent's work, check that nothing it added reads from an ignored path.

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

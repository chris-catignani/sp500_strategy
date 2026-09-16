Read [AGENTS.md](AGENTS.md) for project conventions, architecture, and invariants before making changes.

Before delegating implementation work to an Antigravity (`agy`) subagent, read
[docs/SUBAGENTS.md](docs/SUBAGENTS.md). It documents failure modes that end a subagent's
turn silently — with no output, no commit, and no indication of the cause — and they will
cost you turns if you meet them cold.

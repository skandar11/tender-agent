---
title: log — the chronology of this vault
type: registry
status: active
sensitivity: normal
scope: all
updated: 2026-11-09
---

# Log

Append-only. One entry per move, newest at the bottom:
`## [YYYY-MM-DD] <operation> | <title>` and 1–3 lines (the source → the pages
touched; the question → the page filed; the lint counts). Operations: ingest ·
query · lint · build · version · decision. Read the tail: `grep "^## \[" log.md | tail -5`.
History lives here and in git; pages say how it is now.

## [2026-11-15] build | the base built for Маржан by the administrator
Frame form 2026-11-10 (`bin/new`); domains tenders · firms · office; the tender layer carried from the previous agent (EASY TENDER instance of 2026-11-12); decision `~/maksi-agents/decisions/2026-11-15-full-agent-build.md`.

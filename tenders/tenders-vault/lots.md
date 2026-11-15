---
title: lots — a lot as a folder and its card
type: reference
status: active
sensitivity: private
scope: work
updated: 2026-11-15
related:
  - operations/glubokiy-analiz-lota
  - operations/zavesti-kartochku-lota
---

# lots — records

`../lots/<year>/` — per lot:

| What | Where | git |
|---|---|---|
| the lot's folder | `<platform>-<announcement>/` — `platform`: goszakup · samruk · mitwork · meks | — |
| platform files and their text | `<folder>/docs/`, `docs/_text/` | outside |
| the raw answer of the platform | `<folder>/lot.json` | outside |
| past «протоколы итогов» of the customer | `<folder>/protocols/` | outside |
| the facts on one page | `<folder>/сводка.md` | tracked |
| the customer's contracts on a similar subject | `<folder>/history.csv` | tracked |
| the agent's conclusions, verdict | `<folder>/анализ.md` | tracked |
| the card | `<platform>-<announcement>.md` beside the folder | tracked |

The folder is built by `engine/scripts/lot.py get <number | link>`; the card — by
[[operations/zavesti-kartochku-lota|завести карточку лота]]. The first lot appears with the first
live analysis.

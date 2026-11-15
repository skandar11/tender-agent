---
title: executors — the agent's hands
type: registry
status: active
sensitivity: normal
scope: all
updated: 2026-10-10
related:
  - ../meta-vault/harness
  - automations
---

# Executors — the agent's hands

There is one agent (`../CLAUDE.md` §Agent). Everything else is executors: they
do a step, they carry no judgment. An executor does not exist until it is
here. The law — `meta-vault/harness.md`.

| Executor | Kind | Where it lives | What it does | Who calls it | Status |
|---|---|---|---|---|---|
| `bin/check` | script | `bin/check` (python3, stdlib) | a run: links, names, tables, secrets in the index; read-only | [[../meta-vault/operations/check-links-and-names\|check the base]] | live |
| `bin/setup` | script | `bin/setup` (sh; macOS, Linux) | a clean machine: git, Python, the engine's `.venv`, `secrets/`, a check run | first launch · [[../meta-vault/operations/add-engine\|add an engine]] | possible |
| `bin/setup.ps1` | script | `bin/setup.ps1` (PowerShell; Windows) | the same on Windows via winget, without administrator rights; warns about long paths | first launch · [[../meta-vault/operations/add-engine\|add an engine]] | possible |

| `engine/scripts/portal.py` | script | `engine/` (python3, stdlib; no key) | new lots: госзакуп, Самрук, Mitwork (one platform) and МЭКС; her filter; `--new` | [[../tenders/tenders-vault/operations/chto-novogo\|что нового]] | live (run 2026-11-15, Скандар's machine) |
| `engine/scripts/lot.py` | script | `engine/` (python3, stdlib) | a lot as a folder: documents of four platforms, text, customer's contracts, past protocols, `сводка.md` | [[../tenders/tenders-vault/operations/glubokiy-analiz-lota\|глубокий анализ лота]] | live (run 2026-11-15) |
| `engine/scripts/ows.py` | script | `engine/` (python3, stdlib; her portal key) | portal API by key: lots, contracts, plans, participant; `check` | [[../meta-vault/operations/check-access\|проверь доступы]] · lot.py · firm.py | live (2026-11-12; API down at times) |
| `engine/scripts/firm.py` | script | `engine/` (python3, stdlib; portal key; КГД key — when issued) | a firm by BIN, «протокол итогов», a table of firms, history | [[../tenders/tenders-vault/operations/proverit-firmu\|проверить фирму]] | live (2026-11-12) |
| `engine/scripts/finstab.py` | script | `engine/` (python3, stdlib) | financial stability by the portal's form, lot limit | [[../firms/firms-vault/operations/poschitat-finustoychivost\|посчитать финустойчивость]] | live (2026-11-15 on her two firms) |
| `engine/scripts/extract_docs.py` · `engine/common.py` | script | `engine/` | text from documents; shared helpers | lot.py | live |
| Claude in Chrome | browser | the extension in her Chrome (one for all profiles — to check at the installation) | Самрук files: the UUID of each file from the page's network requests; reading a firm's cabinet on her request | lot.py (Самрук) | possible |

_(a line for each skill, script, subagent, MCP server, channel; kind:
skill · script · subagent · mcp · channel · cron; status: possible · live ·
off)_

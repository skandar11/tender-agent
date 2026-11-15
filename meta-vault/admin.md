---
title: admin — the administrator's level (Скандар, Maksi AI Solutions)
type: reference
status: active
sensitivity: private
scope: all
updated: 2026-11-15
tags: [admin, meta, maksi, updates, access]
related:
  - owner
  - structure
  - operations/accept-new-version
  - operations/check-access
  - operations/experience-up
  - operations/tidy-computer
  - ~/maksi-agents/decisions/2026-11-15-full-agent-build
---

# The administrator's level

Скандар's word 2026-11-15: «Плюс я хочу расширить мета уровень чтобы сам мог с ее компьютера
управлять все этим» · «мета для меня и может сама захочет я не против».

**Who.** Скандар — Maksi AI Solutions, the author and keeper of this agent. He opens this folder on
Маржан's computer (in person or remotely) and says it is him. From then on the agent speaks to him on
«ты», about the structure of the agent, not about her lots. Маржан may use this level too.

**What changes in this mode:** the agent may edit the engine, the operations, the doors and the rules;
it reads the journals of her work; it never reads or changes her cabinets and never touches her data
beyond what the task needs. Push to the repository — only by Скандар's word.

## Operations

| Operation | Trigger | What |
|---|---|---|
| [[operations/accept-new-version\|обнови агента]] | «обнови агента», «прими новую версию» | the new version of the frame and of the tender layer from the original (Maksi's repository) |
| [[operations/check-access\|проверь доступы]] | «проверь доступы», «всё ли работает» | the portal key from her address, the КГД key, the platforms, Python, `bin/check`, the browser |
| [[operations/how-are-things\|что у Маржан]] | «что у Маржан», «как она пользуется» | a query over `log.md`, `planning/plan.md`, the lots: what she asked, what was analysed, where the agent stumbled |
| [[operations/experience-up\|опыт наверх]] | «опыт наверх», the monthly review of agents | one page of experience for the original: what worked, what broke, what she asked for and did not get — no client data |
| [[operations/tidy-computer\|наведи порядок]] | «наведи порядок на компьютере» | her folders, downloads and desktop into the base through `inbox/`; nothing is deleted |

## Where the agent comes from

- **The frame** — `~/maksi-agents/meta/` (form 2026-11-10), built fresh by `bin/new` on 2026-11-15.
- **The tender layer** (works and services) — Maksi's own: the engine, the rules, the operations. This
  base is its original while she is the only client (rule of the catalogue: an agent made for a
  client lives at the client).
- **Delivery** — a private GitHub repository of Maksi AI Solutions; her machine pulls versions. What
  she already had on the computer and on GitHub is integrated at the installation.
- Decision on how every new agent is built — `~/maksi-agents/decisions/2026-11-15-full-agent-build.md`
  (on Скандар's machine).

## The installation checklist

1. What is there: her GitHub, the folder of the old agent (EASY TENDER), Chrome users — read only.
2. Clone, `bin\setup.ps1` or `sh bin/setup`, `bin/check`.
3. `secrets/goszakup-token` — her key; [[operations/check-access|проверь доступы]] from her address.
4. Chrome: the extension in the needed profiles; the map in [[owner]] §Browser.
5. Her old files → `inbox/` → ingest; the old agent's folder stays as it is or goes to the archive by
   her word.
6. One live run: «что нового» and «глубокий анализ лота» on her lot.
7. Commit; push — by Скандар's word.

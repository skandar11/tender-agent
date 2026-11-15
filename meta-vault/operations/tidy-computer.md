---
title: tidy the computer — наведи порядок
type: operation
trigger: phrase («наведи порядок на компьютере», «разбери загрузки»)
executor: agent
status: possible
sensitivity: private
scope: all
updated: 2026-11-15
related:
  - ingest
  - triage-inbox
  - ../owner
---

# Tidy the computer

Скандар's word 2026-11-15: «чтобы упорядочить все у нее на компе и работать».

**When:** «наведи порядок на компьютере», «разбери загрузки», «разложи рабочий стол», the installation.

**Nothing is deleted and nothing is moved without her word.** The agent proposes, she says «да».

1. **Inventory, read only.** The folders she names (by default «Загрузки», «Рабочий стол»,
   «Документы»): a table — folder · how many files · what kinds · the oldest and newest date. Do not
   open personal files; tender and work files are recognised by names and types.
2. **Proposal** — a table: group of files → where in the base (`tenders/` lot folder, `firms/docs/<firm>/`,
   `office/docs/`, `inbox/` to sort, stays where it is). Personal and unclear — stay where they are.
3. **⏸ owner:** her word on the table, in whole or by lines.
4. **Move** what she approved: into `inbox/` (then [[ingest]]) or straight into the domain's `docs/`
   when the place is clear. Platform documents of a lot — into the lot's folder `docs/`.
5. **Log** — a line in `../log.md`: what, from where, where to, how many files.

Duplicates are not deleted: the second copy goes to `archive/duplicates-<date>/` with a line in
`archive/INDEX.md`.

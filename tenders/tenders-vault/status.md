---
title: status — hot state of the tenders domain
type: status
status: active
sensitivity: normal
scope: work
updated: 2026-11-15
tags: [status, hot]
related:
  - HOME
---

# status — state as of 2026-11-15

A snapshot, not a journal. Contract — [[../../meta-vault/vault-template|vault-template]] §status.md contract.

## Blockers / not done

- **The КГД key** — not issued; without it no territoriality and taxes in a firm check. The request
  is filed by her firm on portal.kgd.gov.kz.
- **Not run on her machine** — the portal key is tied to her address; the first check is at the
  installation ([[../../meta-vault/operations/check-access|проверь доступы]]).
- **No live analysis of her own lot yet.**

## Works

- The monitor of four platforms by her filter — run 2026-11-15 on Скандар's machine: Карагандинская
  область, works and services over 20 million — 210 госзакуп, 3 Самрук, 1 Mitwork (by text).
- The lot collector `lot.py` — run 2026-11-15 on all four platforms (госзакуп 7/7 files, Mitwork 5/7,
  МЭКС 2/2, Самрук — by UUID from Chrome).
- `firm.py`, `finstab.py` — selftests pass; live runs 2026-11-12 in the previous agent.

## Structure

- **Health (from a run, dated):** see `../../meta-vault/structure.md` §Health.
- **Changes to the layout:** 2026-11-15 — the domain was born from the template (`project/` →
  `tenders/`); rules, tools and the engine carried from the previous agent of 2026-11-12.
- **Divergences from the base:**

| Base rule | How it is here | Why |
|---|---|---|
| a records folder holds files | `lots/` holds a folder per lot + a card beside it | a lot's documents are many files; the folder is what `lot.py` builds |

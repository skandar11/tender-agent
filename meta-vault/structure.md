---
title: structure — the state of the namespace build
type: status
status: active
sensitivity: normal
scope: all
updated: 2026-11-09
related:
  - vault-template
  - operations/check-links-and-names
  - operations/accept-new-version
---

# Structure — the state of the build

The state of the **layout** of the namespace, separate from the state of the
business (the business — in the domains' `status.md` and `../planning/plan.md`).
A snapshot, not a journal.

## Version

- **Template form:** 2026-11-10 (the first line of §Form journal in [[vault-template]]).
- **Built:** 2026-11-15 — by the administrator (Скандар, Maksi), step 0 from his words of 10.11 and 15.11; Маржан confirms at the installation.
- **Owner:** Маржан · **agent:** «агент» · **administrator:** Скандар ([[admin]])

## Health (from the `bin/check` run, dated)

- 2026-11-15, Скандар's machine: `bin/check` — 0 broken; selftests of `lot.py`, `firm.py`, `finstab.py` — ok; `portal.py` live; the portal API by key answered 500 that hour.

## Divergences from the template

| Template rule | How here | Why |
|---|---|---|
| step 0 — a conversation with the owner | built from Скандар's words (10.11, 15.11); her confirmation at the installation | the build was ordered by the administrator before the meeting |
| the first domain from `project/` | `tenders/`; plus `firms/` | her process is tenders; her firms are their own room |
| records in English | operations, rules and cards in Russian; doors and the method — English | she reads Russian; template rule 2026-11-09 for the method |
| `lots/` — files | a folder per lot + a card beside it | `lot.py` builds the folder; documents are many |
| one person | two: the owner and the administrator ([[admin]]) | Скандар's word 2026-11-15 |

## Asked for, not built

**Verbatim, in the owner's words**, with the date and the outcome (built / not /
decided not to build — why). The most valuable section: it shows what the base
lacked in practice.

- 2026-11-10 (through Скандар): «выявить территориальность, по месту нахождения отчетности налоговой фирмы» — **not built**: needs the КГД key.
- 2026-11-10: «Если я тебе дам содиныски солью все цифры, и ты не соберешь в устойчивость» — **half**: `finstab.py` built, the 1С export parser waits for a sample.
- 2026-11-10: «аудированная отчетность, в каком процентном соотношении» — **not built**: the depositary (dfo.kz) is checked by hand.

## Lessons for the template

What this build learned that will serve **any** next one: a rule that was
missing, a form that did not fit, a recipe step that had to be worked around.
One line — date · what · where in the template to fix it. The template's keeper
lifts the lessons from here.

- 2026-11-15 · the administrator's level (two people at one base) is not in the template — `meta-vault/admin.md` here; a form for it · `template/meta-vault/`
- 2026-11-15 · «tidy the computer» (the owner's folders → `inbox/`) is not in the template · `template/meta-vault/operations/`
- 2026-11-15 · a records folder of folders (`lots/<year>/<id>/` + a card) — the zone form speaks only of files · `forms/zone-form.md`

## Method files (shipped from the template on [[operations/accept-new-version|a new version]])

`meta-vault/vault-template.md` · `meta-vault/principles.md` ·
`meta-vault/glossary.md` · `meta-vault/forms/` · `meta-vault/examples/` ·
`meta-vault/harness/` · `meta-vault/operations/build-namespace.md` ·
`new-domain.md` · `add-engine.md` · `check-links-and-names.md` ·
`accept-new-version.md` · `ingest.md` · `query.md` · `lint.md` · `bin/check` ·
`bin/setup` · `bin/setup.ps1` · `.gitattributes`. Everything else is the owner's —
including `log.md` and `sources/`, which are the base's own history.

## Build journal

Newest on top; layout only.

- 2026-11-15 — built: frame form 2026-11-10; domains `tenders/` (from `project/`), `firms/`, `office/`; engine
  and tender layer carried from the previous agent (EASY TENDER instance, archived); the admin level.
- 2026-11-09 — the template.

---
title: Owner — profile of the namespace owner
type: reference
status: active
sensitivity: private
scope: all
updated: 2026-11-15
tags: [owner, profile, identity]
related:
  - preferences
  - admin
  - HOME
---

# Owner — Маржан

Who the owner is. The agent reads this file to know who it works with; the **rules** of
communication live separately — [[preferences]]. A stub with an honest «not known yet» is fine,
invented data is not. Source of what is below: Скандар's words of 2026-10-23 and 2026-11-10 (the
build was done by the administrator; Маржан confirms or corrects it at the installation).

## Who

- **Name:** Маржан. Surname — not known yet.
- **Form of address:** «вы», by name.
- **Languages:** Russian — the agent speaks and writes to her in Russian.
- **City:** Караганда.

## Agent

- **Agent name:** «агент» — she has not named it yet.

## What she does

- **Large tenders — works and services.** Her filter (10.11): competitions over 20 million ₸,
  acceptance of applications open, no goods. Platforms: госзакуп (including Казводхоз), Самрук,
  Mitwork, МЭКС. Domain — `../tenders/`.
- **Her firms** as participants: Ulytau Building, L.M. Electric (the ones whose financial stability
  was calculated on 10.11); the full list — at the installation. Domain — `../firms/`.
- Papers, contracts, taxes of the legal entities — `../office/`.

## Context for the agent

- She asked for (10.11, through Скандар): a firm by its BIN — contracts of the current financial year,
  territoriality by the tax office, negative values, audited reporting, the register of unreliable
  suppliers for 5 years, all against the rules of procurement; a table like the «протокол итогов»;
  financial stability from 1С — for this year and the next.
- Small goods tenders are not her work here.
- Her key to the procurement portal is her own (`../secrets/goszakup-token`); the tax committee (КГД)
  key — not issued yet.

## Browser

Маржан has several Chrome users (profiles); the Claude extension is one for all of them (Скандар's
word 2026-11-15 — to be checked at the installation). The map — purpose only, no logins or passwords:

| Profile | Whose / what for | The agent may |
|---|---|---|
| _(filled at the installation)_ | | |

Open platform pages (Самрук files, Mitwork) — from the profile marked «агент» or the one she names.
A firm's cabinet — only from that firm's profile, only reading, only on her request.

## What this file does not hold

Secret identifiers (document numbers, accounts, IIN) do not go here: they live in scans in
`office/docs/` and `firms/docs/`; access keys — in `secrets/`.

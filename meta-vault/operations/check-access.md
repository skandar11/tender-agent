---
title: check access — проверь доступы
type: operation
trigger: phrase («проверь доступы», «всё ли работает»); the installation
executor: agent → engine/scripts/ows.py · portal.py · bin/check
status: possible
sensitivity: normal
scope: all
updated: 2026-11-15
related:
  - ../admin
  - ../secrets-map
---

# Check access

**When:** «проверь доступы», «всё ли работает», the installation, after a new version.

Report — a table: what · works / does not · what to do. Read only: nothing is changed.

1. **Python and the engine** — `python3 --version` (Windows: `py --version`); `python3 bin/check`.
2. **The portal key** — `python3 engine/scripts/ows.py check` → «доступ есть». 403 — the key was issued
   for another address: Маржан re-issues it in her cabinet (Профиль участника → Выпуск токена) from
   this machine. 500 — the portal is down, repeat in a few minutes.
3. **The platforms without a key** — `python3 engine/scripts/portal.py lots --limit 1` and
   `portal.py meks --min 20000000` answer; МЭКС sometimes gives 502 — repeat.
4. **The КГД key** — `secrets/kgd-token` is there or not; without it — no territoriality and taxes
   (`firm.py` says so itself).
5. **The browser** — the Claude extension answers; which profiles are connected; the map in
   [[../owner|owner]] §Browser matches.
6. **Git** — `git status`, the remote, the last commit; unpushed commits — a line, push by Скандар's word.

Write down: the date and the result — a line in [[../structure|structure]] §Health.

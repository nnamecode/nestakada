# DEV-09N exact13 — независимое ревью implementation plan

Дата: 2026-11-15. First verdict: **CHANGES_REQUESTED**, P1/P2/P3=`0/2/0`.

- `N13-PLAN-R01`: общий 64 KiB cap был ниже фактических authority CSV и media. Remediation: отдельные caps route-map128 KiB, route-evidence/media-evidence256 KiB, source/artifact128 KiB, each media256 KiB, total media2 MiB; exact-cap/cap+1 negatives сохранены.
- `N13-PLAN-R02`: IMP-004–006 не требовали RED до product behavior. Remediation: каждый срез начинается с focused test addition и expected RED через named wrapper после owner code gate/fresh foundation, затем minimal code и GREEN.

Остальные границы reviewer принял. После remediation требуется repeat read-only review; code/package/config/test execution остаются закрыты.

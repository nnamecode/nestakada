# DEV-09N exact13 — независимое ревью области

Дата: 2026-11-15. First verdict: **CHANGES_REQUESTED**, P1/P2/P3=`0/2/1`.

Рецензент read-only подтвердил exact13, арифметику 101/114, exact7 media, существующие десять `Page.Kind`, реализуемость navigation/breadcrumbs/SEO и no-widget Reviews/Contacts profile. Docker, тесты, сеть и файлы рецензент не менял.

Findings:

- `N13-R01` P2: `tel:` не проходит общий sanitizer, а proposal не задавал typed source для template. Remediation: один bounded `contacts_profile` в existing page revision schema, exact `tel`/`mailto`/route facts, без model/migration/runtime package read и без глобального расширения link policy; negative schemes обязательны.
- `N13-R02` P2: filesystem и PostgreSQL нельзя обещать одной транзакцией. Remediation: exact7 media prepare/replay/recovery отдельно; page writer только preflight/recapture exact READY assets и атомарное присоединение all13 aggregates/usages. Recoverable media over-preparation допустима, partial Page aggregate запрещён.
- `N13-R03` P3: owner approval не был записан. Remediation: D-1093 фиксирует ответ «Продолжай» как scope approval и разрешение independent review, но не code/implementation.

После remediation требуется repeat read-only review только `N13-R01–R03`. До `APPROVED` implementation plan и product code запрещены.

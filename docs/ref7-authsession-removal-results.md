# REF-07B: результат удаления legacy `AuthSession`

Дата: 2026-11-09
Основание: D-664, D-667, уточнение D-668; приёмка ASDROP-001–008 из `docs/ref7-authsession-removal-plan.md`.

## Результат реализации

- До удаления: legacy `AuthSession` 3 строки, Django `Session` 3 строки, `AuthResourceState` 2 строки.
- До миграции создано и изолированно проверено backup-поколение `dd5af316-cbcf-4648-a6f6-fd70c18f67b5`: tables 42, migrations 30, media files 15 / 6240 bytes.
- Добавлена `accounts.0004_delete_authsession` только с `DeleteModel(AuthSession)`; historical `0001` не изменялась.
- Модель удалена из product runtime. Первое независимое ревью выявило остаточные ссылки в активном acceptance harness; их устранение и повторная проверка выполняются по D-670.
- В основной test DB таблица `accounts_authsession` отсутствует. Django DB-backed sessions и generation/issued/last-seen проверки сохранены.
- Synthetic reverse `0004→0003` создаёт пустую schema-таблицу, повторный forward её удаляет. Три исторические строки возвращаются только восстановлением pre-migration backup.

## Проверки

- Focused accounts + page deletion: 51/51 PASS.
- Full standard PostgreSQL suite: 302/302 PASS.
- Editor regressions после актуализации legacy fixtures: `combined` 3/3, `price-gui` 4/4, `restore-terminal` 6/6, `table-gui` 5/5 PASS.
- Итоговый full editor: 242/242 PASS за 700.089 s.
- После устранения двух P1 D-670: 16/16 fixture load PASS, targeted restore-terminal 6/6 PASS за 24.894 s, повторный full editor 242/242 PASS за 695.186 s.
- `manage.py check`: 0 замечаний. `makemigrations --check --dry-run`: no changes.
- Финальные counts: Django Session 3; AuthResourceState 2; pages 6; revisions 22; states 6; drafts 1; stages 3; pins 1; receipts 396; identities 765 — совпадают с pre-migration.
- Secure stale-generation contract: прежняя сессия после grant change получает 401; fresh session без поля получает 403; old replay поколения1 получает 403; old stage поколения1 остаётся 409; новая stage поколения3 работает и обе корректно инвалидируются сменой current.
- Backup catalog после проверки: current `dd5af316-cbcf-4648-a6f6-fd70c18f67b5`, previous `5adf6799-9797-49ac-b2ec-da22ea493868`, generations 2.
- Foundation остановлен штатно; named volumes и backup сохранены.

## Границы

`django_session`, `AuthResourceState`, `LoginThrottle`, runtime-active R7-I003 и orphan TRUST volume не удалялись. Production/VPS/старый сайт не затрагивались. Legacy shared-public suite со старым ожиданием `SharedReceipt` не расширял scope REF-07B; основной standard и полный editor-наборы прошли.

Первое независимое ревью: `CHANGES_REQUIRED` по двум P1 (остаточные fixture/scanner refs и неотделённый от CSRF `403` в RST005). Оба замечания исправлены и основные проверки PASS. После D-672 все 13 current ignored browser freeze manifests обновлены отдельными точными patches; все 41 file/SHA записи сверены PASS по D-673. Повторное independent review: `APPROVED`, P1/P2/P3 нет. REF-07B завершён по D-674.

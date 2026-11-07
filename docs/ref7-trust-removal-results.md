# REF-07A: результат удаления изолированного TRUST-контура

Дата: 2026-11-06
Статус: завершено; независимое ревью `APPROVED`, P1/P2 нет.

## Результат

Удалены ровно 91 tracked-файл R7-I001 общим объёмом 1588741 байт:

- `trust/**`;
- `environment/trust/**`;
- именованные TRUST tools/tests и `scripts/local-trust.ps1`;
- `tools/dev29/**`, включая source-only checkpoint ZIP.

Копия удалённого исходного кода в репозитории не создавалась; восстановление остаётся в Git. Модели, migrations, таблицы и данные приложения не менялись.

## Проверки R7A-001–008

- exact Git diff: 91 согласованное удаление;
- runtime/config search вне docs/work: ссылок на `trust_service`, `trust-db`, TRUST environment и удалённые entry points нет;
- foundation search: старый TRUST-контур не используется; `--auth-local=trust` относится к стандартной авторизации временной restore-БД, поле `trust` в lock-файле — описание проверки APT index;
- foundation compose config: PASS;
- новый test source snapshot и PostgreSQL: PASS;
- focused исправленных regressions: 5/5 PASS;
- полный штатный набор: 302/302 PASS за 315.103 с; Django system check: 0 issues;
- `makemigrations --check --dry-run`: `No changes detected`;
- `git diff --check`: PASS;
- test foundation штатно остановлен, application containers/networks удалены, named volumes сохранены.

Полный набор до исправления выявил два устаревших `SimpleTestCase` после появления DB session middleware и одно устаревшее ожидание password-race после REF-06A. Исправлены только тесты: foundation использует `TestCase`, а password-race ожидает fail-closed `TREE_SESSION_ENDED` и по-прежнему доказывает отсутствие мутаций/audit/receipt/identity. Продуктовый security/runtime-код не ослаблялся.

## Backup и остаточные данные

Локальный backup не менялся:

- catalog SHA-256: `fe36fd933b835c2363596fcfa6f3d7dfe79bac969085d9edce6d3688908a53f4`;
- current: `5adf6799-9797-49ac-b2ec-da22ea493868`;
- previous: `818e2c86-6c38-4159-a05f-03e3633c48db`;
- generation directories: 2, по четыре прежних артефакта в каждом.

TRUST containers и networks отсутствуют. Обнаружен один старый named volume `nestakada-trust-test-dbdata`. Он намеренно не удалён: REF-07A разрешал удаление файлов, но исключал данные. Volume недоступен удалённому runtime и требует отдельного явного решения владельца, если его нужно уничтожить для освобождения места.

Production, VPS и старый сайт не затрагивались.

## Независимое ревью

Рецензент подтвердил exact 91 deletion в согласованных группах, отсутствие оставшихся trust-named/runtime/config/CI ссылок, независимость foundation/backup/restore и неизменность schema/data/migrations приложения. Переход foundation tests на `TestCase` обоснован обязательным чтением DB session middleware; более ранний `TREE_SESSION_ENDED` в password-race сохраняет fail-closed DEL-002 и все unchanged assertions. Findings: нет.

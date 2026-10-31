# DEV-03 — вход, сессии и права

Основание D-320/321; REQ-014/015/016/021/060, security-baseline ARC-SEC004/005/006, архитектура§11, PR08, принятые UI-состояния D-307. Перед кодом: existing12 AUTH-LOGIN/LIMIT из acceptance/auth-login.spec.js, session/reset/disable LIFE и unsaved-editor дают поведенческий контракт; редактор/заявки не подменяются заглушками.

План модельных/HTTP/security проверок DEV03-M01..M12: (01) owner/employee реальный вход/закрытый ответ/logout; (02) одинаковый отказ unknown/wrong/disabled/blocked +CSRF/GETunsafe; (03) IP-only5/600/900, mixedlogins, успех очищаеттолькосвойIP; (04) довериеIPтолькоsingleownNginx и forgedheaders; (05) idle30min/absolute12h и пассивная проверка безпродления; (06) reset/disable/generation отзываютстарыеsession; (07) владелецсоздаётсотрудника/пароль и серверныйdenyselfreset; (08) grantтольконазначеннымservice/article и allowedtext, priceoff; (09) отзывgrant действуетнаследующийзапрос; (10) лимит/очисткаистёкших/failclosed безразрушенияживыхsession/throttle; (11) конкурентныеотказы/пятаяпопытка/права; (12) локальная интерактивная owner management команда+safeaudit.

Ограничения: безMFA/email/CAPTCHA, без новых парольных бизнес-правил. Есть Django hashing, непустой пароль и ограничение размера транспортного ввода; старый пароль не читается. UIредактора/несохранённыйтекст, версии, заявки/ихпереназначение и break-glass восстановления будутсвоимимодулями. DEV03 реализуетосновуправ/инвалидации дляихдальнейшейинтеграции.

## Реализовано

Завершено 2026-10-31 (начато 2026-10-30) по D-320, локальные настройки D-321/D-322. Код: app/accounts; зарегистрирован /manage/, его точный SYSTEM route и запрет конфликтующей публичной страницы в частном namespace. Старый сайт, VPS и preview не менялись.

- Вход/выход с CSRF, закрытая страница текущего пользователя и список доступных страниц; владелец создаёт сотрудников, задаёт новый пароль, отключает/включает доступ и назначает intro/main/price. Авторизация использует реальную роль UserProfile и nesadmin; флаги штатного Django superuser/staff не подменяют её. Прайс выключен по умолчанию, главная/каталоги/служебные типы не выдаются сотруднику.
- Сессия привязана к пользователю/поколению, максимум 12 часов и idle 30 минут; пассивный GET /manage/session/ не продлевает idle. Сброс пароля/disable/локальный revoke-all hook закрывают прежние сессии, enable их не оживляет. Текущие права проверяются заново; ожидаемое поколение владельца перепроверяется в owner-командах.
- IP берётся из реального peer. Только для собственного Nginx (точное сопоставление peer с его Docker DNS) принимается один X-Real-IP, который Nginx перезаписывает; XFF/Forwarded не доверяются. PostgreSQL сериализует 5 подтверждённых неудач за 600 с, блокирует источник на 900 с, успех очищает только свой IP. Время читается внутри блокировки, включая конкурентные touch одной сессии. Неизвестный логин/неверный пароль/blocked дают одинаковый безопасный отказ и выполняют password-hash verification.
- Локальный Nginx: 10 запросов/с/IP и burst20 на вход, ограничение тела входа 16 КиБ до Django. Внутренняя валидация форм не повторяет пароли, отвергает лишние/повторные поля и неподдержанный multipart. Закрытые запросы проверяются до дорогого разбора тела; ответы private,no-store, включая ошибки. Политика Secure cookies остаётся отдельной для локального HTTP и deployment-audit.
- Квоты D-321: до10000 LoginThrottle и1000 AuthSession на среду. При исчерпании новый ключ/сессия не создаётся; живые не вытесняются. Очистка только истёкшего состояния выполняется при входе и management cleanup_auth. Два фиксированных resource-state агрегируют переходы заполнения. Автозапуск/расписание Windows не добавлены; плановый эксплуатационный вызов согласуется со служебными задачами/хостингом.
- Аудит входов, сбросов, disable, grant и значимых отказов; неизвестные анонимные GET не создают AuditEvent/сессии/throttle. Неудачи и blocked/permission repeats агрегируются с отдельным bounded счётчиком, не теряются при expiry/успехе/logout. Общая схема AuditEvent дополнена только положительным typed occurrence_count и count_is_lower_bound; переполнение не выдаётся за точное количество. Нет raw payload/пароля/токенов/полного URL в аудите.
- Интерактивные локальные create_owner/recover_owner: скрытый ввод, штатный Django PBKDF2, без argv/env password. Ошибочные аргументы отклоняются до argparse без повтора их значений; recover закрывает прежние owner-сессии. Публичной self-recovery/change password сотрудника, MFA/email/CAPTCHA нет. Это обычный owner recovery, не break-glass после отката/компрометации.

## Проверки и свидетельства

| Проверка | Факт |
|---|---|
| Финальный PostgreSQL unit/integration | 75 PASS, 14.999 с: 34 accounts +41 прежних. work/foundation/test/checks/dev03-unit-final.txt |
| Миграции и Django checks | accounts0001–0003, audit0002 применены; makemigrations --check --dry-run: No changes detected; check:0issues/0silenced |
| AUTH-LOGIN/LIMIT | Исходные12 сценариев без изменения проверок: 12PASS,0skipped/unexpected/flaky,155.556с; test-results/acceptance/auth-login-results.json |
| Реальные разные источники | Два временных Nginx helpers → собственный ingress; actual IP/Dockeridentity + реальные limiter rows и X-Request-ID сверяются. A/A2 делят IP, B другой; тесты не подменяются XFF/ожидаемыми ответами |
| FOUNDATION | 11PASS,6.916с, host guard до/после; test-results/acceptance/foundation-security-results.json |
| Harness/driver safety/browser startup | 96PASS,45.723с (86driver,4document,6browser), test-results/acceptance/harness-results.json |
| Возврат среды после Auth fixture | work/foundation/test/checks/dev03-fixture-restored.json:0users/profiles/native+authsessions; local_http, testClockFalse, нет clockmount/helpers. controller-state.json:runIdnull/ownedIDs[] |
| Визуальная проверка входа | Реальный Chromium CLI: desktop1280×900 иmobile390×844, поля/кнопка не обрезаны. output/playwright/dev03-login-desktop.png и dev03-login-mobile.png; это не полная браузерная/визуальная приёмка админки |
| Финальные документные проверки | 4PASS после обновления реестра; git diff --check PASS |
| Проверка известных credentials | 182изменённых/новых текстовых файла,0совпадений; runtime/скриншоты игнорируются Git |
| Независимое ревью | [dev03-review.md](dev03-review.md), DEV03-REV-001–005 закрыты |

Снимок финального unit-прогона:583be8dd-29ab-4146-8887-8d3ce146f00d, SHA256 e5fd5faa6cc5210cba87007bb4df2bab60634b9e5f40907093e775bf9dc41eb0. После успешных12Auth/11Foundation доработаны только secure console helper,2команды иихтест. Сравнение сохранено в checks/dev03-auth-domain-comparison.json:56файлов неизменны, ровно4ожидаемых изменения; login/session/rights/proxy домен не менялся. Эти сетевые сценарии не объявляются повторно запущенными после console-only fix. Финальные75 unit/checks выполнены на новом снимке. После них отдельно просмотрена рецензентом одна текстовая правка error.html: нейтральное сообщение не обещает отсутствие записи при неопределённом результате БД. Логика не менялась; повтор runtime для такой copy-правки не требуется. SHA выше относится к снимку unit-прогона, а не к последней рабочей копии; точный единственный diff — checks/dev03-copy-delta.json.

Начальный snapshot изменений: work/dev03-20261030/before (tracked diff и136 untracked). Первый unit-прогон выявил гонку времён/счётчика и обработку пустого POST; исправлены причины, отдельно исправлено управление часами самого теста. Первый сетевой прогон имел3pass и20с timeout инструмента на длинной последовательности; тестовый budget auth-проекта120с и лишний hash в read-only observer исправлены, бизнес5/600/900 и12проверок сохранены. Скрипт всегда возвращает обычный профиль/убирает helpers; слепых эквивалентных повторов не было.

## Запуск локально

Используются уже согласованные Docker/образы, новых пакетов/системных настроек нет. Обычный запуск:

```powershell
.\scripts\local-foundation.ps1 -Environment dev -Action Start
# Владелец сам вводит пароль скрыто в локальной консоли:
docker.exe exec -it nestakada-foundation-dev-app python manage.py create_owner
# При обычной утрате пароля:
docker.exe exec -it nestakada-foundation-dev-app python manage.py recover_owner
```

Вход dev: http://127.0.0.1:8766/manage/login/. Пароли в чат/аргументы/env не передавать. Реальный постоянный owner этим заданием не создан: только синтетические тестовые аккаунты, затем удалённые.

Проверки: Start test → UnitTests; scripts/test-foundation.ps1 дляобычного профиля; scripts/test-auth.ps1 длявременного auth_isolated/двухIP. Оба сетевых режима запускать последовательно: runner использует один scratch. Auth fixture требует пустую таблицу пользователей или точно зарегистрированные собственные synthetic IDs; чужие пользователи не удаляются. Тестовые часы существуют только в явном auth_isolated/test профиле, Windows/VPS clock не меняется. Пакет и browser images на T:, token/control state в игнорируемом work с DACL владельца/SYSTEM.

## Границы следующей очереди

Текущий этап8, DEV-03 завершена в ограниченной очереди. Следующая задача DEV-06 — медиа/использование/безопасная очистка; её код ещё не разрешён. Не пройдены все140AC/полные AT014/015/016/060, production/настоящийproxy/HTTPS/нагрузка и реальные8×3браузера. Параметры10000/1000/10rps/burst20 не являются измеренным бюджетом VPS.

Редактор/черновики/история/сохранность ввода в реальном редакторе и контентные права интегрируются в DEV-05/07/29. Несохранённый текст здесь не записывается в localStorage/URL и не восстанавливается после закрытия вкладки; полного editor UX пока нет. Передача открытых заявок при disable (REQ036) в этой очереди не симулируется: самих ServiceRequest ещё нет, интеграция обязательна при соответствующем модуле. Полные категории/файлы/квоты30дней/Telegram и защита всех сканов/бэкграунд-задачи остаются DEV-17/20 ислужебными задачами. Внешний head, фактическое восстановление и break-glass остаются своими воротами.

Контейнеры в конце остановлены, БД/секреты/артефакты сохранены вне Git; старый сайт/VPS/preview не менялись. Push не выполнялся.

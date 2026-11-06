# REF-2 — приёмочные сценарии рефакторинга

Дата: 2026-11-05. Статус: проект окончательного набора для архитектурного ревью и REF-Q002; реализация тестов не разрешена D-597.

## 1. Общие правила

- Все заявки и пользователи синтетические; реальные ПД запрещены до LEGAL-01.
- Внешние email/Telegram заменяются локальными fake adapters с независимыми отказами и bounded timeout.
- PostgreSQL используется там, где проверяется транзакция, блокировка, SQLi или rollback.
- Nginx/fallback проверяется только в локальном изолированном окружении.
- Секреты, cookies, телефоны, тела заявок и HTML содержимое не попадают в test reports.
- Каждый сценарий имеет постоянный REF-AC ID; внутренние unit cases могут быть многочисленнее.
- Первоначальный FAIL допустим как baseline, но не является приёмкой.

## 2. Пользователи и права

| ID | Уровень | Действие | Обязательный результат |
|---|---|---|---|
| REF-AC-001 | e2e | Владелец входит по логину/паролю | Доступна админка; cookies secure policy; приватные ответы `no-store`; лишних способов входа нет |
| REF-AC-002 | integration/e2e | Сотрудник открывает назначенную страницу | Видит страницу и только разрешённые поля; не видит owner-only действия |
| REF-AC-003 | security integration | Сотрудник подменяет POST/JSON и URL | Защищённые поля, URL, Stable, пользователи и права не меняются; сервер возвращает безопасный 403/409 и пишет bounded audit |

## 3. Версии, Stable и общие блоки

| ID | Уровень | Действие | Обязательный результат |
|---|---|---|---|
| REF-AC-004 | integration/e2e | Разрешённое сохранение страницы | Одна новая automatic revision и новый current создаются атомарно; публичное чтение видит её |
| REF-AC-005 | integration | Создать >10 обычных версий при существующей Stable | Остаются 10 последних ordinary; Stable и её media не удалены; новая версия не наследует Stable |
| REF-AC-006 | integration/e2e | Восстановить старую версию owner/employee | Создаётся новая revision; URL/защищённые поля не меняются; сотрудник восстанавливает только разрешённые поля |
| REF-AC-007 | integration/e2e | Сохранить и восстановить Header/Footer | Owner-only операция создаёт DB revision; публичный renderer использует current; отказ оставляет предыдущий current; filesystem journal не нужен |

## 4. Дерево, URL и публикация

| ID | Уровень | Действие | Обязательный результат |
|---|---|---|---|
| REF-AC-008 | integration | Rename/reorder/move страницы | Транзакция сохраняет дерево, sibling order и legacy URL; цикл/конфликт отклоняется без частичного изменения |
| REF-AC-009 | integration/e2e | Publish/hide | Публичная выдача и навигация меняются атомарно; hidden не воскресает через alias/cache/HTML reserve |
| REF-AC-010 | integration/e2e | `nesadmin` подтверждает удаление страницы | Удаляются страница и все её версии, включая Stable; поддерево/чужие shared media не удаляются неявно; сотруднику операция запрещена |

## 5. Медиа, аудит и отказоустойчивость

| ID | Уровень | Действие | Обязательный результат |
|---|---|---|---|
| REF-AC-011 | security integration | Загрузить oversized/неподдерживаемый/polyglot/опасный файл | Файл не становится READY/публичным; временные данные очищены; безопасная ошибка без утечки path |
| REF-AC-012 | integration | Выполнить вход, save, Stable, delete, notification failure | Audit фиксирует actor/action/result/time без password/token/cookie/телефона/comment/body |
| REF-AC-013 | fault integration | Вызвать отказ до/после DB write или file move | Старый public current цел; неизвестный исход не выдаётся за успех; повтор не создаёт дубликат |
| REF-AC-014 | smoke | Запустить основной сайт без TRUST containers/env/API | System check/start/admin/core операции проходят; нет import/network/config зависимости TRUST |

## 6. SQL injection и сканирование

| ID | Уровень | Действие | Обязательный результат |
|---|---|---|---|
| REF-AC-015 | security integration | SQLi payload в path/query/form/JSON/sort/filter/editor | Структура SQL не меняется, DDL/чужое чтение/запись отсутствуют, runtime role не имеет DDL, ответ не раскрывает SQL/trace |
| REF-AC-016 | security/perf | Известные scan paths и bounded поток неизвестных путей | Известные paths получают короткий 404 до session/DB; лимиты действуют; аудит агрегирует шум; normal URL не блокируется |

## 7. Ручной HTML-резерв и Nginx fallback

| ID | Уровень | Действие | Обязательный результат |
|---|---|---|---|
| REF-AC-017 | integration/e2e | `nesadmin` нажимает build; employee/anonymous повторяют | Owner build формирует проверенный набор; employee/anonymous получают 403/login; concurrent build не запускается |
| REF-AC-018 | fault integration | Build прерывается/даёт missing URL/private leak | `current` и `previous` не меняются; staging очищается/помечается безопасно; ошибка видна owner/audit |
| REF-AC-019 | integration | После build публикуется изменение, затем новый build | Резерв помечен stale без auto-build; успешный новый current сдвигает прежний в previous атомарно |
| REF-AC-020 | Nginx smoke | Upstream даёт normal/502/503/504, затем восстанавливается | Fallback только public GET/HEAD на error; POST, `/manage/`, private и normal 404 не подменены; возврат к Django автоматический |
| REF-AC-021 | content/security | Проверить HTML set и форму заявки | Нет admin/history/preview/ПД/token; форма не сохраняет данные и честно предлагает согласованный контакт без ложного success |

## 8. Минимальные заявки

Синтетика: owner `nesadmin`, employee `worker1`, заявка «Тестовый клиент», телефон из зарезервированного тестового диапазона, fake email/Telegram adapters.

| ID | Уровень | Действие | Обязательный результат |
|---|---|---|---|
| REF-AC-022 | integration/e2e | Отправить валидную заявку, открыть owner/employee/anonymous | Одна строка с `created_at`; owner и employee read-only видят; anonymous не видит; response `private, no-store` |
| REF-AC-023 | integration | После DB save проверить оба fake channels | Email уходит на адрес из owner settings, Telegram — в env chat; оба получают согласованный состав; secrets/ПД отсутствуют в logs |
| REF-AC-024 | fault integration | Независимо сломать email, Telegram, оба; повторить потерянный response | DB-заявка сохраняется ровно один раз; исправный канал работает; bounded safe errors записаны; visitor не получает ложную потерю |
| REF-AC-025 | security/e2e | Owner и employee пытаются delete | `nesadmin` удаляет после confirm+CSRF без password re-entry; employee не видит кнопку и получает 403 прямым POST; settings также owner-only |
| REF-AC-026 | schema/UI | Проверить model/admin/templates/API | Есть только согласованные поля и `created_at`; нет status/assignee/notes/history/`updated_at`; список не поддерживает mutation сотрудников |

## 9. Backup/restore и структурированный редактор

| ID | Уровень | Действие | Обязательный результат |
|---|---|---|---|
| REF-AC-027 | ops integration | Создать local и encrypted external set; вызвать failure новой копии | Комплект содержит DB+media+manifest/checksums, secrets не открыты; failure не удаляет последнюю good; safe result log создан |
| REF-AC-028 | isolated restore | Восстановить выбранный комплект в отдельную DB/media | Checksums/schema/migrations/smoke/ключевые counts проходят; production не меняется; процедура и ошибки понятны владельцу |
| REF-AC-029 | security integration/e2e | Редактировать каждый Page.Kind и отправить arbitrary layout/script/template | Разрешённые structured fields сохраняются; неизвестные blocks/HTML/JS/Django syntax отклонены; preview и public используют один renderer/sanitizer |

## 10. Отзыв доступа, удаление данных, медиа и логи

| ID | Уровень | Действие | Обязательный результат |
|---|---|---|---|
| REF-AC-030 | restore/privacy integration | Удалить синтетическую заявку, затем восстановить backup старше удаления | До DB-delete UUID+время durable записаны во внешний ledger без ПД; отказ ledger блокирует delete; restore применяет ledger до открытия сайта, заявка не воскресает |
| REF-AC-031 | security integration/e2e | При активной employee session отключить пользователя, сменить/сбросить пароль, роль и PageGrant | Каждое изменение увеличивает `UserProfile.generation`; старая Django session получает отказ/завершение на следующем закрытом запросе; новая session видит только актуальные права |
| REF-AC-032 | media integration | Пытаться удалить asset, используемый current/ordinary/manual/Stable/draft/Header/Footer/current-or-previous HTML; затем удалить свободный asset | Используемый asset/file не меняется; свободный удаляется контролируемо; ошибка не удаляет metadata частично; SHA всех 214 legacy originals до/после совпадают |
| REF-AC-033 | logging/ops integration | Создать audit/error/scanner/notification failure, выполнить rotation/limit и смоделировать отказ technical log | Owner видит важные события/ошибки; scanner шум агрегирован; rotation/общий cap не удаляют protected audit; отказ наблюдаем; Django/Nginx/PostgreSQL outputs не содержат password/token/cookie/phone/comment/body |

Для REF-AC-027 в одном локальном и одном внешнем месте сохраняются `current` и `previous`; логически плохой новый `current` не уничтожает предыдущее проверенное поколение.

## 11. Пирамида выполнения

- На каждый commit: targeted unit/integration и security affected set.
- На завершённый функциональный инкремент: все связанные REF-AC, полный Chromium и независимый code review.
- Перед выпуском: все REF-AC, Firefox/WebKit smoke, реальный телефон/Яндекс Браузер, deploy checks и restore rehearsal.
- Никаких атакующих проверок против старого/живого сайта; только локальное изолированное окружение.

## 12. Ворота готовности REF-2

REF-2 готов к REF-Q002, когда независимое архитектурное ревью подтвердит:

- каждый обязательный инвариант плана связан хотя бы с одним REF-AC;
- ни один сценарий не требует TRUST/admission/evidence architecture;
- сценарии заявок соответствуют D-596 и LEGAL-01;
- удаляемые старые tests имеют указанный replacement REF-AC;
- тесты исполнимы без секретов, реальных ПД, production и бессрочных диагностических архивов.

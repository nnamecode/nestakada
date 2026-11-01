# DEV07-RUI — сообщения завершённой подготовки восстановления

2026-11-01. Продолжение после DEV07-RST по поручению владельца «давай дальше». Реализация существующего D07-018, без новых DTO, маршрутов, зависимостей, прав, TTL и cleanup. Использовать прежний HTML-экран отказа и HTTP409. Новая квитанция операции при чтении не создаётся.

| ID | Проверка до кода |
|---|---|
| RUI-001 | Свой released stage_read сообщает: «Подготовка восстановления отменена. Данные для подстановки не выдаются. Текущая версия страницы не изменена этим просмотром.» Без candidate/редактора/receipt, current/history/pins/receipts неизменны |
| RUI-002 | Свой consumed stage_read сообщает: «Подготовка восстановления уже применена. Повторная подстановка недоступна. Текущая версия страницы не изменена этим просмотром.» Без candidate и повторного применения |
| RUI-003 | Свой invalidated stage_read сообщает: «Подготовка восстановления утратила актуальность. Подготовьте восстановление заново из истории. Текущая версия страницы не изменена этим просмотром.» Без автоматического нового stage/redirect/rebase |
| RUI-004 | Свой held stage, несовместимый с актуальными current/rights/generation, получает сообщение об утрате актуальности, но read не меняет status/pins и не превращается в cleanup. Точное восстановление прежних grants до штатной invalidation сохраняет старый разрешённый положительный путь |
| RUI-005 | Чужой stage при одинаковых правах на ту же Page, missing UUID и отказ текущих прав/сессии не раскрывают terminal status/actor/source/candidate. Нет владельческого обхода actor binding. Свой совместимый held stage продолжает показывать настоящий candidate по прежнему пути |
| RUI-006 | Не связанный с VERSIONS_STAGE_STALE отказ совместимости/медиа/preflight не маскируется новым сообщением. Metadata lookup не читает исторический payload. Повторные GET не создают версий/receipts/version audit, не освобождают pins и не возвращают HTML через fallback current |

Технический порядок: перехватить только точный VERSIONS_STAGE_STALE в существующем stage_read; повторно выполнить текущие E.enter/session/Page access checks; прочитать только pk/page/actor/status собственной строки; применить whitelist released/consumed/invalidated/held и фиксированные сообщения на прежнем error.html. Missing/foreign/неизвестный status возвращаются прежним общим отказом. Обработчик не использует фальшивую result/receipt и не вызывает terminate_stage. Редактор selected-source остаётся прежним409 JSON.

Проверки: настоящая PostgreSQL/CSRF/версии, положительный held, отрицательные samePage/samegrants roles, metadata-only query control и строгая сохранность domain/receipt/pin; отдельные Chromium/Nginx DOM-проверки видимых сообщений и отсутствия candidate. Полные гонки read-vs-cancel/preflight, gone после физического удаления, все session/media/MAX/legacy/browser/resource матрицы не закрываются этим UI-срезом. Старый сайт/VPS не трогать; DEV-07 около 98%, этап 8 около 20%.

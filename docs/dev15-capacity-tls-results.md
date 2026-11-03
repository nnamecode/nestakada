# DEV-15: проверка полного снимка через HTTPS

2026-11-02. Основание: D-380, RP15-011/020, [сценарии](dev15-capacity-tls-checks.md). DEV-15 около 92%, этап 8 около 28%. Это продолжение проверки локального компонента; включение рабочего допуска записи и DEV-29 не выполнены.

## Подтверждено

Исправлена ошибка проверочного ACL-инструмента TLS-REV-003: PostgreSQL отклонял пустой массив в aclexplode. Точный SQL/22023 сохранён в readonly diagnostic; исправление NULLIF прошло независимое ревью и AST-проверку реальных непустых исходников. Первый preflight FAIL сохранён отдельно, до выдачи прав.

На исправленном инструменте фактически прошли verify, минимальный grant и restore. Временный runtime доступ ограничен точной UNIT/OID32563, четырьмя таблицами чтения и UPDATE(id) Head для блокировки строки. Контроль запрещённых UPDATE(mode)/INSERT и проверка effective ACL пройдены. В первом успешном ACL-прогоне effective ACL восстановлен, а raw ACL отличается допустимым представлением owner ACL вместо NULL. В последнем resume-003 восстановлены и effective, и raw ACL. После прогонов стенд остановлен, запись disabled, permit пустой.

Все 30 host/frozen исходников компонента сохранились без расхождений: source `5fbcb9d9ea04ee58853b9b8d9fe2131fc6b0d1122f087239f3c66bfded768986`. Прежние 131 UNIT PASS и выбранные capacity A/B результаты остаются отдельными свидетельствами.

## Неустановленный исход первого запуска процесса снимка

После выдачи временных прав Docker exec вернул пустые stdout/stderr. Host не сохранял exit/error/signal и завершился TLS_HOST_FAILED на разборе пустого JSON. Причина не доказана; timeout или OOM не объявляются фактом. Успешное TLS-чтение этим запуском не подтверждено.

Изолированный network-none smoke того же launcher и исходника с пустым ARG вернул ожидаемый JSON отказа конфигурации, exit 1. Это проверяет framing, но не объясняет первоначальный исход. Исходные report/intent и приватный пустой вывод сохранены.

Для связанного Resume подготовлена фиксация stdout/stderr в существующем /tmp API и извлечение до Stop, сохранение метаданных процесса и cgroup до разбора JSON. Отдельные каталог и подписанный дочерний intent сохраняют связь с исходным FAIL. Исходник клиента, лимит 30/6 секунд, отсутствие retries и прежние ресурсы сохраняются.

Resume-001 остановился до probe с TLS_SOCKET_NOT_READY. Verify/grant/restore PASS; effective и raw ACL полностью восстановлены, Stop0. Сам probe не запускался. Дополнительный file-capture smoke не засчитан: Docker создал контейнер, но запуск не подтвердился; точная причина не сохранена, созданный неработающий контейнер удалён после проверки scope/image.

Независимое ревью точного локального Django wheel (5.2.18, SHA92ed81…) выявило несовместимость командного запуска с минимальными правами: runserver безусловно читает django_migrations до bind, SELECT на эту таблицу отсутствует. PostgreSQL introspection не исключает её по отсутствию SELECT. Это доказанный дефект startup-профиля; конкретная причина старого пустого вывода без runtime-логов по-прежнему не установлена.

ResumeStartup/resume-002 связан с resume-001. UNIT-команда проверяет actual DB/OID/роль/disabled/source, требует фактический SQL42501 обычного check_migrations, затем пропускает только повторную migration check в подклассе той же команды. Схема проверяется отдельным host-аудитом до grant. MAIN возвращается к прежней команде; SQL-права не расширяются. Code gate положительный, AST непустой startup-команды PASS. Readiness теперь сохраняет ошибки, состояния, память и логи до Stop.

## Фактический исход resume-002

SQL42501 для django_migrations подтверждён в логах API, bind8000/TLS готовность PASS. Probe завершился exit0 за28.618с host-времени, транспортные stdout/stderr пусты, как и предусмотрено файловым перенаправлением. Cgroup API111587328/268435456, DB291639296/536870912, ingress9732096/134217728байт; OOM и kill0 у всех. Это факты запуска процесса, не подтверждённое содержимое его отчёта.

Итог FAIL TLS_PROBE_FILE_CAPTURE_FAILED: два docker cp вернули1, оба host-файла пустые. Stderr cp не сохранялась, точный текст прежней ошибки неизвестен. [Документация Docker](https://docs.docker.com/reference/cli/docker/container/cp/#corner-cases) указывает ограничения копирования из tmpfs. Исходный FAIL сохранён; ACL восстановлены, Stop0. RP15-011 не закрывается одним exit0.

Один ResumeReadResult/resume-003 заменяет только способ извлечения отчёта: ограниченный Python reader через Docker exec без stdin на том же API ID, O_NOFOLLOW/regular file/1МиБ, приватный полный metadata capture и wx/0600 host-файл. Родительский FAIL, signed intent, startup42501, exec0 и OOM0 проверяются до нового запуска. Exact reader взят из host-кода и прошёл реальный network-none smoke на tmpfs, UID10001/mode600; временный контейнер удалён. Независимый code gate положительный, клиент/30с/права/ресурсы не менялись. До фактического результата и result-review RP15-011 открыт.

## Достоверный результат resume-003

**FAIL: SNAPSHOT_DEADLINE.** Bounded reader извлёк stdout395байт/stderr0, оба reader exit0. Probe exit1, host elapsed33.232с. Получены manifest и45страниц; начато47запросов/успешны46, final head не прочитан. Полные5120items/52страницы/whole SHA не подтверждены. Разделить whole30 и timeout последнего запроса6с можно только временной трассой; host elapsed её не заменяет.

Startup SQL42501/bind/TLS подтвердились повторно, права восстановлены, final stopped0/disabled. Отчёт и intents сохранены; автоматического повторного прогона или увеличения лимитов нет. Следующий разбор — [dev15-tls-deadline-investigation.md](dev15-tls-deadline-investigation.md).

После отказа отдельная readonly сверка PASS: UNIT fullv2/counts/Head полностью совпали с before; MAIN и старый архив неизменны;30host/frozen исходников и config без расхождений. Все9capacity/TLSквитанций имеют корректные HMAC. Последующий Stop/0ownedcontainers подтверждён. Windows PowerShell5.1 подтвердил owner/SYSTEM ACL для165элементов private. MAIN API return в неуспешном resume-003 не выполнялся и не объявляется PASS; все контейнеры удалены штатным Stop, данные сохранены.

Независимое [result-review](dev15-capacity-tls-review.md) приняло факты отказа и сохранности; RP15-011 остаётся FAIL. Рецензент отдельно сверил SHA всех9квитанций без расхождений. Evidence: work/dev15-tls-20261102/final-preservation.json и final-private-acl.json.

Полный CLOSE-02, остаточные ресурсные и байтовые проверки, MAIN activation и native сценарии остаются в работе. Старый сайт, VPS, HTML admission и production не затронуты; push не выполнялся.

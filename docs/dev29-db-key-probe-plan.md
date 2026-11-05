# DEV29-Q027 — один диагностический helper

Статус: предложение, не разрешение запуска. Двухстадийный вариант диагностики+staging возвращён независимым ревью на уточнение; staging исключён. Цель — установить эффективные Linux metadata и read-open под999:999 для известного TLS key, без чтения байтов ключа.

## Границы

Один новый уникальный runId и один helper, без PostgreSQL/SQL, сетей и данных проекта. Pinned Python image sha256:09433387bce7dd726eb2f76918287c04c1fbd340eed1db2aaa3397fbd0474951, pull=never. UID/GID999:999, networknone, rootfsRO, capdropALL, no-new-privileges, memory128MiB,CPU0.25,PIDs32,shm16MiB,lognone,restartno,stdin/ttyfalse. Только один bind <LOCAL_PRIVATE_ROOT>/database-server-key в /probe/key readonly; ни directory bind, ни Docker socket, ни volume/ports. Исходный файл/ACL неизменны.

## Реализация после согласования

Новый отдельный локальный wrapper не меняет runner/frozen42. Сначала offline проверки и независимое ревью кода. Перед native — проверить knownpath цепочку/reparse/regular, ограниченную Windows ACL, metadata и неизменность источника; секрет не читать/не хешировать. Подтвердить exact endpoint/engine и pinned image без pull, чистоту уникальных labels. Один Prepare/one-shot attempt, без повторов.

Helper выполняет фиксированный Python -I -B -c без shell: geteuid/getegid, lstat/stat известного пути, os.access(R_OK), os.open(O_RDONLY|O_NOFOLLOW), затем os.fstat(fd), сравнение regular/type/st_dev/st_ino/size с проверенным stat и немедленный close в finally БЕЗ os.read/file.read/логирования содержимого. Open failure — закрытый errno enum, а не traceback/raw message. Единственный JSON: scope/version,uid,gid,fileUid,fileGid,mode,size,regular,symlink,readable,openReadOnly,openedIdentityMatches,errno. При open-failure openedIdentityMatches=null; при успешном open требуется true, иначе остановка без повторов. Другие поля/невалидный вывод/uid!=999/gid!=999/неregular/symlink/дрейф source => остановка, без исправлений. Отказ open является результатом диагностики, не поводом повторять.

До start проверить inspect helper: exact image/user/argv/mountRO/networknone/caps/limits/logging/no extra mounts. Первый inventory readiness≤44с, info+inventory≤90с; остальные команды≤10с, helper≤10с, cleanup≤30с, весь lifecycle≤180с. Таймаут не продлевать. stdout/stderr≤4096bytes, raw stderr/Env/ключи не сохранять в Git; публиковать лишь закрытую проекцию. При отказе до подтверждения preflight/helper create новые ресурсы не создавать.

Наконец stop/remove только owned helper с проверкой immutable id/runlabel/sameengine; доказать отсутствие helper и новых owned volumes/networks, source metadata/ACL unchanged. Не выполнять prune или очистку чужих ресурсов. При cleanupUNPROVEN — остановка и отчёт, без второго запуска. Независимое ревью фактов и cleanup обязательно.

## Результат

Probe не меняет права и не исправляет DB. После фактов — отдельное конкретное предложение способа доступа и его ревью до реализации. Staging/новый PG Run/старый сайт/VPS/публикация/push не входят. Одно будущее разрешение Q027 может охватить wrapper, offline, review, один условный helper и cleanup; оно ещё не получено.

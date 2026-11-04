# DEV-29: причина таймаутов R021 установлена по локальному журналу

2026-11-04. DIAG29-CAUSE-001 / D-458. [Неуспешный Q021](dev29-bounded-resume-results-002.md) сохраняется FAIL. Новое диагностическое поручение D457 выполнено чтением сохранённых evidence и ограниченного локального host-журнала Docker Desktop; ни одной новой Docker-команды/SQL/Run для этого вывода не запускали. Сырые журналы/секреты/личные пути в проект не копировались.

## Причина последнего отказа

Первый запрос /containers/json застал Docker Engine в состоянии stopped и вызвал cold start linux/wsl. Движок стал ready/running только через19,09с. Два CLI inventory имели native budget8999мс каждый и оба завершились раньше готовности. Последний terminal inventory выполнялся после этой задержки и успел получить пустой успешный ответ. Причина — несоответствие короткого inventory deadline холодному запуску остановленного движка; успешный info/проверка engine identity в этом состоянии не являлись доказательством готовности daemon.

Это непосредственное объяснение R021, не новая гипотеза о spawnSync. Во всех3inventory argv/transport/бюджет были одинаковыми. Последовательность событий не требует нового native probe; сейчас он наблюдал бы другое, прогретое состояние и не объяснил бы прошлое лучше имеющегося журнала.

| UTC4ноября (Москва+3ч) | Нормализованное событие |
| --- | --- |
| 00:16:17.249 | Старт первого inventory call2 |
| 00:16:17.3888109 | Backend получил containers/json и перешёл idle→busy |
| 00:16:17.3963273 | linux/wsl engine stopped→starting |
| около00:16:26.259 | Call2 timeout после9010мс, daemon ещё не готов |
| 00:16:26.0456951 /26.04625 | Control API готов, но backend продолжает ждать Docker daemon |
| 00:16:26.804 | Старт второго inventory call4 |
| около00:16:35.812 | Call4 timeout после9008мс |
| 00:16:36.4880466 | Daemon ready after19.088s, engine starting→running |

Call4 завершился примерно за0,676с до готовности daemon. Backend log доказывает доставку первого container-list request; доставка второго на daemon/API отдельно не доказана. Ранее,23:45:41.199505Z3ноября, backend явно записал stopping→stopped и активацию idle mode. Эти события объясняют stoppedstate последнегоRun; вывод не требует менять настройки ResourceSaver/WSL или предполагать отказ прав/БД. Термин «VM stopped» во внутреннемлоге не выдаётся за доказательство остановки общей WSL VM.

## Независимая проверка и воспроизводимость

Рецензент /root/dev29_publication_review независимо прочитал bounded log≤512KiB (фактически171104bytes) и239строк UTC-окна00:15:17.249–00:17:26.804. STATIC LOG ACTUAL-EVIDENCE REVIEW APPROVED causal conclusion дляR021; raw log не копировался. SHA256 точных выбранных UTF-8строк, соединённых LF безконечногоLF:112597593afb0b2883d2e758f6ed219af546b6f7fc801b3791ec745d532ca686. Это hash evidencewindow, не файл логов в Git.

Дополнительные hashes отдельных исходных строк (безкопированиясамихстрок):

| Событие | SHA256 |
| --- | --- |
| Idle engine stopped | d83ba93feeea88806047791408208ec87eed8c57ffb0087d1314781b95496f78 |
| Query triggered wake | 71c9568c00b9fed31e82dd1e6ed549541ff67a0ef85965b218625cf3d59fa87b |
| Engine starting | f10ffe02d443818d643faaa53902a38ae6a435687483c22393eee97e1b8f2398 |
| Daemon ready | 4cf805297b9c203d175a3d8f5b5533da4198b3d8c260a312b28f713b0f3c3bc5 |
| Engine running | 0e3ef12f784697701449a6946e11a4e7d10f3db59fb14aca2b89c8d375134f43 |

Вывод не переносится автоматически наQ016: его failure2/4 UTC22:51:16.759/22:51:26.395, а текущийlog начинается22:51:35.2921901 и не содержит начала того отказа. СтарыеrawSHA0b8471/d044 совпали; их результаты/история не переписываются. ДокументацияDocker описывает различияResourceSaver/WSL/Hyper-V, но дляэтогоотказа используются локальныеtimestamps/state transitions, а не перенос типовых задержек изdocs. [Docker docs](https://docs.docker.com/desktop/use-desktop/resource-saver/), [Node events](https://nodejs.org/download/release/v26.8.2/docs/api/child_process.html).

## Безопасная диагностика и дальнейшее действие

[Lifecycle-plan](dev29-docker-lifecycle-diagnostic.md) прошёл независимое review; отдельный локальный инструмент подготовлен: syntax2 и18 mocktests PASS. После coordinator static review один inert Node-child qualifier завершилсяFAIL (expectedstatusPASS/actualFAIL,11.39мс); диагностический errorCode в assertion не сохранён, причина этого квалификационного сбоя NOT PROVEN. Повтора не было. Поэтому observer NOT_RUNTIME_QUALIFIED, approved-inputs/attempt/result не создавались; его code review не выдаёт разрешения Probe. Это отдельный необязательный инструмент, его ошибка не опровергает уже установленную по историческому журналу причинуR021. Nativeprobe отменён как ненужный: attempt/result/approved-inputsmanifest не создавать. Это не отказиз-заошибкиновойпробы — новойпробы не было. Его qualification отдельно, не proof причиныR021.

Предлагаемое исправление: отдельный ограниченный допуск готовности первого read-only inventory после простоя, с cold-start budget, перед запускомSQL/once-phase clocks. Не увеличиватьвсеtimeouts и не отключатьResourceSaver. Конкретное изменение в frozencontroller/новыйPGRun потребуютотдельного рассмотрения/согласования; сейчас кодR021/source31/runner/лимиты не менялись. [Предложение readiness](dev29-docker-readiness-proposal.md).

Старый сайт/VPS/DB/корпус сохранны. R021 functional runtime остаётся «Приостановлено владельцу»; INIT/C/T/1000/139 NOT_RUN. DEV-29≈35%, этап8≈31%; диагностика не повышаетfunctionalготовность.

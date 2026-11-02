# DEV-15 — независимое ревью допуска записи и fault/recovery

2026-11-02, D-376. Исполнитель product/probe — shared_contract, координатор — infra/archive/host orchestration, независимый readonly-рецензент — combined_review. Рецензент не меняет проверяемые файлы и не запускает среду.

## Пройденные ворота

Precode WP15-001–013 проверены до реализации. Рецензент подтвердил: additive0002 и явный сохранный UNIT archive внутри прежнего кластера/ресурсов покрываются D-374/D-376 и не требуют нового архитектурного согласования владельца.

Code gate ArchiveUnit → Stop → Start disabled →62 unit → Stop положительный. Проверены full persistent Head/Credential reconciliation digest, own API cgroup против operator attestation DB/ingress, signed runtime/container exclusion, сохранность архива и неподменяемая квитанция.

При отдельном review negative guard найден safety-gap: strict DB-only guard в finally препятствовал бы остановке оставшегося после timeout one-off init. Исправлен до запуска: cleanup проверяет exact scope/project для всех собственных контейнеров; preflight сохраняет DB-only. Финальный SHA guard bcd1e5bf31a57969bcce14126e19d8cede15639d05f09bf5f03de0ac48fc7e7b. Повторное ревью положительное на один negative-run с exact errorCode/unchanged-state → ArchiveUnit → Stop → disabled unit → Stop. Все эти действия фактически выполнены, подробности в dev15-write-results.md.

## Native code/QA gate — положительный

Рецензент отдельно сверил фактические62 PASS46.410с/source19c9… и host/probe. Найденный недостаток сохранности исправлен до запуска: полный случайный план/новый ключ, каждый exact intent и оба signed envelopes сохраняются приватно до отправки/перезаписи; public receipts содержат SHA точных bytes. Gate положительный на один native one-shot: host9018ce3a…, probe24f1794f…, fixed6/3 synthetic scope, обязательный внешний finally Stop независимо от exitcode инструмента. Дополнительных блокеров нет.

Native run фактически PASS15групп, Stop PASS. Затем рецензент подтвердил отдельное оформление postfault archive verify: тот же pinned helper/signed receipt, DB-only+init до768МиБ, точное совпадение результата, noflush/rename/DROP и Stop. Этот запуск также фактически PASS.

## Итоговое result/doc review

Итоговый independent result/doc gate положительный. Рецензент подтвердил62 unit,15 native-проверок и postfault archive verify, лично сверил source21/host/frozen/config drift0, head0→9/epoch1→2/counts4/3/1/2, квоты и свидетельства сохранности. Source/schema/evidence linkage соответствует проверенному ограниченному профилю. Пики RAM относятся только к последним cgroup-периодам, бюджет — наблюдаемый объём, recovery — только synthetic TRUST writer. Материальных исправлений нет; pending-review закрыт.

DEV-15 остаётся в работе, около85%; этап8 около28%. Следующий локальный срез — полный snapshot consumer/безопасный startup. APP/gate integration, физический ARC-10, внешнее размещение/собственное восстановление TRUST и production остаются открыты. Общий профиль disabled; стенд остановлен, история/архив/ключи сохранены. Рецензент ничего не менял и не запускал.

Конечный отчёт должен отличать локальный синтетический writer от APP reconciliation, container KILL от физического отключения питания, потерю тела ответа от packet loss и измеренный объём от дисковой hard quota. Полный DEV-15/ARC-10/production этим не закрываются.

# DEV-15: независимое ревью TLS-измерения

2026-11-02. Рецензент dev15_review проверил результат другого исполнителя, исходники не редактировал и runtime не запускал. DEV-15 около92%, этап8 около28%.

**Факты отказа и сохранности приняты. RP15-011 остаётся FAIL.**

Санитизированный JSON395байт полностью совпадает с report.probe: SNAPSHOT_DEADLINE, 47начатых/46успешных запросов, manifest1/pages45/head0. Probe exit1, host33.232с; оба reader exit0, stderr пустой. Startup marker42501 и bind/TLS пройдены, OOM0 у API/DB/ingress. Whole30/request6 и влияние CPU по этим данным не разделяются; причина прежнего пустого вывода также не доказана.

UNIT Head/V2 before/after, MAIN и архив сопоставлены без различий. Restore effective/raw равны исходным, финал stopped/owned0. Preservation artifact подтверждает30исходников/drift0 и9корректных HMAC; рецензент отдельно сверил SHA всех9квитанций без расхождений. ACL artifact подтверждает165элементов owner/SYSTEM. MAIN API return после отказа не запускался и не получает PASS.

SHA отчёта resume-003: `1a1539208b8da105885ea063853f510fe1033bad414930140e5b0174fa27beca`. SHA final-preservation.json: `6bbcdb32f27446b265dff151a10fbb70ffc0ef0cfb766cf4de16cdd2e75a608b`.

План одного диагностического запуска с трассой≤54fetch и CPU-метриками обоснован. В трассе нужны фактический timeout после pacing и его delay. Прежние30/6/no-retry/caps сохраняются; перед запуском отдельное code-review. Документы оставляют CLOSE-02, MAIN activation, native и DEV-29 открытыми. Старые отказы не заменены успешными результатами.

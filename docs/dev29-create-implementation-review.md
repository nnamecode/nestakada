# DEV-29: независимое итоговое ревью локального создания

2026-11-03, D-408/D-409. **APPROVED: CP29-001–012 в согласованной локальной области.** Рецензент tls_review не редактировал код/отчёт и не запускал SQL/Docker. Блокеров нет.

Подтверждены 211 backend PASS, 53 сохранённых HTTP-ответа для пяти типов, editor draft-save, exact replay, stale/input, CSRF и права; все 252 исходника и 20 SHA. Три raw ACL-действия связаны с одним baseline, MAIN неизменна, UNIT-права возвращены, собственная fixture очищена, журнал CLOSED, override отсутствует. Пределы доказательств и сохранённый первый FAIL описаны корректно.

| Проверенный артефакт | SHA256 |
| --- | --- |
| work/dev29-create-20261103/unit-result-ad8a0f99-0903-4d2c-b2c9-e7dadce4dcd7-1793676096205.json | 0c19398788edbc81357f317049bb85ec20a472d238aaab46f3e534f57e283557 |
| work/dev29-create-20261103/unit-collected-results.json | d22eebe2c96ea2e48cec5f2e68b7adcdec441737e00fe9d59b649459c2f46c27 |
| docs/dev29-create-results.md до итоговой отметки/процента координатора | 125c53d30e7f50155eea1b2ca4b85711687d1b95676128f4dd9569d149f91a51 |

Code-review до запуска исправил переход в actual OwnerDraft; тесты после создания проверяют check→draft→save всех пяти типов и свежий selector при replay. Следующий ограниченный review подтвердил настоящий CSRF-клиент и обязательный draft rebase:false, нулевой read-only UNIT-baseline и новый backend gate. Отдельный HTTP-review исправил audit reference uuid:<PageID> до HTTP-запуска. Прежний FAIL не удалён.

Оценка DEV-29 около 30%, этапа 8 около 31% допустима как приблизительная. Это локальное создание с выключенным по умолчанию флагом, не публичная публикация и не завершение DEV-29. Следом профиль APP↔TRUST/публикации; URL lifecycle/скрытие/удаление и полный TEST/READY впереди. Старый сайт/VPS не затронуты.

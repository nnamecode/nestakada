# REBUILD-1 media source offline harness architecture review

Дата: 2026-11-17. Review ID: `RB1-MEDIA-SOURCE-OFFLINE-HARNESS-REVIEW-001`.

Вердикт: **CHANGES_REQUESTED — P1=1, P2=0, P3=0**.

`RB1-MSRC-OFF-P1-001`: AC004 нельзя надёжно доказать AST patterns или только fake Invoke-Docker; exact extracted Invoke-MediaVerifier имеет дополнительные process/filesystem/path boundaries. D-1389 разрешает узкие fail-closed in-memory fakes/spies для всех перечисленных boundaries и требует behavioral execution production function. Remove-Item записывает intent без удаления; unexpected call FAIL. Production state algorithm не копируется. Остальные AC достаточны; one-file/no-dependency boundary сохранена.

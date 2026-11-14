# TEST-10 — предложение ограниченного feasibility-профиля

Статус D-1036, 2026-11-14: independent feasibility review — `APPROVED`, P1/P2/P3=0. `TEST09-Q009=1` оставил storage backend невыбранным и перевёл работу к следующей согласованной нефизической группе. Этот документ только инвентаризирует TEST-10; он не разрешает запуск браузеров, Foundation, форм, fault-стенда, установку старых версий/VM/сервиса или изменение acceptance-статусов.

## Точный объём

Канонический routing D-1015 содержит ровно 18 уникальных AC:

`AC-008`, `AC-013`, `AC-014`, `AC-015`, `AC-021`, `AC-022`, `AC-023`, `AC-025`, `AC-036`, `AC-056`, `AC-DTL-004`, `AC-DTL-006`, `AC-DTL-011`, `AC-DTL-018`, `AC-OPS-011`, `AC-PRO-004`, `AC-PRO-012`, `AC-MIG-003`.

Группировка не меняет oracle и нужна только для feasibility:

| Пакет | AC | Количество | Текущий blocker |
|---|---|---:|---|
| T10-A editor/version/auth UI | `AC-013`, `AC-014`, `AC-015`, `AC-021`, `AC-022`, `AC-023`, `AC-DTL-004`, `AC-DTL-006`, `AC-DTL-018` | 9 | нет утверждённого manual run manifest/stand/session fixtures |
| T10-B forms/requests | `AC-036`, `AC-DTL-011`, `AC-PRO-004` | 3 | формы/ПД default-off; legal и synthetic sink/run profile не открыты |
| T10-C gallery/source | `AC-008`, `AC-025`, `AC-MIG-003` | 3 | production/persistent import и полный ручной маршрут не разрешены |
| T10-D real browser/device matrix | `AC-056`, `AC-OPS-011` | 2 | неполная фактическая матрица 8×3, нет реальных mobile combinations |
| T10-E fallback manual | `AC-PRO-012` | 1 | DEV-26/fault stand/physical fallback остаются deferred/blocked |

## Read-only host inventory

Проверены только известные точные executable paths; приложения не открывались. Версия означает только версию найденного локального файла и не доказывает, что это `current` на дату будущей приёмки.

| Browser family | Найденный кандидат | Локальная версия | Ограничение |
|---|---|---|---|
| Chrome | да | `157.0.8103.52` | только одна локальная версия, не запускалась |
| Edge | да | `157.0.4341.57` | только одна локальная версия, не запускалась |
| Firefox | нет | — | не устанавливать ради исчезновения blocker без решения владельца |
| Яндекс Браузер | нет | — | то же |
| Opera | нет | — | то же |
| Safari | нет | — | Windows не заменяет реальные macOS/iPhone checks |
| MIUI Browser | нет | — | требуется реальное доступное устройство/комбинация |
| Samsung Internet | нет | — | требуется реальное доступное устройство/комбинация |

Из 24 строк `docs/acceptance-browser-matrix.csv` есть только два локальных current-candidate binary; предыдущие две версии Chrome/Edge и остальные 18 комбинаций отсутствуют. Все 24 строки остаются `not_run`: inventory не является browser execution.

## Закрытые правила

`T10F-001`: Django HTTP, Playwright, WebKit emulation и общий Chromium не закрывают real-browser/manual oracle.

`T10F-002`: не скачивать старые небезопасные браузеры на рабочую ОС, не создавать VM/device farm и не покупать cloud service без отдельного owner proposal.

`T10F-003`: недоступная комбинация остаётся `not_run` с limitation; её нельзя переносить в PASS по соседнему браузеру/версии.

`T10F-004`: конкретные major versions фиксируются на дату фактического запуска по проверяемому источнику; текущий inventory не назначает их по памяти.

`T10F-005`: сначала требуется exact manual run manifest: synthetic users/data, one isolated stand, case order, reset/cleanup, screenshot/text evidence без секретов/ПД и stop-on-second-equivalent-error.

`T10F-006`: T10-A не запускается до reviewed manifest и отдельного owner gate. T10-B/C/E не наследуют этот gate и остаются закрыты своими prerequisites.

`T10F-007`: browser matrix ведётся по фактическим browser/major/OS/device/date/case IDs; неизвестные значения не заполняются предположениями.

`T10F-008`: нельзя включать реальные заявки/ПД, production/VPS, старый сайт или внешние уведомления. Только синтетические данные в отдельно разрешённом стенде.

`T10F-009`: один manual package за run; FAIL/BLOCKED/cleanup ambiguity останавливает переход к следующему package.

`T10F-010`: acceptance registry не повышается автоматически. После каждого разрешённого пакета требуется per-AC evidence reconciliation.

## Рекомендованный следующий шаг

Не устанавливать недостающие браузеры и не открывать все TEST-10 пакеты. Сначала независимо проверить этот feasibility-профиль. После `APPROVED` отдельный owner gate `TEST10-Q001=1` сможет разрешить только подготовку bounded manual run plan для T10-A на доступных current Chrome/Edge candidates; он не разрешит запуск браузеров или изменение acceptance.


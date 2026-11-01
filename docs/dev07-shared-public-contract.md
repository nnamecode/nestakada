# DEV07-SH-PUB — общий публичный renderer

2026-11-01, D-356. Контракт до кода. DEV-07 около98%, этап8 около20%. Сохранены175существующих изменённых файлов с SHA256. Новых программ, ресурсов, схемы БД и квот нет; старый сайт/VPS не затрагиваются.

## Область

Основания: D-066/D-110/D-111/D-145–147/D-301; [закрытая shared схема](dev07-shared-implementation-checks.md), [приёмка общих блоков](acceptance-shared-blocks.md), [публичные контракты](acceptance-public-contracts.md). Структура и адаптивная геометрия взяты из принятого docs/design/public-light-v4-template.html; исторический public-light-v4.md сам по себе не является утверждением.

В этом срезе реализуется product renderer сохранённых current Header/Footer, гидратация UUID Asset и закрытого nav marker, доверенные CSS/JS меню и HTTP-проверяемые функции выдачи ресурсов. Production public Page/router/SEO, выбор состава главного меню, управление деревом DEV-29 и сборка реальных страниц DEV-08/09 здесь не вводятся. В основном URLConf не появляется тестовый public host.

Действующий SHI07-NAV сохраняется: renderer получает навигацию типизированным server argument от доверенного кода, не из HTML или HTTP. Не создаётся ручной реестр меню и правило «все115страниц в шапке». Тестовый host получает настоящие опубликованные synthetic Page/PRIMARY Route из существующей read projection и не объявляется production resolver. Дочерние элементы editor nav по-прежнему запрещены.

## Согласованная выдача

1. Под коротким content lock получить согласованные current Header/Footer IDs, immutable descriptors/schema/payload hashes, реальные AssetUsage/READY public variants и типизированный host/nav context. Host stamp обязан отражать влияющее содержимое/вариант будущей страницы; shared renderer не угадывает его вместо DEV-08.
2. Вне SQL прочитать/проверить private immutable HTML и media bytes, закрыто разобрать поддерживаемую header-v1/footer-v1 структуру, вставить только доверенные navigation nodes и server-assigned media URLs. Никакого Django template/Python/JS eval или превращения arbitrary HTML в SafeString без проверки. Контакты/телефон/social href остаются буквальными из снимка, не обновляются отдельным выдуманным справочником.
3. Перед выбором200/304 под свежим коротким content lock повторно получить ВСЕ влияющие данные/host stamp. Изменение означает новую попытку только с новым наблюдённым контекстом; максимум две попытки. Неизменившаяся ошибка файлов/данных не повторяется вслепую. При нестабильности/неполноте — явный unavailable/no-store, без пустого200, старого304 или подстановки draft/history.
4. ETag учитывает host stamp, пару current IDs/hashes, nav URLs/labels/order, текущие media descriptors/SHA, renderer policy и доверенные CSS/JS bytes. Публичный обычный ответ no-cache; ошибка no-store. If-None-Match проверяется после readiness, GET/HEAD/weak/list/star не возвращают неправильный304. Last-Modified не выдумывается по одному Header: полный timestamp навигации/страницы даст будущий host; этот срез не закрывает весь AT-050/AC-050 или IMS.

Линеаризация — свежая проверка перед решением200/304. Более поздний commit не превращает уже согласованное представление в смесь разных снимков; не обещается невозможная «самая новая версия после завершения любого конкурентного commit». Cleanup может удалить старый current между фазами: ошибка чтения требует новой подтверждённой metadata перед retry, без persistent GET pins/заданий или write lease на весь read.

## Ресурсы и интерактивность

Media выдаётся только для реального READY main либо legacy-public варианта, реально удерживаемого текущим общим блоком через точную связь. Source/preview/history-only/draft-only/stage-only/unready/неизвестное denied; перед conditional304 повторяется актуальная проверка прав/ссылки. Проверенный FD и SHA не подменяются другим файлом при гонке. Выбранные публичные media требуют revalidation, не долгого immutable-кэша, который отменяет проверку текущей ссылки.

Функции media/static response подключаются только в тестовый URLConf этого среза; production paths/resolver остаются DEV-08. URL builder — доверенный server callback, не editor attrs; не выдавать /manage/private/source paths. SVG из дизайн-пакета не импортируется через лазейку: сохраняются UUID bindings и растровые правила существующей медиатеки. Фактический brand/icon/font import и полное визуальное совпадение после него остаются зависимыми задачами.

CSS/JS — только фиксированные собственные файлы с версией в URL/ETag. Допускается кэш доверенных static bytes, не готового HTML. Меню работает на320/390/768/1024/desktop, с клавиатурой/aria/Escape и без горизонтального переполнения. Без JS ссылки доступны. Код не исполняет контент редактора и не ослабляет CSP ради inline script/style; host для проверки использует строгую self-policy.

Anonymous GET/HEAD не создают Session/AuthSession/receipts/jobs и не сохраняют отрисованное содержимое. Не вводить полный HTML cache, фоновые процессы, новые зависимости, SQL write-пины, повышение app/worker/ingress caps или новые бизнес-ограничения дерева.

## Исполнение

Сначала независимое ревью этого контракта и [сценариев](dev07-shared-public-checks.md), затем конкретный bounded API/QA → код → actual PG/FS/HTTP и Chromium через существующий Nginx → независимое ревью. Nginx уже проксирует location / в localhost-стенде, его конфигурацию/публикацию портов менять не требуется. Тестовые routes живут только в отдельном ROOT_URLCONF; production root остаётся прежним. Полный DEV-07/08/29/выпуск этим документом не закрывается.

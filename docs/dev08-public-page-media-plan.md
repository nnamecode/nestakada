# DEV-08G: самостоятельные публичные изображения текущей страницы

Дата: 2026-11-09
Основание: завершённый DEV-08F / D-708, существующие `page-content-v1`, READY `Asset`/`AssetFile`, `AssetUsage(current_page)` и проверенный `/public-media/<FileUUID>/`.

## Цель и граница

Показать без нового media/storage слоя самостоятельный `layout.kind=image` как body-блок в его точном сохранённом месте. Он использует только server-selected публичную производную существующего READY Asset и прежний public-media endpoint с явным контекстом Page/slot.

`main_image` в этом срезе не рисуется: по D-257 и утверждённым внутренним страницам оно участвует в page-kind hero с текстовой панелью, а универсальная позиция не задана. Его композиция выносится в отдельный presentation-срез. `preview_image` предназначено для будущих карточек/превью. Protected marker внутри text и generic `protected_ref` остаются closed `503`; DEV-08G не создаёт универсальный component renderer и не преобразует carrier эвристически.

## Приёмочные сценарии

- `PIMG-001`: standalone image следует точному порядку layout относительно text/price. `main_image`/`preview_image` не получают выдуманного универсального положения и самостоятельно не выводятся.
- `PIMG-002`: в HTML попадает только локальный server-generated URL `/public-media/<FileUUID>/?page=<PageUUID>&slot=embedded:<ImageUUID>`; storage key, source URL, AssetUUID и private-source metadata отсутствуют. Порядок query canonical и создаётся только сервером.
- `PIMG-003`: alt экранируется как текст; alignment берётся только из closed `left|center|right`; nullable positive width/height становятся только числовыми HTML attributes, CSS удерживает изображение в контейнере.
- `PIMG-004`: разрешается только опубликованная current Page, точный `embedded:<ImageUUID>` slot и совпадающий `AssetUsage(kind=current_page, consumer_id=PageUUID, slot, asset_id)`; image ID обязан быть достижим ровно из standalone `layout.kind=image`. Guessed/unreferenced/old-version/unpublished, `main_image`, `preview_image`, protected-only и orphan embedded отказываются. Тот же файл на другой опубликованной Page доступен только с её собственными правильными page+slot, но не в контексте первой Page.
- `PIMG-005`: Asset обязан быть READY и иметь одну подходящую публичную производную: `MAIN` для нового изображения либо единственный `LEGACY_PUBLIC` для побайтного legacy original. `PRIVATE_SOURCE`, `PREVIEW`, ambiguous/missing variant закрываются.
- `PIMG-006`: query отсутствует только у прежнего shared-block media consumer; Page media принимает ровно по одному canonical `page` и `slot`, без дублей/лишних keys. GET/HEAD проверяет тот же immutable file descriptor и фактические bytes/MIME; JPEG/PNG допустимы только для `LEGACY_PUBLIC`, WebP — для `MAIN`. Ответ имеет `nosniff`, local ETag и no-cache; неизвестное/несвязанное даёт закрытый404, повреждение/race —503. Unsafe method закрывается framework CSRF как403 либо view как405 до media capture/файлового чтения и без мутации; CSRF не ослаблять ради унификации кода.
- `PIMG-007`: существующий двухпопыточный composition расширяется typed host-media tuple: внутри короткой DB transaction capture полного Page/payload/standalone slot/current_page usage/public file descriptor; затем вне transaction `open_verified` + MIME каждого page FD; затем новая короткая DB recapture и сравнение полного host stamp. Drift revision/publication/usage/slot/file descriptor вызывает один повтор, затем503. Только совпавший финальный capture оставляет frozen slot→FileUUID mapping для body и composite ETag; FS I/O под content lock запрещён. Missing/corrupt physical image закрывает весь page503 до template/response, без canary/UUID/частичного HTML.
- `PIMG-008`: protected text, `protected_ref` и неизвестный kind сохраняют прежний whole-page503 без canary/UUID; DEV-08G не ослабляет rich-HTML equality guard и не доверяет raw `src`/client URL.
- `PIMG-009`: ALIAS, hidden blank200, redirects/unknown, Header/Footer media, ETag/304/HEAD, sessionless/no-write и существующие text/price сценарии не регрессируют.

## Рентабельная реализация

Расширить существующий public-media consumer resolver текущей опубликованной Page вместо второго endpoint/streamer. Shared media сохраняет прежний URL без query; page image использует обязательные exact page+slot query. `PublicSharedHost` получает bounded mapping только достижимых standalone slots → public file descriptor и включает его в текущий coherent stamp. Минимальное typed расширение `HostContext` передаёт unique page file descriptors в уже существующий capture→FS verify→recapture цикл `render_shared`; отдельная state machine не создаётся. Pure body projection получает только frozen mapping и формирует typed image block; файловых запросов из template нет.

Новых моделей, миграций, фоновых задач, cache, worker, upload policy, URL namespace или зависимости не добавлять. Gallery listing/modal, preview cards, protected carrier hydration, SEO/canonical, migration данных, HTML fallback и production остаются отдельными этапами.

## Статус D-711

Первый plan review вернул два P1 и P2 до кода. D-710 устраняет их: page+slot делает contextual URL однозначным; standalone reachability исключает preview/protected/orphan consumers; физическая проверка включена в точный capture→verify outside transaction→recapture алгоритм; неоднозначный `main_image` удалён из scope. Product code ещё не начат. Требуется repeat independent plan review.

Repeat independent plan review: `APPROVED`, P1/P2/P3 нет. D-711 допускает реализацию только `PIMG-001–009` в указанной границе.

## Статус D-713 / DEV-08G-Q001

Code review вернул CHANGES_REQUIRED. Уже внесены однозначные исправления: exact MAIN→WebP и LEGACY_PUBLIC→JPEG/PNG с binding к `Asset.is_legacy`; media recapture disappearance теперь retry→503, initial invalid остаётся404; malformed contextual UUID даёт404 без маскировки DB failure; N+1 заменён двумя пакетными запросами.

Остаётся согласовать safety ceiling публичного renderer: одновременно ограничить число standalone layout image slots и unique физических файлов на одной Page. Без ceiling анонимный GET может вызвать неограниченное число SHA/open. Рекомендация `64/64`: достаточно обычным внутренним страницам и пагинируемым альбомам, но ограничивает худший запрос; превышение закрывается503 до файлового чтения. Альтернативы: строгие `32/32` либо более тяжёлые `128/128`. До ответа product code и новые tests сохранены, повторные запуски не выполнять.

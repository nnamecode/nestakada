# Независимое ревью плана публичных шаблонов/CSS

Дата: 2026-11-16. Reviewed: `docs/public-template-css-remediation-plan.md` D-1214.

Вердикт: **CHANGES_REQUESTED — P1=2, P2=5, P3=0**. Product code не проверялся и не менялся.

## P1

1. План требует typed actions/reviews/catalog/news и одновременно запрещает HTML-shape inference, но current version schema имеет structured profiles только для home/contacts. Actions/reviews импортированы как canonical `main_text` HTML. Нужно выбрать и согласовать источник: закрытая grammar/parser с editor contract либо versioned structured profiles с полными save/version/restore/editor semantics.
2. Approved `works/closing/card images` не имеют определённого coherent source/media contract для внутренних страниц. Current host захватывает standalone media только текущей страницы, gallery files — только gallery request. Нужна slot-readiness matrix, точный versioned source, capture stamp, contextual URL и deletion/dependency rule; брать файлы напрямую из deliverables нельзя.

## P2

1. `Page.Kind` mapping не равен 115 transport outcomes: `?page=1` redirect выполняется до render, `?page=2` — validated subvariant gallery. Сначала нужен outcome `redirect/blank/render`, затем presentation mapping.
2. Baseline должен быть ordered structural fingerprint, а не только text digest/set: block order, link label+href+internal/external, media slot+asset/file+alt+dimensions+position.
3. D-1210 exact21 home media должен быть prerequisite до baseline/architecture patch, а не частью более позднего family этапа.
4. Visual gate должен назвать исполнимый browser/geometry method, evidence format и anti-loop rule; screenshot/media-query не подменяют numeric overflow.
5. CSS transport должен выбрать один bounded вариант и зафиксировать GET/HEAD/405, MIME, cache, `nosniff`, unknown404 и отсутствие path-derived file access.

После исправлений требуется repeat independent review.

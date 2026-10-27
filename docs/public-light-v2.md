# Светлая главная — вторая концепция

**Отклонена владельцем, D-078.** Причина — типичная шаблонная композиция и недостаточный дизайнерский уровень. Не является согласованной основой. Претензия не сводится к индивидуальному вкусу владельца.

2026-10-27. D-076, UX-03. Первые три раскладки отвергнуты владельцем; новая концепция ещё не утверждена. Предварительно выбрано светлое направление.

D-077: владелец добавил будущий блок заявки на запись на главной. Его дизайн и содержание прорабатываются после утверждения главной; в этой итерации формы пока нет. Юридические/процессные заметки — docs/booking-form-notes.md.

Композиция: светлый фон, крупное название техцентра, автомобильная иллюстрация на весь первый экран, оранжевая основная кнопка. Навигация и телефон компактно собраны в шапке. Услуги оформлены как выделенное кузовное направление и набор крупных строк, без прежней повторяющейся сетки карточек. Существующие названия, слоган и контактные данные сохранены. Статистику, рейтинги, отзывы и новые обещания не придумывали; форм/записи нет. Навигационные пути услуг остаются прежними.

Иллюстрация изображает условный автомобиль и сервисный бокс; это не документальная фотография настоящих помещений/оборудования Эстакады. Создана встроенным image_gen, не CLI/API. Сохранённый оригинал: `T:/nestakada/media/design-concepts/public-light-hero-v2.png`. Веб-копия для предпросмотра: `T:/nestakada/media/design-concepts/public-light-hero-v2-web.jpg` (JPEG, качество 88, исходное разрешение). Оригинал PNG сохранён отдельно. Собственные фотографии галереи не изменялись.

Шаблон: docs/design/public-light-v2-template.html. Сборка локального предпросмотра: scripts/prepare-public-light-v2.py → work/public-light-v2.html. Медиа остаются вне Git в media/, код макета хранится отдельно. Старые публичные варианты сохраняются только как история, не утверждённый дизайн.

Проверки в Edge: изображение/логотип загружаются; на 1024/736/390/320 нет горизонтального переполнения; переходы к кузовному разделу и покраске, мобильное меню и контакты работают. На 320 центры логотипа/телефона/меню совпадают, шапка занимает 66 px. Ошибок JavaScript нет. Десктопный и мобильный снимки просмотрены. Внутренние страницы здесь условные; полный перенос старых текстов и новая проработка остальных страниц ещё впереди.

## Промпт изображения (финальный)

Use case: photorealistic-natural. Asset type: wide website hero photograph for a Russian independent car repair workshop, not a dealership. Create an original premium editorial automotive photograph, landscape approximately 16:9. A clean graphite silver unbranded modern car seen front three-quarter, parked naturally on a light concrete floor in an airy bright workshop with off-white walls, tall windows, a few subtle professional workshop fixtures in the distance. The car fills the RIGHT two-thirds of the image and sits toward the bottom; the LEFT third is clean bright off-white negative space that blends softly into the workshop for overlaid dark website copy. Medium-low camera angle, confident diagonal perspective, crisp believable headlights and wheels, beautifully controlled natural window light, rich graphite metal reflections, realistic understated industrial atmosphere, muted warm grey palette. Professional automotive magazine photography, visually striking but credible. No people, no showroom sales decorations, no brand emblems, no license plate lettering, no signs, no words, no watermark, no illustration, no text. Do not add a logo or website UI. This is a conceptual illustration, not a documentary view of the real Estakada premises.

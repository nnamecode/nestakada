import hashlib
from uuid import uuid4

from django.db import models
from django.test import TestCase, override_settings

from content.models import Page, Route
from content.public_gallery import ALBUM_TARGETS, ROOT_TARGET
from media_library.models import Asset, AssetUsage, MediaFolder
from page_versions import schema
from page_versions.models import PageContentState, PageRevision
from shared_content.models import SharedBlock, SharedRevision

from .contracts import ContractError
from .source import capture, capture_targets


def raw(model):
    return models.QuerySet(model=model, using='default')


@override_settings(PUBLIC_ORIGIN='http://localhost:8767',
                   SEO_ROBOTS_PROFILE='deny-all')
class HtmlReserveSourceTests(TestCase):
    def setUp(self):
        super().setUp()
        for kind in ('header', 'footer'):
            block = SharedBlock.objects.create(kind=kind)
            body = '<%s>safe</%s>' % (kind, kind)
            revision = SharedRevision.objects.create(
                block=block, sequence=1, schema_version=kind + '-v1',
                html=body, payload_hash=hashlib.sha256(body.encode()).hexdigest(),
                author_id=1)
            raw(SharedBlock).filter(pk=block.pk).update(
                current_revision=revision, generation=1)

    def page(self, name, target, *, published=True, kind=Page.Kind.ARTICLE,
             position=0, parent=None):
        page = Page.objects.create(
            name=name, kind=kind, position=position, parent=parent,
            is_published=published)
        route = Route.objects.create(
            page=page, kind=Route.Kind.PRIMARY, target=target,
            is_legacy='?' in target)
        payload = schema.snapshot_v1(kind, h1=name, title=name).data()
        revision = PageRevision.objects.create(
            page=page, sequence=1, schema_version=schema.SCHEMA,
            payload=payload, payload_hash=schema.digest(payload),
            kind=PageRevision.Kind.INITIAL, author_id=1)
        PageContentState.objects.create(
            page=page, current_revision=revision, sequence=1)
        return page, route, revision

    def test_exact_route_status_location_query_and_hidden_contract(self):
        page, primary, _revision = self.page('Main', '/main/')
        alias = Route.objects.create(
            page=page, kind=Route.Kind.ALIAS,
            target='/legacy/?utm=kept', is_legacy=True)
        redirect = Route.objects.create(
            page=page, kind=Route.Kind.REDIRECT, target='/old/')
        hidden, hidden_primary, _revision = self.page(
            'Hidden', '/hidden/', published=False, position=1)
        system = Route.objects.create(
            page=None, kind=Route.Kind.SYSTEM, target='/system/')

        specs = {item.target: item for item in capture_targets()}
        self.assertEqual(specs[primary.target].status, 200)
        self.assertEqual(specs[alias.target].status, 200)
        self.assertEqual(specs[hidden_primary.target].status, 200)
        self.assertEqual(specs[redirect.target].status, 301)
        self.assertEqual(specs[redirect.target].location, primary.target)
        self.assertNotIn(system.target, specs)
        self.assertNotIn('/missing/', specs)
        self.assertEqual(hidden.is_published, False)

    def test_gallery_generated_set_preserves_existing_renderer_contract(self):
        root, _root_route, _revision = self.page(
            'Gallery', ROOT_TARGET, kind=Page.Kind.GALLERY)
        published = []
        for position, target in enumerate(ALBUM_TARGETS):
            page, _route, _revision = self.page(
                'Album ' + str(position), target, kind=Page.Kind.ALBUM,
                position=position, parent=root, published=position != 3)
            if page.is_published:
                published.append(target)
        specs = {item.target: item for item in capture_targets()}
        self.assertEqual(specs[ROOT_TARGET + '?page=1'].status, 302)
        self.assertEqual(specs[ROOT_TARGET + '?page=1'].location, ROOT_TARGET)
        for target in published:
            slug = target.removeprefix(ROOT_TARGET)
            self.assertIn(ROOT_TARGET + '?album=' + slug, specs)
        hidden_slug = ALBUM_TARGETS[3].removeprefix(ROOT_TARGET)
        self.assertNotIn(ROOT_TARGET + '?album=' + hidden_slug, specs)
        self.assertNotIn(ROOT_TARGET + '?page=1&album=' + hidden_slug, specs)

    def test_source_stamp_changes_for_public_data_but_not_retained_usage(self):
        page, _route, revision = self.page('Stamped', '/stamped/')
        first = capture()
        folder = MediaFolder.objects.create(path='html-reserve/test')
        asset_id = uuid4()
        raw(Asset).bulk_create([Asset(
            id=asset_id, folder=folder, status=Asset.Status.READY,
            provenance='HTML reserve test')])
        AssetUsage.objects.create(
            asset_id=asset_id, kind=AssetUsage.Kind.RETAINED_HTML,
            consumer_id=uuid4(), slot='asset:' + str(asset_id))
        self.assertEqual(capture().stamp, first.stamp)

        payload = dict(revision.payload)
        payload['title'] = 'Changed title'
        changed = PageRevision.objects.create(
            page=page, sequence=2, schema_version=schema.SCHEMA,
            payload=payload, payload_hash=schema.digest(payload),
            kind=PageRevision.Kind.AUTOMATIC, author_id=1)
        raw(PageContentState).filter(page=page).update(
            current_revision=changed, sequence=2)
        self.assertNotEqual(capture().stamp, first.stamp)

    def test_page_name_aba_changes_source_stamp_via_postgresql_row_version(self):
        page, _route, _revision = self.page('ABA A', '/aba/')
        first = capture()
        raw(Page).filter(pk=page.pk).update(name='ABA B')
        middle = capture()
        raw(Page).filter(pk=page.pk).update(name='ABA A')
        final = capture()
        self.assertNotEqual(middle.stamp, first.stamp)
        self.assertNotEqual(final.stamp, first.stamp)
        self.assertEqual(final.descriptor['pages'][0][4], 'ABA A')

    def test_route_cap_fails_closed_without_truncation(self):
        self.page('One', '/one/')
        self.page('Two', '/two/', position=1)
        with self.settings(HTML_RESERVE_MAX_ROUTES=1):
            with self.assertRaisesRegex(ContractError, 'SOURCE_ROUTE_LIMIT'):
                capture_targets()

    def test_source_rejects_payload_changed_behind_stored_hash(self):
        _page, _route, revision = self.page('Coherent', '/coherent/')
        payload = dict(revision.payload)
        payload['title'] = 'Changed without digest'
        raw(PageRevision).filter(pk=revision.pk).update(payload=payload)
        with self.assertRaisesRegex(ContractError,
                                    'SOURCE_PAGE_PAYLOAD_INCOHERENT'):
            capture()

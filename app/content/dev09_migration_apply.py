"""Exact UNIT-only application of the reviewed DEV-09B articles package."""
from html import escape
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from uuid import UUID, uuid5

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.db.models import Q

from accounts.models import PageGrant, UserProfile
from accounts.services import lock_auth
from audit.constants import Category, Level, Result, Source
from audit.models import AuditEvent
from audit.services import record_event
from media_library import services as media_services
from media_library.models import Asset, AssetFile, AssetUsage, MediaFolder
from media_library.storage import MediaStorage
from page_editor.clean import restricted_clean
from page_versions import engine, schema
from page_versions.creation import initial_snapshot
from page_versions.models import (
    IdentityReservation, OperationReceipt, OwnerDraft, PageContentState,
    PageRevision, RestoreStage, RevisionMetadata, RevisionProtection,
    VersionBasePin,
)

from .models import Page, Route, lock_content


PACKAGE_SHA256 = '2936561288256d42968363afe90147678aa6fc88bbdff9faf21fde1c2d986639'
MAP_SHA256 = 'c1d542d0761ffbdb9fc58c9227fc94144515ab18c3155952a93dc6fb4d1bbad8'
RTE_SHA256 = 'c3a8a395fb4ed55fef6027a58014ce5decaadda7c559870bf06247c2fbeb79bc'
PACKAGE_NAME = 'dev09b_articles_slice.json'
SERVICES_PACKAGE_NAME = 'dev09e_services_catalog.json'
SERVICES_PACKAGE_SHA256 = 'beffdfdbacc6a24a71c68ee692f03be262f67745b8425e1ce9b204b8d15ca9e9'
SERVICES_GROUPS_SHA256 = '5e4f61aeba6687165cc6a49e4a5fb2383f1f5d4b1f4ac412965096dbdd82eb7e'
SERVICES_SOURCE_SHA256 = 'e61fbaffbfea280abf1c9d3c1017174b8c22323bcc149c88e8bb013cbf9e1da7'
SERVICES_SOURCE_PATH = 'work/site-audit/crawl/0184ec81ddcc19cff2bd.html'
SERVICES_GROUP_COUNTS = (12, 10, 18, 11, 7)
SERVICE_ROOTS_PACKAGE_NAME = 'dev09g_service_roots.json'
SERVICE_ROOTS_PACKAGE_SHA256 = '956c35fb5697acb23b039a980d1915228bd1100f1884ebece3fcd909ace365db'
SERVICE_ROOTS_TILES_SHA256 = 'cdcaa70097a0359671d9d76d765997b22e62c48ed7e823d650167e92fe25f936'
SERVICE_DETAILS_PACKAGE_NAME = 'dev09h_service_details.json'
SERVICE_DETAILS_PACKAGE_SHA256 = '439dea21aa4257e934e0781faec982bb05157d5a734171ced58086df4e8bd52a'
SERVICE_DETAILS_PAGES_SHA256 = '1d22ab1cd4d71116fcf9c3b25d8cdaf05f0f9e1a17612a3341533be7ea39b87d'
PLANNED_PACKAGE_NAME = 'dev09i_planned_maintenance.json'
PLANNED_PACKAGE_SHA256 = 'fa0e85ba9640ffa45916e810bece20e949698b3dbe82f9ead99750210b98a5cf'
PLANNED_PAGES_SHA256 = '91e02eabc9b19944c002cf85f4e4cd3dcc1a0e395f7bb0988c856cc451c5793c'
LEADING_PRICE_PACKAGE_NAME = 'dev09j_leading_price_details.json'
LEADING_PRICE_PACKAGE_SHA256 = 'e091047ae5272fa9834d828d5ed73e1fbc914a41faa07e4367b9787ad0a8934d'
LEADING_PRICE_PAGES_SHA256 = '5fd96cbbbe6adabd96f4a02ccaab1ed5493e1e25a66dc825dbf5ccfdb77ff4ba'
LEADING_PRICE_ROW_COUNTS = (11, 8, 21, 5, 1)
DIAGNOSTICS_PACKAGE_NAME = 'dev09k_diagnostics_branch.json'
DIAGNOSTICS_PACKAGE_SHA256 = '9980c60a1a2ee354ef156c7f9695cfc76ec051f798dfe3610a95f3e29c473e67'
DIAGNOSTICS_PAGES_SHA256 = '21e3965116ada52d91054c0621f220d74545a47bf9502ac2d8cb012bd318266a'
COMBINED_PACKAGE_NAME = 'dev09m_combined_services.json'
COMBINED_PACKAGE_SHA256 = '3fb682d6a092d78439fa45b541668554d793490b41eb89d311359738053f8e01'
COMBINED_PAGES_SHA256 = '0ee0924d71cea90e81ab2596b7b4df6df282ebb6f81998d8b55ff54eea5d8c82'
COMBINED_ROUTES_SHA256 = 'cc5d3255f01e40098a90fd3a48ff8efe2d4f117026b3c55cdaef16fbe42b6433'
COMBINED_MANIFEST_SHA256 = '8e89d9db34b3b3e1e34574c933ce12a3ac37d7ebd8a3b68a1d6c7591233c2cfa'
COMBINED_INFOGRAPHIC_PACKAGE_NAME = 'dev09m_infographic_map019.json'
COMBINED_INFOGRAPHIC_PACKAGE_SHA256 = 'fe083d206a72a3850bb30a554e57d375eba3338aacd87842c6c17f99a0f34954'
COMBINED_INFOGRAPHIC_PROVENANCE = 'DEV09M owner-approved MAP-019 infographic'
SERVICE_ROOTS_EXPECTED = (
    ('729b10a3-709e-41c0-a71f-0d376a2b8586', 'MAP-012',
     '/services/remont/', 2, 'Ремонт', 'Ремонт',
     'Ремонт | Автосервис «Эстакада»',
     'work/site-audit/crawl/ca4ab73dc69f37051a6f.html',
     '249c910d6e6340f652587f14c3cdea20c5c7befe21adf9f42719f16e7bd289a5',
     'work/remont.html',
     'cf7352e8dd14cae5059b3bf583586f32266882b47a44eff3d5119269dd4564c3', 17),
    ('ec990108-25c4-4ae9-961f-13487e63e938', 'MAP-014',
     '/services/drugie-uslugi/', 4, 'Другие Услуги', 'Другие Услуги',
     'Другие Услуги | Автосервис «Эстакада»',
     'work/site-audit/crawl/32ee0e4b4942a75ffa9e.html',
     '25a3204a9ddb323e93b37b60887d78c6680d3978d8026cb7c8818b1ad4eeb78d',
     'work/drugie-uslugi.html',
     '50c2c6c412d9ff93c7581816d7323eb541dc00c0b0878cca50ccadbc7446af1d', 5),
)
SERVICES_PAGE = {
    'page_id': 'f39af842-05a7-4101-af9a-2fc320d457d0',
    'map_id': 'MAP-002', 'url': '/services/',
    'kind': 'services_master_catalog',
    'parent_id': 'e80c3de1-feea-4847-b550-325a825ffc0e',
    'position': 1, 'name': 'Услуги и цены',
    'h1': 'Услуги и цены автосервиса "Эстакада"',
    'title': 'Услуги | Автосервис «Эстакада»',
    'description': '', 'is_published': False,
}
PARENT_DESCRIPTOR = {
    'page_id': 'e80c3de1-feea-4847-b550-325a825ffc0e',
    'url': '/', 'kind': 'home', 'parent_id': None, 'position': 0,
    'name': 'Главная',
}
PAGE_KEYS = {
    'page_id', 'map_id', 'url', 'kind', 'parent_id', 'position', 'name',
    'h1', 'title', 'description', 'is_published', 'content_state', 'source',
    'blocks',
}
EXPECTED = (
    ("MAP-001", "e80c3de1-feea-4847-b550-325a825ffc0e", "/", "home", None, 0, "Главная", "deferred", "work/site-audit/crawl/59657143c68dec7e2e68.html", "b4999dfa62959ae390eb45162dcf62257dc228e52cd2bfe1e9702f49fc1c0b97", ()),
    ("MAP-006", "5e6ab812-950c-46f6-875e-6205a9446cc8", "/articles/", "articles_catalog", "e80c3de1-feea-4847-b550-325a825ffc0e", 4, "Статьи", "deferred", "work/site-audit/crawl/7d77056de27a9d3d4178.html", "364555e482c73244c9c8e887a7b4e9eabcda1f63627c3ef1736eade75bc455ed", ()),
    ("MAP-031", "2d53411f-cc5e-4fd7-9cc7-8ebee6bbd435", "/articles/zamena-masla-v-dvigatele", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 0, "Замена масла в двигателе", "source_text_complete_media_deferred", "work/site-audit/crawl/14576e552fecad65ae73.html", "34e865f3d936e29d84a69c2a97002d532ee2ac359de5a4a439214b9b34b0a6bc", ("p1", "p1", "p1")),
    ("MAP-037", "f22de959-c6c6-4ff8-8008-a9bf835145fe", "/articles/zamena-texnicheskix-zhidkostej", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 1, "Замена технических жидкостей", "source_text_complete_media_deferred", "work/site-audit/crawl/f6c171267a4a1a59417d.html", "f79707f5875c6d64ffd14f4cde85bd12b7e8747bceac2180ebafdc5da90e3927", ("p1", "p1", "p1", "p1", "p1")),
    ("MAP-043", "7054b068-2221-41df-a292-bc30aeb9b119", "/articles/zamena-filtrov-avtomobilya", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 2, "Замена фильтров автомобиля", "source_text_complete_media_deferred", "work/site-audit/crawl/78c4fe8f69621612ab29.html", "8ea9baadcce5f7e43c69557543eb5c00d56632a28ca358b3b4da2c857a0de693", ("p1", "p1", "p1", "p1")),
    ("MAP-048", "5120fe58-109c-48fa-aa11-b34580449aaf", "/articles/kompyuternaya-diagnostika-avtomobilya", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 3, "Компьютерная диагностика автомобиля", "source_text_complete_media_deferred", "work/site-audit/crawl/340a8c32c65d034518b9.html", "a7e11f47d0c44b93810d8a4132315e31c8d7c8078b763b71648bdea20082e09d", ("p1", "p1", "p1", "p1")),
    ("MAP-053", "bf7482e2-016b-481d-b319-a0df7a47d177", "/articles/remen-grm", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 4, "Ремень ГРМ", "source_text_complete_media_deferred", "work/site-audit/crawl/5e25c0d654f83ac6d720.html", "148bbf09861f9c2035e9a26c93f0a0e28ca8830a4fb72e860c6dee246710c147", ("p1", "p1", "p1")),
    ("MAP-057", "010c6bdd-a610-45f1-af6b-52f55a569ddf", "/articles/remont-akpp", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 5, "Ремонт АКПП", "source_text_complete_media_deferred", "work/site-audit/crawl/66ec46d6386f2fd85a68.html", "498a942964d1270b5ab7fe3b69d20bc652588f05014ca96aa29ed192cc02b5e0", ("p1", "p1", "p1", "p1", "p1", "p1", "p1", "p1", "p1")),
    ("MAP-065", "5929545c-b932-4dbc-8ec6-9806f5a9007a", "/articles/remont-dvigatelya-avtomobilya", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 6, "Ремонт двигателя автомобиля", "source_text_complete_media_deferred", "work/site-audit/crawl/aff237c9c93859f8aecb.html", "69eb70cf2fb43fb3442cac2197e8f03dfea93ef84651e17cf51ec1d0a659f7a6", ("p1", "p1", "p1", "u4", "p1")),
    ("MAP-071", "d9e46de1-297b-4c43-969b-6ba579ffe07b", "/articles/remont-i-diagnostika-avtoelektriki", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 7, "Ремонт и диагностика автоэлектрики", "source_text_complete_media_deferred", "work/site-audit/crawl/87b016281c0189929789.html", "3ca05a66dcd63647322e3171e2384eb124e593acf21801f377233a05891cbc5f", ("p1", "p1", "u6", "p1")),
    ("MAP-072", "83763734-e473-41e4-a878-bc06ff6bbd99", "/articles/remont-mkpp", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 8, "Ремонт МКПП", "source_text_complete_media_deferred", "work/site-audit/crawl/ae236ec43daccf2bdb79.html", "6b2918d65a3268fb16eae730783634f47d116ebd25880eeef0a47e66639ba9e5", ("p1", "p1", "p1", "p1", "p1", "p1", "p1")),
    ("MAP-077", "23e720a7-dbad-482a-b9c8-6a2912ae0b48", "/articles/polirovka-far", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 9, "Полировка фар", "source_text_complete_media_deferred", "work/site-audit/crawl/9d71d73299ccfa8e7bee.html", "b2e37576a02003f499a76450c0ea692f766f36f2a74daf7cb6ea08b8f5c8d9d0", ("p1", "p1", "p1", "p1")),
    ("MAP-082", "4dbe3ebe-24ea-4b40-90c7-8354dc33b2fc", "/articles/regulirovka-razval-sxozhdeniya-koles", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 10, "Регулировка развал-схождения колес", "source_text_complete_media_deferred", "work/site-audit/crawl/e6d28289278e8f481833.html", "d84833d87c80b709c52a549a07767a071ff65e30f6d6d4dd259e4c6779ed728c", ("p1", "p1", "p1")),
    ("MAP-087", "d8d10b26-f3f5-46ba-9d32-0984b2d40a9f", "/articles/kachestvennyie-uslugi-shinomontazha", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 11, "Качественные услуги шиномонтажа", "source_text_complete_media_deferred", "work/site-audit/crawl/00600f366618519d6337.html", "f5f8a38fbde524b484b79b74a057b9a6a68f27434e4612741df36f52a96edcab", ("p1", "p1", "p1", "p1", "p1", "p1", "p1", "p1")),
    ("MAP-093", "d4a63713-7f22-41f3-8769-edaa91b8e457", "/articles/sistema-oxlazhdeniya-dvigatelya", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 12, "Система охлаждения двигателя", "source_text_complete_media_deferred", "work/site-audit/crawl/5b2446a839b3c70d5dcf.html", "bcab530a05f47d5be59195bbd7599b802afda04d6c6f607dcf83df5ccf45ed2b", ("p1", "p1", "p1", "u6")),
    ("MAP-100", "f07e4a08-9746-4b1e-81c8-74a325b4230c", "/articles/ochistka-kondiczionera", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 13, "Очистка кондиционера", "source_text_complete_media_deferred", "work/site-audit/crawl/3e5b979e2112059af1d1.html", "22ff446ce6287b6e3d234d4750fd1f3aca0ade3d841f0a841cf7d3dd04abd992", ("p1", "p1", "p1")),
    ("MAP-103", "545aa532-47e0-4fbb-864a-96e5db71482d", "/articles/kuzovnoj-remont-avtomobilya", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 14, "Кузовной ремонт автомобиля", "source_text_complete_media_deferred", "work/site-audit/crawl/3b78a41b670c3f1fb7d2.html", "b1d9ff6c721f19441041bb05c3cee6bc49ade12cafced2eb0658cad544f9f631", ("p4",)),
    ("MAP-105", "1b9bc2ee-ad4a-4e05-9b45-53c7e738755d", "/articles/povrezhdenie-lakokrasochnogo-pokryitiya", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 15, "Повреждение лакокрасочного покрытия", "source_text_complete_media_deferred", "work/site-audit/crawl/f478027d9d05996d409e.html", "b8d8161a6c3b2d0bdfa4aacd704967e9e40b6e968671bdef05e7bd7d4a2fd672", ("p1", "p1", "p1", "p1")),
    ("MAP-108", "1023fe6c-6843-4032-9481-a7106cbbdf71", "/articles/pokraska-bampera", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 16, "Покраска бампера", "source_text_complete_media_deferred", "work/site-audit/crawl/7e52c2b8f35f4aa7ce91.html", "abeff8d042e17dbf6234be5cc2492672f6e571608b4af95a5005956896efa7cc", ("p1", "p1", "p1")),
    ("MAP-110", "9de01837-f7b1-42f2-bcb1-a2832730e6fc", "/articles/kompleksnaya-shumoizolyacziya", "article", "5e6ab812-950c-46f6-875e-6205a9446cc8", 17, "Комплексная шумоизоляция", "source_text_complete_media_deferred", "work/site-audit/crawl/a1934f18d933a8e5a5e1.html", "4a8628d4833152fbe8dcc6f0e944ae0512dd8ed7b161a42e140409f1f2fec3ab", ("p1", "p1")),
)


def _fault(code):
    raise ValidationError(code)


def _enabled():
    database = connection.settings_dict
    if (getattr(settings, 'ENVIRONMENT', None) != 'test'
            or getattr(settings, 'DEV09_MIGRATION_APPLY_ENABLED', False) is not True
            or database.get('ENGINE') != 'django.db.backends.postgresql'
            or database.get('NAME') != 'estakada_foundation_unit'
            or database.get('USER') != 'app_migrator'):
        _fault('MIGRATION_APPLY_DISABLED')


def _pairs(rows):
    result = {}
    for key, value in rows:
        if key in result:
            _fault('MIGRATION_PACKAGE_INVALID')
        result[key] = value
    return result


def _read_package():
    package = Path(__file__).resolve().with_name(PACKAGE_NAME)
    if package.name != PACKAGE_NAME or package.parent != Path(__file__).resolve().parent:
        _fault('MIGRATION_PACKAGE_INVALID')
    nofollow = getattr(os, 'O_NOFOLLOW', None)
    if nofollow is None:
        _fault('MIGRATION_PACKAGE_UNSUPPORTED')
    descriptor = None
    try:
        descriptor = os.open(package, os.O_RDONLY | nofollow)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or not 1 <= info.st_size <= 65536:
            _fault('MIGRATION_PACKAGE_INVALID')
        if Path(os.path.realpath(package)) != package:
            _fault('MIGRATION_PACKAGE_INVALID')
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            content = stream.read(65537)
    except ValidationError:
        raise
    except (OSError, ValueError):
        _fault('MIGRATION_PACKAGE_INVALID')
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (len(content) > 65536 or b'\r' in content
            or hashlib.sha256(content).hexdigest() != PACKAGE_SHA256):
        _fault('MIGRATION_PACKAGE_INVALID')
    try:
        value = json.loads(content.decode('utf-8', errors='strict'),
                           object_pairs_hook=_pairs)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fault('MIGRATION_PACKAGE_INVALID')
    return _validate_package(value)


def _read_services_package():
    package = Path(__file__).resolve().with_name(SERVICES_PACKAGE_NAME)
    if (package.name != SERVICES_PACKAGE_NAME
            or package.parent != Path(__file__).resolve().parent):
        _fault('MIGRATION_PACKAGE_INVALID')
    nofollow = getattr(os, 'O_NOFOLLOW', None)
    if nofollow is None:
        _fault('MIGRATION_PACKAGE_UNSUPPORTED')
    descriptor = None
    try:
        descriptor = os.open(package, os.O_RDONLY | nofollow)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or not 1 <= info.st_size <= 20480:
            _fault('MIGRATION_PACKAGE_INVALID')
        if Path(os.path.realpath(package)) != package:
            _fault('MIGRATION_PACKAGE_INVALID')
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            content = stream.read(20481)
    except ValidationError:
        raise
    except (OSError, ValueError):
        _fault('MIGRATION_PACKAGE_INVALID')
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (len(content) > 20480 or b'\r' in content
            or hashlib.sha256(content).hexdigest() != SERVICES_PACKAGE_SHA256):
        _fault('MIGRATION_PACKAGE_INVALID')
    try:
        value = json.loads(content.decode('utf-8', errors='strict'),
                           object_pairs_hook=_pairs)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fault('MIGRATION_PACKAGE_INVALID')
    return _validate_services_package(value)


def _read_service_roots_package():
    package = Path(__file__).resolve().with_name(SERVICE_ROOTS_PACKAGE_NAME)
    if (package.name != SERVICE_ROOTS_PACKAGE_NAME
            or package.parent != Path(__file__).resolve().parent):
        _fault('MIGRATION_PACKAGE_INVALID')
    nofollow = getattr(os, 'O_NOFOLLOW', None)
    if nofollow is None:
        _fault('MIGRATION_PACKAGE_UNSUPPORTED')
    descriptor = None
    try:
        descriptor = os.open(package, os.O_RDONLY | nofollow)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or not 1 <= info.st_size <= 16384:
            _fault('MIGRATION_PACKAGE_INVALID')
        if Path(os.path.realpath(package)) != package:
            _fault('MIGRATION_PACKAGE_INVALID')
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            content = stream.read(16385)
    except ValidationError:
        raise
    except (OSError, ValueError):
        _fault('MIGRATION_PACKAGE_INVALID')
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (len(content) > 16384 or b'\r' in content
            or hashlib.sha256(content).hexdigest() != SERVICE_ROOTS_PACKAGE_SHA256):
        _fault('MIGRATION_PACKAGE_INVALID')
    try:
        value = json.loads(content.decode('utf-8', errors='strict'),
                           object_pairs_hook=_pairs)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fault('MIGRATION_PACKAGE_INVALID')
    return _validate_service_roots_package(value)


def _read_service_details_package(parent_package=None):
    package = Path(__file__).resolve().with_name(SERVICE_DETAILS_PACKAGE_NAME)
    if (package.name != SERVICE_DETAILS_PACKAGE_NAME
            or package.parent != Path(__file__).resolve().parent):
        _fault('MIGRATION_PACKAGE_INVALID')
    nofollow = getattr(os, 'O_NOFOLLOW', None)
    if nofollow is None:
        _fault('MIGRATION_PACKAGE_UNSUPPORTED')
    descriptor = None
    try:
        descriptor = os.open(package, os.O_RDONLY | nofollow)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or not 1 <= info.st_size <= 98304:
            _fault('MIGRATION_PACKAGE_INVALID')
        if Path(os.path.realpath(package)) != package:
            _fault('MIGRATION_PACKAGE_INVALID')
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            content = stream.read(98305)
    except ValidationError:
        raise
    except (OSError, ValueError):
        _fault('MIGRATION_PACKAGE_INVALID')
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (len(content) > 98304 or b'\r' in content
            or hashlib.sha256(content).hexdigest() != SERVICE_DETAILS_PACKAGE_SHA256):
        _fault('MIGRATION_PACKAGE_INVALID')
    try:
        value = json.loads(content.decode('utf-8', errors='strict'),
                           object_pairs_hook=_pairs)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fault('MIGRATION_PACKAGE_INVALID')
    if parent_package is None:
        parent_package = _read_service_roots_package()
    return _validate_service_details_package(value, parent_package)


def _read_planned_maintenance_package(catalog_package=None):
    package = Path(__file__).resolve().with_name(PLANNED_PACKAGE_NAME)
    if (package.name != PLANNED_PACKAGE_NAME
            or package.parent != Path(__file__).resolve().parent):
        _fault('MIGRATION_PACKAGE_INVALID')
    nofollow = getattr(os, 'O_NOFOLLOW', None)
    if nofollow is None:
        _fault('MIGRATION_PACKAGE_UNSUPPORTED')
    descriptor = None
    try:
        descriptor = os.open(package, os.O_RDONLY | nofollow)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or not 1 <= info.st_size <= 65536:
            _fault('MIGRATION_PACKAGE_INVALID')
        if Path(os.path.realpath(package)) != package:
            _fault('MIGRATION_PACKAGE_INVALID')
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            content = stream.read(65537)
    except ValidationError:
        raise
    except (OSError, ValueError):
        _fault('MIGRATION_PACKAGE_INVALID')
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (len(content) > 65536 or b'\r' in content
            or hashlib.sha256(content).hexdigest() != PLANNED_PACKAGE_SHA256):
        _fault('MIGRATION_PACKAGE_INVALID')
    try:
        value = json.loads(content.decode('utf-8', errors='strict'),
                           object_pairs_hook=_pairs)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fault('MIGRATION_PACKAGE_INVALID')
    if catalog_package is None:
        catalog_package = _read_services_package()
    return _validate_planned_maintenance_package(value, catalog_package)


def _read_leading_price_package(parent_package=None):
    package = Path(__file__).resolve().with_name(LEADING_PRICE_PACKAGE_NAME)
    if (package.name != LEADING_PRICE_PACKAGE_NAME
            or package.parent != Path(__file__).resolve().parent):
        _fault('MIGRATION_PACKAGE_INVALID')
    nofollow = getattr(os, 'O_NOFOLLOW', None)
    if nofollow is None:
        _fault('MIGRATION_PACKAGE_UNSUPPORTED')
    descriptor = None
    try:
        descriptor = os.open(package, os.O_RDONLY | nofollow)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or not 1 <= info.st_size <= 65536:
            _fault('MIGRATION_PACKAGE_INVALID')
        if Path(os.path.realpath(package)) != package:
            _fault('MIGRATION_PACKAGE_INVALID')
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            content = stream.read(65537)
    except ValidationError:
        raise
    except (OSError, ValueError):
        _fault('MIGRATION_PACKAGE_INVALID')
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (len(content) > 65536 or b'\r' in content
            or hashlib.sha256(content).hexdigest() != LEADING_PRICE_PACKAGE_SHA256):
        _fault('MIGRATION_PACKAGE_INVALID')
    try:
        value = json.loads(content.decode('utf-8', errors='strict'),
                           object_pairs_hook=_pairs)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fault('MIGRATION_PACKAGE_INVALID')
    if parent_package is None:
        parent_package = _read_service_roots_package()
    return _validate_leading_price_package(value, parent_package)


def _read_diagnostics_package(catalog_package=None):
    package = Path(__file__).resolve().with_name(DIAGNOSTICS_PACKAGE_NAME)
    if (package.name != DIAGNOSTICS_PACKAGE_NAME
            or package.parent != Path(__file__).resolve().parent):
        _fault('MIGRATION_PACKAGE_INVALID')
    nofollow = getattr(os, 'O_NOFOLLOW', None)
    if nofollow is None:
        _fault('MIGRATION_PACKAGE_UNSUPPORTED')
    descriptor = None
    try:
        descriptor = os.open(package, os.O_RDONLY | nofollow)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or not 1 <= info.st_size <= 98304:
            _fault('MIGRATION_PACKAGE_INVALID')
        if Path(os.path.realpath(package)) != package:
            _fault('MIGRATION_PACKAGE_INVALID')
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            content = stream.read(98305)
    except ValidationError:
        raise
    except (OSError, ValueError):
        _fault('MIGRATION_PACKAGE_INVALID')
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (len(content) > 98304 or b'\r' in content
            or hashlib.sha256(content).hexdigest() != DIAGNOSTICS_PACKAGE_SHA256):
        _fault('MIGRATION_PACKAGE_INVALID')
    try:
        value = json.loads(content.decode('utf-8', errors='strict'),
                           object_pairs_hook=_pairs)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fault('MIGRATION_PACKAGE_INVALID')
    if catalog_package is None:
        catalog_package = _read_services_package()
    return _validate_diagnostics_package(value, catalog_package)


def _read_combined_services_package():
    package = Path(__file__).resolve().with_name(COMBINED_PACKAGE_NAME)
    if (package.name != COMBINED_PACKAGE_NAME
            or package.parent != Path(__file__).resolve().parent):
        _fault('MIGRATION_PACKAGE_INVALID')
    nofollow = getattr(os, 'O_NOFOLLOW', None)
    if nofollow is None:
        _fault('MIGRATION_PACKAGE_UNSUPPORTED')
    descriptor = None
    try:
        descriptor = os.open(package, os.O_RDONLY | nofollow)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            _fault('MIGRATION_PACKAGE_INVALID')
        _combined_enforce_package_bytes(info.st_size)
        if Path(os.path.realpath(package)) != package:
            _fault('MIGRATION_PACKAGE_INVALID')
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            content = stream.read(524289)
    except ValidationError:
        raise
    except (OSError, ValueError):
        _fault('MIGRATION_PACKAGE_INVALID')
    finally:
        if descriptor is not None:
            os.close(descriptor)
    _combined_enforce_package_bytes(len(content))
    if (b'\r' in content
            or hashlib.sha256(content).hexdigest() != COMBINED_PACKAGE_SHA256):
        _fault('MIGRATION_PACKAGE_INVALID')
    try:
        value = json.loads(content.decode('utf-8', errors='strict'),
                           object_pairs_hook=_pairs)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fault('MIGRATION_PACKAGE_INVALID')
    return _validate_combined_services_package(value)


def _read_combined_infographic_package():
    path = Path(__file__).resolve().with_name(COMBINED_INFOGRAPHIC_PACKAGE_NAME)
    if (path.name != COMBINED_INFOGRAPHIC_PACKAGE_NAME
            or path.parent != Path(__file__).resolve().parent):
        _fault('MIGRATION_PACKAGE_INVALID')
    nofollow = getattr(os, 'O_NOFOLLOW', None)
    if nofollow is None:
        _fault('MIGRATION_PACKAGE_UNSUPPORTED')
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | nofollow)
        info = os.fstat(descriptor)
        if info.st_size > 65536:
            _fault('MIGRATION_PACKAGE_INVALID')
        if not stat.S_ISREG(info.st_mode) or Path(os.path.realpath(path)) != path:
            _fault('MIGRATION_PACKAGE_INVALID')
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            content = stream.read(65537)
    except ValidationError:
        raise
    except (OSError, ValueError):
        _fault('MIGRATION_PACKAGE_INVALID')
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (len(content) > 65536 or len(content) != info.st_size or b'\r' in content
            or hashlib.sha256(content).hexdigest()
            != COMBINED_INFOGRAPHIC_PACKAGE_SHA256):
        _fault('MIGRATION_PACKAGE_INVALID')
    try:
        value = json.loads(content.decode('utf-8', errors='strict'),
                           object_pairs_hook=_pairs)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fault('MIGRATION_PACKAGE_INVALID')
    expected = {
        'schema': 'dev09m-infographic-map019-v1',
        'policy': 'owner-approved-after-intro-one-image',
        'source': {
            'relative_path': 'media/design-concepts/infographics/map-019-body-repair-sample-v1.png',
            'mime': 'image/png', 'width': 1448, 'height': 1086,
            'bytes': 2025618,
            'sha256': '01bfda46e7dba90adb38affd6fe615beba90f9e182a77073a5ec6e27fa5c5678',
        },
        'media': {
            'relative_path': 'media/design-concepts/infographics/map-019-body-repair-v1.webp',
            'mime': 'image/webp', 'width': 1200, 'height': 900,
            'bytes': 104682,
            'sha256': 'c86b3d2912b72c4169193777a4df62f0b8ab075bddb9551a77da0027dc6417c5',
            'image_id': 'db49b593-85b1-5377-8873-a4013f762d5e',
            'asset_id': '6fa5cdd8-dabd-52ab-b994-4e10ef2cb2c8',
            'file_id': 'b7cd2e13-9427-57cc-b65e-28fdc5aaff71',
            'folder_id': 'b6fbe54a-6483-5459-a856-0c4d3c6f6afd',
            'folder_path': 'design/services/infographics',
            'storage_key': 'img/6fa5cdd8-dabd-52ab-b994-4e10ef2cb2c8/main.webp',
            'alt': ('Три этапа ремонта кузова: оценка повреждений, '
                    'восстановление деталей и проверка результата.'),
            'alignment': 'center',
        },
        'binding': {
            'map_id': 'MAP-019',
            'page_id': '080d64ee-4ce1-5399-b672-83dc22f9f8bf',
            'url': '/services/kuzovnoj-remont/remont-kuzova',
            'position': 'after_intro_text',
            'block_id': '98ad3c39-de8d-5894-9ce4-a073179ff23e',
        },
    }
    if value != expected:
        _fault('MIGRATION_PACKAGE_INVALID')
    return value


def _combined_infographic_source(package, source_root):
    try:
        root = Path(source_root).resolve(strict=True)
        relative = Path(package['media']['relative_path'])
        path = root.joinpath(*relative.parts)
        info = path.lstat()
        resolved = path.resolve(strict=True)
        content = path.read_bytes()
    except OSError:
        _fault('MIGRATION_MEDIA_SOURCE_UNAVAILABLE')
    if (not stat.S_ISREG(info.st_mode) or path.is_symlink()
            or resolved != path.absolute() or root not in resolved.parents
            or len(content) != info.st_size
            or len(content) != package['media']['bytes']
            or hashlib.sha256(content).hexdigest()
            != package['media']['sha256']):
        _fault('MIGRATION_MEDIA_SOURCE_UNAVAILABLE')
    return content


def _combined_infographic_exact_asset(package, asset, files):
    row = package['media']
    return (str(asset.folder_id) == row['folder_id']
            and asset.status in (Asset.Status.STAGED, Asset.Status.READY)
            and asset.provenance == COMBINED_INFOGRAPHIC_PROVENANCE
            and asset.is_legacy is False and asset.source_url == ''
            and asset.source_sha256 == row['sha256'] and len(files) == 1
            and str(files[0].pk) == row['file_id']
            and files[0].kind == AssetFile.Kind.MAIN
            and files[0].key == row['storage_key']
            and files[0].sha256 == row['sha256']
            and files[0].byte_size == row['bytes'])


def import_combined_infographic_media(*, source_root, storage=None):
    """Import the one approved MAP-019 WebP, or verify its exact replay."""
    _enabled()
    package = _read_combined_infographic_package()
    content = _combined_infographic_source(package, source_root)
    row = package['media']
    storage = storage or MediaStorage()
    with transaction.atomic():
        folder = MediaFolder.objects.select_for_update().filter(
            pk=row['folder_id']).first()
        if folder is None:
            MediaFolder.objects.create(id=UUID(row['folder_id']),
                                       path=row['folder_path'])
        elif folder.path != row['folder_path']:
            _fault('MIGRATION_MEDIA_EXISTING_CONFLICT')
    with transaction.atomic():
        asset = Asset.objects.select_for_update().filter(
            pk=row['asset_id']).first()
        if asset is None:
            asset = Asset.objects.create(
                id=UUID(row['asset_id']), folder_id=row['folder_id'],
                provenance=COMBINED_INFOGRAPHIC_PROVENANCE,
                source_sha256=row['sha256'])
            status = 'created'
        else:
            status = 'replayed' if asset.status == Asset.Status.READY else 'recovered'
        files = list(AssetFile.objects.select_for_update().filter(
            asset=asset).order_by('pk'))
        if asset.status == Asset.Status.READY:
            if (not _combined_infographic_exact_asset(package, asset, files)
                    or storage.manifest(row['storage_key']) != {
                        'sha256': row['sha256'], 'byte_size': row['bytes']}):
                _fault('MIGRATION_MEDIA_EXISTING_CONFLICT')
            return {'status': 'pass', 'asset': row['asset_id'],
                    'result': status}
        if asset.status != Asset.Status.STAGED:
            _fault('MIGRATION_MEDIA_EXISTING_CONFLICT')
        if files:
            if (not _combined_infographic_exact_asset(package, asset, files)
                    or storage.manifest(row['storage_key']) != {
                        'sha256': row['sha256'], 'byte_size': row['bytes']}):
                _fault('MIGRATION_MEDIA_EXISTING_CONFLICT')
        else:
            media_services.write_file(
                asset_id=asset.pk, file_id=row['file_id'],
                kind=AssetFile.Kind.MAIN, key=row['storage_key'],
                chunks=content, storage=storage)
    media_services.mark_ready(asset_id=row['asset_id'], storage=storage)
    return {'status': 'pass', 'asset': row['asset_id'], 'result': status}


def _exact_keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        _fault('MIGRATION_PACKAGE_INVALID')


def _canonical_uuid(value):
    try:
        return type(value) is str and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def _validate_package(value):
    _exact_keys(value, {'schema', 'policy', 'inputs', 'pages'})
    if (value['schema'] != 'dev09-articles-slice-v2'
            or value['policy'] != 'validated_package_not_import_authority'):
        _fault('MIGRATION_PACKAGE_INVALID')
    _exact_keys(value['inputs'], {'map_sha256', 'evidence_sha256'})
    if (value['inputs'] != {'map_sha256': MAP_SHA256,
                            'evidence_sha256': RTE_SHA256}
            or type(value['pages']) is not list
            or len(value['pages']) != len(EXPECTED)):
        _fault('MIGRATION_PACKAGE_INVALID')
    identifiers = set()
    positions = set()
    for page, expected in zip(value['pages'], EXPECTED, strict=True):
        _exact_keys(page, PAGE_KEYS)
        _exact_keys(page['source'], {'relative_path', 'sha256'})
        (map_id, page_id, url, kind, parent_id, position, name, content_state,
         source_path, source_sha, block_shape) = expected
        if (page['map_id'] != map_id or page['page_id'] != page_id
                or page['url'] != url or page['kind'] != kind
                or page['parent_id'] != parent_id or page['position'] != position
                or page['name'] != name or page['content_state'] != content_state
                or page['description'] != '' or page['is_published'] is not False
                or page['source'] != {'relative_path': source_path,
                                      'sha256': source_sha}
                or not _canonical_uuid(page['page_id'])
                or (page['parent_id'] is not None
                    and not _canonical_uuid(page['parent_id']))
                or type(page['h1']) is not str or type(page['title']) is not str):
            _fault('MIGRATION_PACKAGE_INVALID')
        position_key = (page['parent_id'], page['position'])
        if page_id in identifiers or position_key in positions:
            _fault('MIGRATION_PACKAGE_INVALID')
        identifiers.add(page_id)
        positions.add(position_key)
        blocks = page['blocks']
        if (type(blocks) is not list or len(blocks) != len(block_shape)):
            _fault('MIGRATION_PACKAGE_INVALID')
        texts = [page['name'], page['h1'], page['title']]
        for block, token in zip(blocks, block_shape, strict=True):
            count = int(token[1:]) if len(token) > 1 and token[1:].isdigit() else 0
            if token.startswith('p'):
                _exact_keys(block, {'type', 'segments'})
                values = block['segments']
                expected_type = 'paragraph'
            elif token.startswith('u'):
                _exact_keys(block, {'type', 'items'})
                values = block['items']
                expected_type = 'unordered_list'
            else:
                _fault('MIGRATION_PACKAGE_INVALID')
            if (block['type'] != expected_type or type(values) is not list
                    or len(values) != count
                    or any(type(text) is not str or not text for text in values)):
                _fault('MIGRATION_PACKAGE_INVALID')
            texts.extend(values)
        if ((content_state == 'deferred' and blocks != [])
                or (content_state == 'source_text_complete_media_deferred'
                    and not blocks)):
            _fault('MIGRATION_PACKAGE_INVALID')
        for text in texts:
            schema.text(text, multiline=False)
    return value


def _validate_services_package(value):
    _exact_keys(value, {'schema', 'policy', 'inputs', 'page'})
    if (value['schema'] != 'dev09-services-catalog-v1'
            or value['policy'] != 'validated_package_not_import_authority'):
        _fault('MIGRATION_PACKAGE_INVALID')
    _exact_keys(value['inputs'], {
        'map_sha256', 'evidence_sha256', 'source_sha256'})
    if value['inputs'] != {
            'map_sha256': MAP_SHA256, 'evidence_sha256': RTE_SHA256,
            'source_sha256': SERVICES_SOURCE_SHA256}:
        _fault('MIGRATION_PACKAGE_INVALID')
    page = value['page']
    _exact_keys(page, set(SERVICES_PAGE) | {'source', 'groups'})
    _exact_keys(page['source'], {'relative_path', 'sha256'})
    if (any(page[key] != expected for key, expected in SERVICES_PAGE.items())
            or page['source'] != {
                'relative_path': SERVICES_SOURCE_PATH,
                'sha256': SERVICES_SOURCE_SHA256}
            or not _canonical_uuid(page['page_id'])
            or not _canonical_uuid(page['parent_id'])
            or type(page['groups']) is not list
            or len(page['groups']) != len(SERVICES_GROUP_COUNTS)):
        _fault('MIGRATION_PACKAGE_INVALID')
    for group, count in zip(
            page['groups'], SERVICES_GROUP_COUNTS, strict=True):
        _exact_keys(group, {'name', 'href', 'items'})
        if type(group['items']) is not list or len(group['items']) + 1 != count:
            _fault('MIGRATION_PACKAGE_INVALID')
        for item in [group, *group['items']]:
            if item is not group:
                _exact_keys(item, {'name', 'href'})
            if (type(item['name']) is not str or not item['name']
                    or len(item['name']) > 200
                    or type(item['href']) is not str
                    or re.fullmatch(r'/services/[a-z0-9/-]+', item['href']) is None
                    or '//' in item['href'] or '..' in item['href']):
                _fault('MIGRATION_PACKAGE_INVALID')
            schema.text(item['name'], limit=200, multiline=False)
    encoded_groups = json.dumps(
        page['groups'], ensure_ascii=False,
        separators=(',', ':')).encode('utf-8')
    if hashlib.sha256(encoded_groups).hexdigest() != SERVICES_GROUPS_SHA256:
        _fault('MIGRATION_PACKAGE_INVALID')
    return value


def _validate_service_roots_package(value):
    _exact_keys(value, {'schema', 'policy', 'inputs', 'pages'})
    if (value['schema'] != 'dev09-service-roots-v1'
            or value['policy'] != 'validated_approved_artifact_not_import_authority'
            or value['inputs'] != {'map_sha256': MAP_SHA256,
                                   'evidence_sha256': RTE_SHA256}
            or type(value['pages']) is not list
            or len(value['pages']) != 2):
        _fault('MIGRATION_PACKAGE_INVALID')
    for page, expected in zip(value['pages'], SERVICE_ROOTS_EXPECTED, strict=True):
        _exact_keys(page, {'page_id', 'map_id', 'url', 'kind', 'parent_id',
                           'position', 'name', 'h1', 'title', 'description',
                           'is_published', 'source', 'artifact', 'tiles'})
        _exact_keys(page['source'], {'relative_path', 'sha256'})
        _exact_keys(page['artifact'], {'relative_path', 'sha256'})
        (page_id, map_id, url, position, name, h1, title, source_path,
         source_sha, artifact_path, artifact_sha, tile_count) = expected
        if (page['page_id'] != page_id or page['map_id'] != map_id
                or page['url'] != url or page['kind'] != 'service_catalog'
                or page['parent_id'] != SERVICES_PAGE['page_id']
                or page['position'] != position or page['name'] != name
                or page['h1'] != h1 or page['title'] != title
                or page['description'] != '' or page['is_published'] is not False
                or page['source'] != {'relative_path': source_path, 'sha256': source_sha}
                or page['artifact'] != {'relative_path': artifact_path,
                                         'sha256': artifact_sha}
                or not _canonical_uuid(page_id) or type(page['tiles']) is not list
                or len(page['tiles']) != tile_count):
            _fault('MIGRATION_PACKAGE_INVALID')
        for tile in page['tiles']:
            _exact_keys(tile, {'name', 'href'})
            if (type(tile['name']) is not str or not tile['name']
                    or len(tile['name']) > 200 or type(tile['href']) is not str
                    or re.fullmatch(r'/services/[a-z0-9/-]+', tile['href']) is None
                    or '//' in tile['href'] or '..' in tile['href']):
                _fault('MIGRATION_PACKAGE_INVALID')
            schema.text(tile['name'], limit=200, multiline=False)
    encoded = json.dumps([page['tiles'] for page in value['pages']],
                         ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if hashlib.sha256(encoded).hexdigest() != SERVICE_ROOTS_TILES_SHA256:
        _fault('MIGRATION_PACKAGE_INVALID')
    return value


def _validate_service_text(page):
    schema.text(page['name'], limit=200, multiline=False)
    schema.text(page['h1'], multiline=False)
    schema.text(page['title'], multiline=False)
    schema.text(page['intro'], multiline=False)
    for block in page['blocks']:
        if type(block) is not dict or block.get('type') == 'heading':
            _exact_keys(block, {'type', 'text'})
            if block['type'] != 'heading' or type(block['text']) is not str:
                _fault('MIGRATION_PACKAGE_INVALID')
            schema.text(block['text'], multiline=False)
            continue
        if block.get('type') == 'paragraph':
            _exact_keys(block, {'type', 'segments'})
            cohorts = [block['segments']]
        elif block.get('type') in ('unordered_list', 'ordered_list'):
            _exact_keys(block, {'type', 'items'})
            cohorts = block['items']
        else:
            _fault('MIGRATION_PACKAGE_INVALID')
        if (type(cohorts) is not list or not cohorts
                or any(type(segments) is not list or not segments
                       for segments in cohorts)):
            _fault('MIGRATION_PACKAGE_INVALID')
        for segments in cohorts:
            for segment in segments:
                _exact_keys(segment, {'text', 'strong'})
                if (type(segment['text']) is not str or not segment['text']
                        or type(segment['strong']) is not bool):
                    _fault('MIGRATION_PACKAGE_INVALID')
                schema.text(segment['text'], multiline=False)


def _validate_service_details_package(value, parent_package):
    _exact_keys(value, {'schema', 'policy', 'inputs', 'pages'})
    if (value['schema'] != 'dev09-service-details-v1'
            or value['policy'] != 'validated_approved_text_not_import_authority'
            or value['inputs'] != {
                'map_sha256': MAP_SHA256, 'evidence_sha256': RTE_SHA256,
                'parent_package_sha256': SERVICE_ROOTS_PACKAGE_SHA256}
            or type(value['pages']) is not list or len(value['pages']) != 10):
        _fault('MIGRATION_PACKAGE_INVALID')
    parents = {page['page_id']: page for page in parent_package['pages']}
    identities, positions, urls = set(), set(), set()
    for page in value['pages']:
        _exact_keys(page, {'page_id', 'map_id', 'url', 'kind', 'parent_id',
                           'position', 'name', 'h1', 'title', 'description',
                           'is_published', 'source', 'artifact', 'intro', 'blocks'})
        _exact_keys(page['source'], {'relative_path', 'sha256'})
        _exact_keys(page['artifact'], {'relative_path', 'sha256'})
        parent = parents.get(page['parent_id'])
        tile = (parent['tiles'][page['position']]
                if parent is not None and type(page['position']) is int
                and 0 <= page['position'] < len(parent['tiles']) else None)
        if (page['kind'] != 'service_detail' or page['is_published'] is not False
                or page['description'] != '' or not _canonical_uuid(page['page_id'])
                or parent is None or tile is None
                or tile != {'name': page['name'], 'href': page['url']}
                or type(page['intro']) is not str or not page['intro']
                or type(page['blocks']) is not list or not page['blocks']
                or type(page['map_id']) is not str or type(page['h1']) is not str
                or type(page['title']) is not str):
            _fault('MIGRATION_PACKAGE_INVALID')
        identity, position = page['page_id'], (page['parent_id'], page['position'])
        if identity in identities or position in positions or page['url'] in urls:
            _fault('MIGRATION_PACKAGE_INVALID')
        identities.add(identity); positions.add(position); urls.add(page['url'])
        _validate_service_text(page)
    encoded = json.dumps(value['pages'], ensure_ascii=False,
                         separators=(',', ':')).encode('utf-8')
    if hashlib.sha256(encoded).hexdigest() != SERVICE_DETAILS_PAGES_SHA256:
        _fault('MIGRATION_PACKAGE_INVALID')
    return value


def _validate_leading_price_package(value, parent_package):
    _exact_keys(value, {'schema', 'policy', 'inputs', 'pages'})
    if (value['schema'] != 'dev09-leading-price-details-v1'
            or value['policy'] != 'validated_approved_price_text_not_import_authority'
            or value['inputs'] != {
                'map_sha256': MAP_SHA256, 'evidence_sha256': RTE_SHA256,
                'parent_package_sha256': SERVICE_ROOTS_PACKAGE_SHA256}
            or type(value['pages']) is not list or len(value['pages']) != 5):
        _fault('MIGRATION_PACKAGE_INVALID')
    parents = [page for page in parent_package['pages']
               if page['map_id'] == 'MAP-012']
    if len(parents) != 1:
        _fault('MIGRATION_PACKAGE_INVALID')
    parent = parents[0]
    identities, positions, urls = set(), set(), set()
    text_cells = {
        (2, 12): 'от 3500 за 1 шт.',
        (2, 15): '1500 за 1 шт.',
    }
    for page_index, (page, row_count) in enumerate(
            zip(value['pages'], LEADING_PRICE_ROW_COUNTS, strict=True)):
        _exact_keys(page, {'page_id', 'map_id', 'url', 'kind', 'parent_id',
                           'position', 'name', 'h1', 'title', 'description',
                           'is_published', 'source', 'artifact', 'intro',
                           'blocks', 'price_rows'})
        _exact_keys(page['source'], {'relative_path', 'sha256'})
        _exact_keys(page['artifact'], {'relative_path', 'sha256'})
        tile = (parent['tiles'][page['position']]
                if type(page['position']) is int
                and 0 <= page['position'] < len(parent['tiles']) else None)
        if (page['kind'] != 'service_detail' or page['parent_id'] != parent['page_id']
                or page['is_published'] is not False or page['description'] != ''
                or not _canonical_uuid(page['page_id'])
                or tile != {'name': page['name'], 'href': page['url']}
                or type(page['intro']) is not str or not page['intro']
                or type(page['blocks']) is not list or not page['blocks']
                or type(page['price_rows']) is not list
                or len(page['price_rows']) != row_count
                or type(page['map_id']) is not str or type(page['h1']) is not str
                or type(page['title']) is not str):
            _fault('MIGRATION_PACKAGE_INVALID')
        identity, position = page['page_id'], (page['parent_id'], page['position'])
        if identity in identities or position in positions or page['url'] in urls:
            _fault('MIGRATION_PACKAGE_INVALID')
        identities.add(identity); positions.add(position); urls.add(page['url'])
        _validate_service_text(page)
        for row_index, row in enumerate(page['price_rows']):
            _exact_keys(row, {'label', 'cell'})
            if type(row['label']) is not str or not row['label']:
                _fault('MIGRATION_PACKAGE_INVALID')
            try:
                schema.text(row['label'], 500, multiline=False)
            except ValidationError:
                _fault('MIGRATION_PACKAGE_INVALID')
            expected_text = text_cells.get((page_index, row_index))
            cell = row['cell']
            if expected_text is not None:
                _exact_keys(cell, {'kind', 'text'})
                if cell != {'kind': 'text', 'text': expected_text}:
                    _fault('MIGRATION_PACKAGE_INVALID')
            else:
                _exact_keys(cell, {'kind', 'amount', 'from'})
                if (cell['kind'] != 'amount' or type(cell['amount']) is not str
                        or re.fullmatch(r'(0|[1-9][0-9]{0,8})(\.[0-9]{1,2})?',
                                        cell['amount']) is None
                        or type(cell['from']) is not bool):
                    _fault('MIGRATION_PACKAGE_INVALID')
    encoded = json.dumps(value['pages'], ensure_ascii=False,
                         separators=(',', ':')).encode('utf-8')
    if hashlib.sha256(encoded).hexdigest() != LEADING_PRICE_PAGES_SHA256:
        _fault('MIGRATION_PACKAGE_INVALID')
    return value


def _validate_diagnostics_package(value, catalog_package):
    _exact_keys(value, {'schema', 'policy', 'inputs', 'pages'})
    if (value['schema'] != 'dev09-diagnostics-branch-v1'
            or value['policy'] != 'validated_approved_diagnostics_text_not_import_authority'
            or value['inputs'] != {
                'map_sha256': MAP_SHA256, 'evidence_sha256': RTE_SHA256,
                'catalog_package_sha256': SERVICES_PACKAGE_SHA256}
            or type(value['pages']) is not list or len(value['pages']) != 10):
        _fault('MIGRATION_PACKAGE_INVALID')
    catalog = catalog_package.get('page') if type(catalog_package) is dict else None
    groups = catalog.get('groups') if type(catalog) is dict else None
    group = groups[3] if type(groups) is list and len(groups) == 5 else None
    if (catalog is None or catalog.get('map_id') != 'MAP-002'
            or type(group) is not dict or group.get('name') != 'Диагностика'
            or group.get('href') != '/services/diagnostika/'
            or type(group.get('items')) is not list or len(group['items']) != 10):
        _fault('MIGRATION_PACKAGE_INVALID')
    parent = value['pages'][0]
    source_table = {
        'headers': ['Класс авто, наименование работ', 'Цена, руб.'],
        'rows': [
            {'kind': 'category', 'label': 'ВАЗ'},
            {'kind': 'service', 'label': 'Диагностика ЭСУД и удаление ошибок',
             'price': 'от 1500'},
            {'kind': 'category', 'label': 'Иномарки среднего класса'},
            {'kind': 'service', 'label': 'Диагностика ЭСУД и удаление ошибок',
             'price': 'от 1500'},
            {'kind': 'category', 'label': 'Внедорожники'},
            {'kind': 'service', 'label': 'Диагностика ЭСУД и удаление ошибок',
             'price': 'от 1500'},
        ],
    }
    if (type(parent) is not dict or parent.get('map_id') != 'MAP-013'
            or parent.get('kind') != 'service_section_overview'
            or parent.get('parent_id') != catalog['page_id']
            or parent.get('position') != 3
            or group.get('name') != parent.get('name')
            or group.get('href') != parent.get('url')
            or parent.get('source_table') != source_table):
        _fault('MIGRATION_PACKAGE_INVALID')
    identities, positions, urls = set(), set(), set()
    for index, page in enumerate(value['pages']):
        keys = {'page_id', 'map_id', 'url', 'kind', 'parent_id', 'position',
                'name', 'h1', 'title', 'description', 'is_published',
                'source', 'artifact', 'intro', 'blocks'}
        if index == 0:
            keys.add('source_table')
        _exact_keys(page, keys)
        _exact_keys(page['source'], {'relative_path', 'sha256'})
        _exact_keys(page['artifact'], {'relative_path', 'sha256'})
        if index == 0:
            expected_parent = catalog['page_id']
            tile = {'name': group['name'], 'href': group['href']}
            expected_kind = 'service_section_overview'
        else:
            expected_parent = parent['page_id']
            item = group['items'][page['position']] if (
                type(page['position']) is int
                and 0 <= page['position'] < len(group['items'])) else None
            tile = item
            expected_kind = 'service_detail'
        if (page['kind'] != expected_kind or page['parent_id'] != expected_parent
                or page['is_published'] is not False or page['description'] != ''
                or not _canonical_uuid(page['page_id'])
                or tile != {'name': page['name'], 'href': page['url']}
                or type(page['intro']) is not str or not page['intro']
                or type(page['blocks']) is not list or not page['blocks']
                or type(page['map_id']) is not str or type(page['h1']) is not str
                or type(page['title']) is not str):
            _fault('MIGRATION_PACKAGE_INVALID')
        identity, position = page['page_id'], (page['parent_id'], page['position'])
        if identity in identities or position in positions or page['url'] in urls:
            _fault('MIGRATION_PACKAGE_INVALID')
        identities.add(identity); positions.add(position); urls.add(page['url'])
        _validate_service_text(page)
    encoded = json.dumps(value['pages'], ensure_ascii=False,
                         separators=(',', ':')).encode('utf-8')
    if hashlib.sha256(encoded).hexdigest() != DIAGNOSTICS_PAGES_SHA256:
        _fault('MIGRATION_PACKAGE_INVALID')
    return value


def _validate_planned_maintenance_package(value, catalog_package):
    _exact_keys(value, {'schema', 'policy', 'inputs', 'pages'})
    if (value['schema'] != 'dev09-planned-maintenance-v1'
            or value['policy'] != 'validated_approved_text_not_import_authority'
            or value['inputs'] != {
                'map_sha256': MAP_SHA256, 'evidence_sha256': RTE_SHA256,
                'catalog_package_sha256': SERVICES_PACKAGE_SHA256}
            or type(value['pages']) is not list or len(value['pages']) != 9):
        _fault('MIGRATION_PACKAGE_INVALID')
    catalog = catalog_package['page']
    group = catalog['groups'][1]
    parent = value['pages'][0]
    if (group['name'] != 'Плановое ТО'
            or group['href'] != '/services/planovoe-to/'
            or len(group['items']) != 9
            or group['items'][2] != {
                'name': 'Замена фильтров',
                'href': '/services/planovoe-to/zamena-filtrov'}):
        _fault('MIGRATION_PACKAGE_INVALID')
    identities, positions, urls = set(), set(), set()
    expected_positions = (1, 0, 1, 3, 4, 5, 6, 7, 8)
    for index, page in enumerate(value['pages']):
        _exact_keys(page, {'page_id', 'map_id', 'url', 'kind', 'parent_id',
                           'position', 'name', 'h1', 'title', 'description',
                           'is_published', 'source', 'artifact', 'intro', 'blocks'})
        _exact_keys(page['source'], {'relative_path', 'sha256'})
        _exact_keys(page['artifact'], {'relative_path', 'sha256'})
        is_parent = index == 0
        tile = ({'name': group['name'], 'href': group['href']} if is_parent
                else group['items'][page['position']]
                if type(page['position']) is int
                and 0 <= page['position'] < len(group['items']) else None)
        if (page['kind'] != ('service_section_overview'
                             if is_parent else 'service_detail')
                or page['parent_id'] != (catalog['page_id']
                                         if is_parent else parent['page_id'])
                or page['position'] != expected_positions[index]
                or page['is_published'] is not False or page['description'] != ''
                or not _canonical_uuid(page['page_id'])
                or tile != {'name': page['name'], 'href': page['url']}
                or type(page['intro']) is not str or not page['intro']
                or type(page['blocks']) is not list or not page['blocks']
                or type(page['map_id']) is not str or type(page['h1']) is not str
                or type(page['title']) is not str):
            _fault('MIGRATION_PACKAGE_INVALID')
        identity, position = page['page_id'], (page['parent_id'], page['position'])
        if identity in identities or position in positions or page['url'] in urls:
            _fault('MIGRATION_PACKAGE_INVALID')
        identities.add(identity); positions.add(position); urls.add(page['url'])
        _validate_service_text(page)
    encoded = json.dumps(value['pages'], ensure_ascii=False,
                         separators=(',', ':')).encode('utf-8')
    if hashlib.sha256(encoded).hexdigest() != PLANNED_PAGES_SHA256:
        _fault('MIGRATION_PACKAGE_INVALID')
    return value


def _combined_digest(value):
    encoded = json.dumps(value, ensure_ascii=False,
                         separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _combined_text(value, *, empty=False):
    if (type(value) is not str or (not empty and not value)
            or len(value.encode('utf-8')) > 8192
            or '<' in value or '>' in value or '{{' in value or '{%' in value):
        _fault('MIGRATION_PACKAGE_INVALID')
    schema.text(value, multiline=False)
    return value


def _validate_combined_segments(value):
    if type(value) is not list or not 1 <= len(value) <= 128:
        _fault('MIGRATION_PACKAGE_INVALID')
    for segment in value:
        _exact_keys(segment, {'text', 'strong'})
        if type(segment['strong']) is not bool:
            _fault('MIGRATION_PACKAGE_INVALID')
        _combined_text(segment['text'])


def _validate_combined_list(block, *, map_id, depth=1):
    _exact_keys(block, {'type', 'items'})
    if (block['type'] not in ('unordered_list', 'ordered_list')
            or type(block['items']) is not list
            or not 1 <= len(block['items']) <= 128):
        _fault('MIGRATION_PACKAGE_INVALID')
    for index, item in enumerate(block['items']):
        allowed = {'segments'}
        if (map_id == 'MAP-024' and block['type'] == 'ordered_list'
                and depth == 1 and index == 0):
            allowed.add('children')
        _exact_keys(item, allowed)
        _validate_combined_segments(item['segments'])
        if 'children' in item:
            child = item['children']
            if (type(child) is not list or len(child) != 1
                    or type(child[0]) is not dict
                    or child[0].get('type') != 'unordered_list'):
                _fault('MIGRATION_PACKAGE_INVALID')
            _validate_combined_list(child[0], map_id=map_id, depth=2)


def _validate_combined_table(block):
    _exact_keys(block, {'type', 'caption', 'header', 'rows'})
    if block['type'] != 'table':
        _fault('MIGRATION_PACKAGE_INVALID')
    if block['caption'] is not None:
        _validate_combined_segments(block['caption'])
    if (type(block['header']) is not list
            or not 1 <= len(block['header']) <= 16
            or type(block['rows']) is not list
            or not 1 <= len(block['rows']) <= 128):
        _fault('MIGRATION_PACKAGE_INVALID')
    width = sum(cell.get('colspan', 0) if type(cell) is dict else 0
                for cell in block['header'])
    if not 1 <= width <= 16:
        _fault('MIGRATION_PACKAGE_INVALID')
    _combined_enforce_table_caps(
        rows=len(block['rows']), columns=width,
        cells=len(block['header']) + sum(len(row) for row in block['rows']))

    def validate_cell(cell, rows_left):
        _exact_keys(cell, {'text', 'strong', 'rowspan', 'colspan', 'scope'})
        if (type(cell['strong']) is not bool
                or type(cell['rowspan']) is not int
                or type(cell['colspan']) is not int
                or not 1 <= cell['rowspan'] <= rows_left
                or not 1 <= cell['colspan'] <= 16
                or cell['scope'] not in (None, 'row', 'col')):
            _fault('MIGRATION_PACKAGE_INVALID')
        _combined_text(cell['text'])

    for cell in block['header']:
        validate_cell(cell, 1)
    occupied = [0] * width
    for row_index, row in enumerate(block['rows']):
        if type(row) is not list or not row:
            _fault('MIGRATION_PACKAGE_INVALID')
        for cell in row:
            validate_cell(cell, len(block['rows']) - row_index)
            try:
                start = occupied.index(0)
            except ValueError:
                _fault('MIGRATION_PACKAGE_INVALID')
            end = start + cell['colspan']
            if end > width or any(occupied[start:end]):
                _fault('MIGRATION_PACKAGE_INVALID')
            occupied[start:end] = [cell['rowspan']] * cell['colspan']
        if any(value == 0 for value in occupied):
            _fault('MIGRATION_PACKAGE_INVALID')
        occupied = [max(0, value - 1) for value in occupied]


def _validate_combined_block(block, *, map_id, section=False):
    if type(block) is not dict:
        _fault('MIGRATION_PACKAGE_INVALID')
    kind = block.get('type')
    if kind == 'heading' and not section:
        _exact_keys(block, {'type', 'text'})
        _combined_text(block['text'])
    elif kind == 'paragraph':
        _exact_keys(block, {'type', 'segments'})
        _validate_combined_segments(block['segments'])
    elif kind in ('unordered_list', 'ordered_list'):
        _validate_combined_list(block, map_id=map_id)
    elif kind == 'table' and not section:
        _validate_combined_table(block)
    elif kind == 'ordered_sections' and not section and map_id == 'MAP-041':
        _exact_keys(block, {'type', 'items'})
        if type(block['items']) is not list or not 1 <= len(block['items']) <= 32:
            _fault('MIGRATION_PACKAGE_INVALID')
        for item in block['items']:
            _exact_keys(item, {'heading', 'blocks'})
            _combined_text(item['heading'])
            if type(item['blocks']) is not list or not item['blocks']:
                _fault('MIGRATION_PACKAGE_INVALID')
            for child in item['blocks']:
                if child.get('type') not in ('paragraph', 'unordered_list',
                                             'ordered_list'):
                    _fault('MIGRATION_PACKAGE_INVALID')
                _validate_combined_block(child, map_id=map_id, section=True)
    else:
        _fault('MIGRATION_PACKAGE_INVALID')


def _combined_block_stats(block):
    stats = {'plain': 0, 'blocks': 1, 'items': 0, 'sections': 0,
             'tables': 0, 'cells': 0}

    def add_text(value):
        stats['plain'] += len(value.encode('utf-8'))

    kind = block['type']
    if kind == 'heading':
        add_text(block['text'])
    elif kind == 'paragraph':
        for segment in block['segments']:
            add_text(segment['text'])
    elif kind in ('unordered_list', 'ordered_list'):
        stats['items'] += len(block['items'])
        for item in block['items']:
            for segment in item['segments']:
                add_text(segment['text'])
            for child in item.get('children', []):
                child_stats = _combined_block_stats(child)
                for key in stats:
                    stats[key] += child_stats[key]
    elif kind == 'table':
        stats['tables'] = 1
        if block['caption'] is not None:
            for segment in block['caption']:
                add_text(segment['text'])
        cells = [*block['header'], *(cell for row in block['rows'] for cell in row)]
        stats['cells'] = len(cells)
        for cell in cells:
            add_text(cell['text'])
    elif kind == 'ordered_sections':
        stats['sections'] = len(block['items'])
        for item in block['items']:
            add_text(item['heading'])
            for child in item['blocks']:
                child_stats = _combined_block_stats(child)
                for key in stats:
                    stats[key] += child_stats[key]
    return stats


def _combined_enforce_page_caps(stats):
    if (stats['plain'] > 65536 or stats['blocks'] > 128
            or stats['items'] > 256 or stats['sections'] > 32
            or stats['tables'] > 4):
        _fault('MIGRATION_PACKAGE_INVALID')


def _combined_enforce_table_caps(*, rows, columns, cells):
    if not 1 <= rows <= 128 or not 1 <= columns <= 16 or cells > 2048:
        _fault('MIGRATION_PACKAGE_INVALID')


def _combined_enforce_package_caps(stats):
    if stats['blocks'] > 2048 or stats['cells'] > 4096:
        _fault('MIGRATION_PACKAGE_INVALID')


def _combined_enforce_rendered_caps(*, page_bytes=None, package_bytes=None):
    if ((page_bytes is not None and page_bytes > 131072)
            or (package_bytes is not None and package_bytes > 2097152)):
        _fault('MIGRATION_PACKAGE_INVALID')


def _combined_enforce_package_bytes(size):
    if type(size) is not int or not 1 <= size <= 524288:
        _fault('MIGRATION_PACKAGE_INVALID')


def _validate_combined_services_package(value):
    _exact_keys(value, {'schema', 'policy', 'inputs', 'pages', 'routes'})
    expected_inputs = {
        'map_sha256': MAP_SHA256,
        'evidence_sha256': RTE_SHA256,
        'identity_manifest_sha256': COMBINED_MANIFEST_SHA256,
        'page_content_sha256': COMBINED_PAGES_SHA256,
        'route_content_sha256': COMBINED_ROUTES_SHA256,
    }
    if (value['schema'] != 'dev09-combined-services-v1'
            or value['policy'] != 'reviewed_canonical_structured_data_authority'
            or value['inputs'] != expected_inputs
            or type(value['pages']) is not list or len(value['pages']) != 24
            or type(value['routes']) is not list or len(value['routes']) != 25
            or _combined_digest(value['pages']) != COMBINED_PAGES_SHA256
            or _combined_digest(value['routes']) != COMBINED_ROUTES_SHA256):
        _fault('MIGRATION_PACKAGE_INVALID')
    page_ids, map_ids, positions, urls = set(), set(), set(), set()
    package_stats = {'blocks': 0, 'cells': 0}
    for page in value['pages']:
        _exact_keys(page, {'page_id', 'map_id', 'url', 'kind', 'parent_id',
                           'position', 'name', 'h1', 'title', 'description',
                           'is_published', 'source', 'artifact', 'intro', 'blocks'})
        _exact_keys(page['source'], {'relative_path', 'sha256'})
        _exact_keys(page['artifact'], {'relative_path', 'sha256'})
        if (not _canonical_uuid(page['page_id'])
                or not _canonical_uuid(page['parent_id'])
                or page['kind'] not in ('service_section_overview',
                                        'service_detail',
                                        'service_wash_legacy_alias')
                or type(page['position']) is not int or page['position'] < 0
                or page['is_published'] is not False
                or type(page['blocks']) is not list
                or not 1 <= len(page['blocks']) <= 128
                or re.fullmatch(r'/services/[a-z0-9/-]+', page['url']) is None
                or '//' in page['url'] or '..' in page['url']):
            _fault('MIGRATION_PACKAGE_INVALID')
        for descriptor in (page['source'], page['artifact']):
            if (type(descriptor['relative_path']) is not str
                    or re.fullmatch(r'[a-z0-9_./-]+', descriptor['relative_path']) is None
                    or descriptor['relative_path'].startswith('/')
                    or '..' in descriptor['relative_path']
                    or re.fullmatch(r'[a-f0-9]{64}', descriptor['sha256']) is None):
                _fault('MIGRATION_PACKAGE_INVALID')
        for field in ('name', 'h1', 'title', 'intro'):
            _combined_text(page[field])
        _combined_text(page['description'], empty=True)
        identity = page['page_id']; position = (page['parent_id'], page['position'])
        if (identity in page_ids or page['map_id'] in map_ids
                or position in positions or page['url'] in urls):
            _fault('MIGRATION_PACKAGE_INVALID')
        page_ids.add(identity); map_ids.add(page['map_id'])
        positions.add(position); urls.add(page['url'])
        page_stats = {
            'plain': sum(len(page[field].encode('utf-8'))
                         for field in ('name', 'h1', 'title', 'description', 'intro')),
            'blocks': 0, 'items': 0, 'sections': 0, 'tables': 0, 'cells': 0,
        }
        for block in page['blocks']:
            _validate_combined_block(block, map_id=page['map_id'])
            block_stats = _combined_block_stats(block)
            for key in page_stats:
                page_stats[key] += block_stats[key]
            if block.get('type') == 'table':
                cells = len(block['header']) + sum(len(row) for row in block['rows'])
                if cells > 2048:
                    _fault('MIGRATION_PACKAGE_INVALID')
        _combined_enforce_page_caps(page_stats)
        package_stats['blocks'] += page_stats['blocks']
        package_stats['cells'] += page_stats['cells']
    _combined_enforce_package_caps(package_stats)
    route_targets = set()
    route_map_ids = set()
    route_counts = {page_id: 0 for page_id in page_ids}
    page_by_id = {page['page_id']: page for page in value['pages']}
    for route in value['routes']:
        _exact_keys(route, {'map_id', 'target', 'kind', 'is_legacy', 'page_id'})
        page = page_by_id.get(route['page_id'])
        expected_map = (page is not None and (
            route['map_id'] == page['map_id']
            if route['kind'] == 'primary'
            else route['map_id'] == 'MAP-088' and page['map_id'] == 'MAP-115'))
        if (not expected_map
                or route['kind'] not in ('primary', 'alias')
                or route['is_legacy'] is not True
                or re.fullmatch(r'/services/[a-z0-9/-]+', route['target']) is None
                or route['target'] in route_targets
                or route['map_id'] in route_map_ids):
            _fault('MIGRATION_PACKAGE_INVALID')
        route_targets.add(route['target']); route_map_ids.add(route['map_id'])
        route_counts[route['page_id']] += 1
    primary = {route['page_id']: route['target'] for route in value['routes']
               if route['kind'] == 'primary'}
    if (len(primary) != 24
            or any(primary.get(page['page_id']) != page['url'] for page in value['pages'])
            or sorted(route_counts.values()) != [1] * 23 + [2]):
        _fault('MIGRATION_PACKAGE_INVALID')
    return value


def _snapshot(page):
    def escaped_text(value):
        return escape(value, quote=False).replace('\u00a0', '&nbsp;')

    base = initial_snapshot(page['kind'], h1=page['h1'],
                            title=page['title']).data(page['kind'])
    if page['blocks']:
        rendered = []
        for block in page['blocks']:
            if block['type'] == 'paragraph':
                rendered.append('<p>' + '<br>'.join(
                    escaped_text(segment) for segment in block['segments'])
                    + '</p>')
            elif block['type'] == 'unordered_list':
                rendered.append('<ul>' + ''.join(
                    '<li>' + escaped_text(item) + '</li>'
                    for item in block['items']) + '</ul>')
            else:
                _fault('MIGRATION_PACKAGE_INVALID')
        main_text = ''.join(rendered)
        if restricted_clean(main_text) != main_text:
            _fault('MIGRATION_PACKAGE_INVALID')
        base['main_text'] = main_text
    base['description'] = page['description']
    return schema.Snapshot.trusted(base, page['kind'])


def _services_snapshot(page):
    rendered = []
    for group in page['groups']:
        rendered.append(
            '<h2><a href="' + escape(group['href'], quote=True) + '"><strong>'
            + escape(group['name'], quote=False) + '</strong></a></h2><ul>')
        for item in group['items']:
            rendered.append(
                '<li><a href="' + escape(item['href'], quote=True) + '"><strong>'
                + escape(item['name'], quote=False) + '</strong></a></li>')
        rendered.append('</ul>')
    main_text = ''.join(rendered)
    if restricted_clean(main_text) != main_text:
        _fault('MIGRATION_PACKAGE_INVALID')
    base = initial_snapshot(
        page['kind'], h1=page['h1'], title=page['title']).data(page['kind'])
    base['main_text'] = main_text
    base['description'] = page['description']
    return schema.Snapshot.trusted(base, page['kind'])


def _owner():
    rows = list(UserProfile.objects.select_for_update().select_related('user').filter(
        role=UserProfile.Role.OWNER, user__username='nesadmin',
        user__is_active=True))
    if len(rows) != 1:
        raise PermissionDenied('AUTH_OWNER_REQUIRED')
    return rows[0].user


def _identity():
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database(), current_user')
        if cursor.fetchone() != ('estakada_foundation_unit', 'app_migrator'):
            _fault('MIGRATION_APPLY_DISABLED')


def _expected_payload(page):
    return _snapshot(page).data(page['kind'])


def _services_payload(page):
    return _services_snapshot(page).data(page['kind'])


def _service_root_payload(page):
    main_text = '<ul>' + ''.join(
        '<li><a href="' + escape(tile['href'], quote=True) + '"><strong>'
        + escape(tile['name'], quote=False) + '</strong></a></li>'
        for tile in page['tiles']) + '</ul>'
    if restricted_clean(main_text) != main_text:
        _fault('MIGRATION_PACKAGE_INVALID')
    payload = initial_snapshot(
        page['kind'], h1=page['h1'], title=page['title']).data(page['kind'])
    payload['main_text'] = main_text
    payload['description'] = page['description']
    return schema.Snapshot.trusted(payload, page['kind']).data(page['kind'])


def _service_detail_payload(page):
    def escaped_text(value):
        try:
            schema.text(value, multiline=False)
        except ValidationError:
            _fault('MIGRATION_PACKAGE_INVALID')
        return escape(value, quote=False)

    def render_segments(segments):
        rendered = []
        for segment in segments:
            value = escaped_text(segment['text'])
            rendered.append('<strong>' + value + '</strong>'
                            if segment['strong'] else value)
        return ''.join(rendered)

    intro = '<p>' + escaped_text(page['intro']) + '</p>'
    rendered = []
    for block in page['blocks']:
        if block['type'] == 'heading':
            rendered.append('<h2>' + escaped_text(block['text']) + '</h2>')
        elif block['type'] == 'paragraph':
            rendered.append('<p>' + render_segments(block['segments']) + '</p>')
        elif block['type'] in ('unordered_list', 'ordered_list'):
            tag = 'ul' if block['type'] == 'unordered_list' else 'ol'
            rendered.append('<' + tag + '>' + ''.join(
                '<li>' + render_segments(item) + '</li>'
                for item in block['items']) + '</' + tag + '>')
        else:
            _fault('MIGRATION_PACKAGE_INVALID')
    main = ''.join(rendered)
    if restricted_clean(intro) != intro or restricted_clean(main) != main:
        _fault('MIGRATION_PACKAGE_INVALID')
    payload = initial_snapshot(
        page['kind'], h1=page['h1'], title=page['title']).data(page['kind'])
    payload['intro_text'] = intro
    payload['main_text'] = main
    payload['description'] = page['description']
    return schema.Snapshot.trusted(payload, page['kind']).data(page['kind'])


def _combined_payload(page, infographic=None):
    def render_segments(segments):
        return ''.join(
            ('<strong>' + escape(segment['text'], quote=False) + '</strong>')
            if segment['strong'] else escape(segment['text'], quote=False)
            for segment in segments)

    def render_list(block):
        tag = 'ul' if block['type'] == 'unordered_list' else 'ol'
        items = []
        for item in block['items']:
            children = ''.join(render_list(child)
                               for child in item.get('children', []))
            items.append('<li>' + render_segments(item['segments'])
                         + children + '</li>')
        return '<' + tag + '>' + ''.join(items) + '</' + tag + '>'

    def render_block(block):
        kind = block['type']
        if kind == 'heading':
            return '<h2>' + escape(block['text'], quote=False) + '</h2>'
        if kind == 'paragraph':
            return '<p>' + render_segments(block['segments']) + '</p>'
        if kind in ('unordered_list', 'ordered_list'):
            return render_list(block)
        if kind == 'ordered_sections':
            return '<ol>' + ''.join(
                '<li><strong>' + escape(item['heading'], quote=False)
                + '</strong>' + ''.join(render_block(child)
                                         for child in item['blocks']) + '</li>'
                for item in block['items']) + '</ol>'
        if kind == 'table':
            caption = ('' if block['caption'] is None else
                       '<caption>' + render_segments(block['caption']) + '</caption>')

            def cell_html(cell, tag):
                attrs = ''
                if cell['rowspan'] != 1:
                    attrs += ' rowspan="' + str(cell['rowspan']) + '"'
                if cell['colspan'] != 1:
                    attrs += ' colspan="' + str(cell['colspan']) + '"'
                if cell['scope'] is not None:
                    attrs += ' scope="' + cell['scope'] + '"'
                text = escape(cell['text'], quote=False)
                if cell['strong']:
                    text = '<strong>' + text + '</strong>'
                return '<' + tag + attrs + '>' + text + '</' + tag + '>'

            header = '<thead><tr>' + ''.join(
                cell_html(cell, 'th') for cell in block['header']) + '</tr></thead>'
            rows = '<tbody>' + ''.join(
                '<tr>' + ''.join(cell_html(cell, 'td') for cell in row) + '</tr>'
                for row in block['rows']) + '</tbody>'
            return '<table>' + caption + header + rows + '</table>'
        _fault('MIGRATION_PACKAGE_INVALID')

    intro = '<p>' + escape(page['intro'], quote=False) + '</p>'
    main = ''.join(render_block(block) for block in page['blocks'])
    _combined_enforce_rendered_caps(
        page_bytes=len(intro.encode('utf-8')) + len(main.encode('utf-8')))
    if (restricted_clean(intro) != intro
            or restricted_clean(main) != main):
        _fault('MIGRATION_PACKAGE_INVALID')
    payload = initial_snapshot(
        page['kind'], h1=page['h1'], title=page['title']).data(page['kind'])
    payload['intro_text'] = intro
    payload['main_text'] = main
    payload['description'] = page['description']
    if infographic is not None and page['map_id'] == infographic['binding']['map_id']:
        row = infographic['media']
        if (page['page_id'] != infographic['binding']['page_id']
                or page['url'] != infographic['binding']['url']):
            _fault('MIGRATION_PACKAGE_INVALID')
        payload['embedded_images'] = [{
            'id': row['image_id'], 'asset_id': row['asset_id'],
            'alt': row['alt'], 'alignment': row['alignment'],
            'width_px': row['width'], 'height_px': row['height'],
        }]
        payload['layout'].insert(1, {
            'id': infographic['binding']['block_id'], 'kind': 'image',
            'image_id': row['image_id'],
        })
    return schema.Snapshot.trusted(payload, page['kind']).data(page['kind'])


def _diagnostics_payload(page):
    payload = _service_detail_payload(page)
    table = page.get('source_table')
    if table is None:
        return payload
    headers = table['headers']
    rendered = [
        '<table><thead><tr><th scope="col">',
        escape(headers[0], quote=False),
        '</th><th scope="col">',
        escape(headers[1], quote=False),
        '</th></tr></thead><tbody>',
    ]
    for row in table['rows']:
        label = escape(row['label'], quote=False)
        if row['kind'] == 'category':
            rendered.extend(('<tr><td colspan="2"><strong>', label,
                             '</strong></td></tr>'))
        elif row['kind'] == 'service':
            rendered.extend(('<tr><td>', label, '</td><td>',
                             escape(row['price'], quote=False), '</td></tr>'))
        else:
            _fault('MIGRATION_PACKAGE_INVALID')
    rendered.append('</tbody></table>')
    main_text = ''.join(rendered) + payload['main_text']
    if restricted_clean(main_text) != main_text:
        _fault('MIGRATION_PACKAGE_INVALID')
    payload['main_text'] = main_text
    return schema.Snapshot.trusted(payload, page['kind']).data(page['kind'])


def _leading_price_payload(page):
    payload = _service_detail_payload(page)
    namespace = UUID(page['page_id'])
    column_id = str(uuid5(namespace, 'price-column:0'))
    rows = []
    for index, source in enumerate(page['price_rows']):
        cell = {'column_id': column_id, **source['cell']}
        rows.append({
            'id': str(uuid5(namespace, 'price-row:' + str(index))),
            'label': source['label'],
            'cells': [cell],
        })
    payload['price'] = {
        'columns': [{'id': column_id, 'label': 'Цена, руб.'}],
        'rows': rows,
    }
    if [node['kind'] for node in payload['layout']] != ['text', 'text', 'price']:
        _fault('MIGRATION_PACKAGE_INVALID')
    payload['layout'] = [payload['layout'][0], payload['layout'][2],
                         payload['layout'][1]]
    return schema.Snapshot.trusted(payload, page['kind']).data(page['kind'])


def _parent_payload():
    return initial_snapshot(
        'home', h1='АВТОТЕХЦЕНТР ЭСТАКАДА',
        title='Главная | Автосервис «Эстакада»').data('home')


def _migration_events(page_id):
    return AuditEvent.objects.filter(
        code='MIGRATION_PAGE_IMPORTED', object_ref='uuid:' + str(page_id))


def _preflight_absent(pages):
    page_ids = [UUID(page['page_id']) for page in pages]
    urls = [page['url'] for page in pages]
    if (Page.objects.filter(pk__in=page_ids).exists()
            or Route.objects.filter(pk__in=page_ids).exists()
            or IdentityReservation.objects.filter(pk__in=page_ids).exists()
            or Route.objects.filter(target__in=urls).exists()):
        _fault('MIGRATION_EXISTING_CONFLICT')
    for page in pages:
        if Page.objects.filter(parent_id=page['parent_id'],
                               position=page['position']).exists():
            _fault('MIGRATION_EXISTING_CONFLICT')
        if _migration_events(page['page_id']).exists():
            _fault('MIGRATION_EXISTING_CONFLICT')


def _create_aggregate(page_data, actor, payload, routes=None):
    page = Page.objects.create(
        id=UUID(page_data['page_id']), name=page_data['name'],
        kind=page_data['kind'], parent_id=page_data['parent_id'],
        position=page_data['position'], is_published=False)
    if routes is None:
        routes = [{'target': page_data['url'], 'kind': Route.Kind.PRIMARY,
                   'is_legacy': True}]
    for route in routes:
        Route.objects.create(
            page=page, target=route['target'], kind=route['kind'],
            is_legacy=route['is_legacy'])
    revision = engine.new_revision(page, None, payload, PageRevision.Kind.INITIAL,
                                   actor)
    PageContentState.objects.create(
        page=page, current_revision=revision, sequence=1)
    instant = engine.now()
    draft = OwnerDraft.objects.create(
        page=page, revision=1, base_revision=revision, payload=payload,
        payload_hash=schema.digest(payload), author_id=actor.pk,
        created_at=instant, updated_at=instant)
    VersionBasePin.objects.create(
        revision=revision, holder_kind='owner_draft', holder_id=draft.pk)
    engine.sync_usage(AssetUsage.Kind.CURRENT_PAGE, page.pk, payload)
    engine.sync_usage(AssetUsage.Kind.DRAFT, draft.pk, payload)
    record_event(
        category=Category.PAGES_LINKS,
        event_code='MIGRATION_PAGE_IMPORTED', level=Level.INFO,
        source=Source.APPLICATION, result=Result.SUCCESS,
        actor_id=actor.pk, object_kind='page', object_ref=page.pk)


def _exact_event(page_id, actor_id):
    rows = list(_migration_events(page_id))
    if len(rows) != 1:
        return False
    row = rows[0]
    return (row.category == Category.PAGES_LINKS
            and row.level == Level.INFO and row.source == Source.APPLICATION
            and row.result == Result.SUCCESS and row.actor_id == actor_id
            and row.object_kind == 'page'
            and row.request_id is None and row.ip_address is None
            and row.occurrence_count == 1
            and row.count_is_lower_bound is False)


def _exact_aggregate(page_data, actor, payload, routes=None):
    page_id = UUID(page_data['page_id'])
    page = Page.objects.filter(pk=page_id).first()
    if (page is None or page.name != page_data['name']
            or page.kind != page_data['kind']
            or (str(page.parent_id) if page.parent_id is not None else None)
            != page_data['parent_id']
            or page.position != page_data['position'] or page.is_published):
        return False
    actual_routes = list(Route.objects.filter(page=page).order_by('target'))
    if routes is None:
        routes = [{'target': page_data['url'], 'kind': Route.Kind.PRIMARY,
                   'is_legacy': True}]
    expected_routes = sorted(
        ((route['target'], route['kind'], route['is_legacy']) for route in routes),
        key=lambda row: row[0])
    revisions = list(PageRevision.objects.filter(page=page))
    states = list(PageContentState.objects.filter(page=page))
    drafts = list(OwnerDraft.objects.filter(page=page))
    if ([(route.target, route.kind, route.is_legacy) for route in actual_routes]
            != expected_routes or len(revisions) != 1
            or len(states) != 1 or len(drafts) != 1):
        return False
    revision, state, draft = revisions[0], states[0], drafts[0]
    if (revision.sequence != 1 or revision.kind != PageRevision.Kind.INITIAL
            or revision.schema_version != payload['schema_version']
            or revision.payload != payload
            or revision.payload_hash != schema.digest(payload)
            or revision.author_id != actor.pk or revision.source_revision_id is not None
            or state.current_revision_id != revision.pk or state.sequence != 1
            or draft.revision != 1 or draft.base_revision_id != revision.pk
            or draft.payload != payload or draft.payload_hash != schema.digest(payload)
            or draft.author_id != actor.pk):
        return False
    metadata = list(RevisionMetadata.objects.filter(revision=revision))
    pins = list(VersionBasePin.objects.filter(
        Q(revision=revision)
        | Q(holder_kind='owner_draft', holder_id=draft.pk)))
    reservations = list(IdentityReservation.objects.filter(
        pk__in=[revision.pk, draft.pk]).order_by('kind', 'id'))
    reservation_values = {(row.pk, row.kind) for row in reservations}
    usages = {(row.kind, row.consumer_id, row.slot, row.asset_id)
              for row in AssetUsage.objects.filter(
                  consumer_id__in=[page_id, revision.pk, draft.pk])}
    wanted = set()
    for kind, consumer_id in (
            (AssetUsage.Kind.CURRENT_PAGE, page_id),
            (AssetUsage.Kind.ORDINARY_VERSION, revision.pk),
            (AssetUsage.Kind.DRAFT, draft.pk)):
        wanted.update((kind, consumer_id, slot, UUID(asset_id))
                      for slot, asset_id in schema.asset_slots(payload).items())
    if (len(metadata) != 1 or metadata[0].generation != 1
            or metadata[0].name != '' or metadata[0].comment != ''
            or metadata[0].manual_date is not None
            or len(pins) != 1 or pins[0].holder_kind != 'owner_draft'
            or pins[0].holder_id != draft.pk
            or reservation_values != {
                (revision.pk, 'pagerevision'), (draft.pk, 'ownerdraft')}
            or IdentityReservation.objects.filter(pk=page_id).exists()
            or RevisionProtection.objects.filter(revision=revision).exists()
            or PageGrant.objects.filter(page=page).exists()
            or RestoreStage.objects.filter(page=page).exists()
            or OperationReceipt.objects.filter(page_id=page_id).exists()
            or usages != wanted
            or not _exact_event(page_id, actor.pk)):
        return False
    return True


def apply_articles_slice():
    """Create all reviewed hidden aggregates, or verify an exact full replay."""
    _enabled()
    package = _read_package()
    with transaction.atomic():
        _identity()
        lock_content('default')
        lock_auth()
        actor = _owner()
        page_ids = [UUID(page['page_id']) for page in package['pages']]
        existing = list(Page.objects.select_for_update().filter(pk__in=page_ids))
        page_count = len(package['pages'])
        if len(existing) == page_count:
            if not all(_exact_aggregate(
                    page, actor, _expected_payload(page))
                    for page in package['pages']):
                _fault('MIGRATION_EXISTING_CONFLICT')
            return {'status': 'pass', 'replayed': True, 'pages': page_count,
                    'published': 0}
        if existing:
            _fault('MIGRATION_EXISTING_CONFLICT')
        _preflight_absent(package['pages'])
        for page in package['pages']:
            _create_aggregate(page, actor, _expected_payload(page))
        return {'status': 'pass', 'replayed': False, 'pages': page_count,
                'published': 0}


def apply_services_catalog():
    """Create the one reviewed hidden services catalog, or exact-replay it."""
    _enabled()
    package = _read_services_package()
    page = package['page']
    payload = _services_payload(page)
    with transaction.atomic():
        _identity()
        lock_content('default')
        lock_auth()
        actor = _owner()
        list(Page.objects.select_for_update().filter(
            pk=PARENT_DESCRIPTOR['page_id']))
        if not _exact_aggregate(
                PARENT_DESCRIPTOR, actor, _parent_payload()):
            _fault('MIGRATION_PARENT_REQUIRED')
        existing = list(Page.objects.select_for_update().filter(
            pk=page['page_id']))
        if len(existing) == 1:
            if not _exact_aggregate(page, actor, payload):
                _fault('MIGRATION_EXISTING_CONFLICT')
            return {'status': 'pass', 'replayed': True, 'pages': 1,
                    'published': 0}
        if existing:
            _fault('MIGRATION_EXISTING_CONFLICT')
        _preflight_absent([page])
        _create_aggregate(page, actor, payload)
        return {'status': 'pass', 'replayed': False, 'pages': 1,
                'published': 0}


def apply_service_roots():
    """Create both reviewed hidden root catalogs, or exact-replay both."""
    _enabled()
    package = _read_service_roots_package()
    parent_package = _read_services_package()
    pages = package['pages']
    payloads = [_service_root_payload(page) for page in pages]
    with transaction.atomic():
        _identity()
        lock_content('default')
        lock_auth()
        actor = _owner()
        list(Page.objects.select_for_update().filter(pk=SERVICES_PAGE['page_id']))
        if not _exact_aggregate(
                SERVICES_PAGE, actor, _services_payload(parent_package['page'])):
            _fault('MIGRATION_PARENT_REQUIRED')
        page_ids = [UUID(page['page_id']) for page in pages]
        existing = list(Page.objects.select_for_update().filter(pk__in=page_ids))
        if len(existing) == 2:
            if not all(_exact_aggregate(page, actor, payload)
                       for page, payload in zip(pages, payloads, strict=True)):
                _fault('MIGRATION_EXISTING_CONFLICT')
            return {'status': 'pass', 'replayed': True, 'pages': 2,
                    'published': 0}
        if existing:
            _fault('MIGRATION_EXISTING_CONFLICT')
        _preflight_absent(pages)
        for page, payload in zip(pages, payloads, strict=True):
            _create_aggregate(page, actor, payload)
        return {'status': 'pass', 'replayed': False, 'pages': 2,
                'published': 0}


def apply_service_details():
    """Create all ten reviewed hidden service details, or exact-replay all."""
    _enabled()
    parent_package = _read_service_roots_package()
    package = _read_service_details_package(parent_package)
    pages = package['pages']
    payloads = [_service_detail_payload(page) for page in pages]
    with transaction.atomic():
        _identity()
        lock_content('default')
        lock_auth()
        actor = _owner()
        parent_ids = [UUID(page['page_id']) for page in parent_package['pages']]
        list(Page.objects.select_for_update().filter(pk__in=parent_ids))
        if not all(_exact_aggregate(parent, actor, _service_root_payload(parent))
                   for parent in parent_package['pages']):
            _fault('MIGRATION_PARENT_REQUIRED')
        parent_by_id = {page['page_id']: page for page in parent_package['pages']}
        for page in pages:
            parent = parent_by_id.get(page['parent_id'])
            tile = (parent['tiles'][page['position']] if parent is not None else None)
            if tile != {'name': page['name'], 'href': page['url']}:
                _fault('MIGRATION_PARENT_REQUIRED')
        page_ids = [UUID(page['page_id']) for page in pages]
        existing = list(Page.objects.select_for_update().filter(pk__in=page_ids))
        if len(existing) == len(pages):
            if not all(_exact_aggregate(page, actor, payload)
                       for page, payload in zip(pages, payloads, strict=True)):
                _fault('MIGRATION_EXISTING_CONFLICT')
            return {'status': 'pass', 'replayed': True, 'pages': len(pages),
                    'published': 0}
        if existing:
            _fault('MIGRATION_EXISTING_CONFLICT')
        _preflight_absent(pages)
        for page, payload in zip(pages, payloads, strict=True):
            _create_aggregate(page, actor, payload)
        return {'status': 'pass', 'replayed': False, 'pages': len(pages),
                'published': 0}


def apply_leading_price_details():
    """Create the five reviewed hidden price-bearing details, or exact-replay all."""
    _enabled()
    parent_package = _read_service_roots_package()
    package = _read_leading_price_package(parent_package)
    pages = package['pages']
    payloads = [_leading_price_payload(page) for page in pages]
    parents = [page for page in parent_package['pages']
               if page['map_id'] == 'MAP-012']
    if len(parents) != 1:
        _fault('MIGRATION_PARENT_REQUIRED')
    parent = parents[0]
    with transaction.atomic():
        _identity()
        lock_content('default')
        lock_auth()
        actor = _owner()
        list(Page.objects.select_for_update().filter(pk=parent['page_id']))
        if not _exact_aggregate(parent, actor, _service_root_payload(parent)):
            _fault('MIGRATION_PARENT_REQUIRED')
        for page in pages:
            tile = parent['tiles'][page['position']]
            if tile != {'name': page['name'], 'href': page['url']}:
                _fault('MIGRATION_PARENT_REQUIRED')
        page_ids = [UUID(page['page_id']) for page in pages]
        existing = list(Page.objects.select_for_update().filter(pk__in=page_ids))
        if len(existing) == len(pages):
            if not all(_exact_aggregate(page, actor, payload)
                       for page, payload in zip(pages, payloads, strict=True)):
                _fault('MIGRATION_EXISTING_CONFLICT')
            return {'status': 'pass', 'replayed': True, 'pages': len(pages),
                    'published': 0, 'price_rows': 46}
        if existing:
            _fault('MIGRATION_EXISTING_CONFLICT')
        _preflight_absent(pages)
        for page, payload in zip(pages, payloads, strict=True):
            _create_aggregate(page, actor, payload)
        return {'status': 'pass', 'replayed': False, 'pages': len(pages),
                'published': 0, 'price_rows': 46}


def apply_diagnostics_branch():
    """Create the reviewed hidden diagnostics parent and nine children."""
    _enabled()
    catalog_package = _read_services_package()
    package = _read_diagnostics_package(catalog_package)
    pages = package['pages']
    payloads = [_diagnostics_payload(page) for page in pages]
    with transaction.atomic():
        _identity()
        lock_content('default')
        lock_auth()
        actor = _owner()
        catalog = catalog_package['page']
        list(Page.objects.select_for_update().filter(pk=catalog['page_id']))
        if not _exact_aggregate(catalog, actor, _services_payload(catalog)):
            _fault('MIGRATION_PARENT_REQUIRED')
        group = catalog['groups'][3]
        parent = pages[0]
        if ({'name': group['name'], 'href': group['href']}
                != {'name': parent['name'], 'href': parent['url']}):
            _fault('MIGRATION_PARENT_REQUIRED')
        for page in pages[1:]:
            tile = group['items'][page['position']]
            if tile != {'name': page['name'], 'href': page['url']}:
                _fault('MIGRATION_PARENT_REQUIRED')
        page_ids = [UUID(page['page_id']) for page in pages]
        existing = list(Page.objects.select_for_update().filter(pk__in=page_ids))
        if len(existing) == len(pages):
            expected_children = {
                (UUID(page['page_id']), page['position']) for page in pages[1:]
            }
            actual_children = set(Page.objects.select_for_update().filter(
                parent_id=parent['page_id']).values_list('pk', 'position'))
            if actual_children != expected_children:
                _fault('MIGRATION_EXISTING_CONFLICT')
            if not all(_exact_aggregate(page, actor, payload)
                       for page, payload in zip(pages, payloads, strict=True)):
                _fault('MIGRATION_EXISTING_CONFLICT')
            return {'status': 'pass', 'replayed': True, 'pages': len(pages),
                    'published': 0, 'table_rows': 6}
        if existing:
            _fault('MIGRATION_EXISTING_CONFLICT')
        _preflight_absent(pages)
        for page, payload in zip(pages, payloads, strict=True):
            _create_aggregate(page, actor, payload)
        return {'status': 'pass', 'replayed': False, 'pages': len(pages),
                'published': 0, 'table_rows': 6}


def apply_planned_maintenance():
    """Create the reviewed hidden maintenance parent and eight children."""
    _enabled()
    catalog_package = _read_services_package()
    package = _read_planned_maintenance_package(catalog_package)
    pages = package['pages']
    payloads = [_service_detail_payload(page) for page in pages]
    with transaction.atomic():
        _identity()
        lock_content('default')
        lock_auth()
        actor = _owner()
        catalog = catalog_package['page']
        list(Page.objects.select_for_update().filter(pk=catalog['page_id']))
        if not _exact_aggregate(catalog, actor, _services_payload(catalog)):
            _fault('MIGRATION_PARENT_REQUIRED')
        group = catalog['groups'][1]
        parent = pages[0]
        if ({'name': group['name'], 'href': group['href']}
                != {'name': parent['name'], 'href': parent['url']}):
            _fault('MIGRATION_PARENT_REQUIRED')
        for page in pages[1:]:
            if (group['items'][page['position']]
                    != {'name': page['name'], 'href': page['url']}):
                _fault('MIGRATION_PARENT_REQUIRED')
        page_ids = [UUID(page['page_id']) for page in pages]
        existing = list(Page.objects.select_for_update().filter(pk__in=page_ids))
        if Page.objects.filter(parent_id=parent['page_id'], position=2).exists():
            _fault('MIGRATION_EXISTING_CONFLICT')
        if len(existing) == len(pages):
            if not all(_exact_aggregate(page, actor, payload)
                       for page, payload in zip(pages, payloads, strict=True)):
                _fault('MIGRATION_EXISTING_CONFLICT')
            return {'status': 'pass', 'replayed': True, 'pages': len(pages),
                    'published': 0}
        if existing:
            _fault('MIGRATION_EXISTING_CONFLICT')
        _preflight_absent(pages)
        for page, payload in zip(pages, payloads, strict=True):
            _create_aggregate(page, actor, payload)
        return {'status': 'pass', 'replayed': False, 'pages': len(pages),
                'published': 0}


def _combined_parent_context():
    catalog_package = _read_services_package()
    roots_package = _read_service_roots_package()
    planned_package = _read_planned_maintenance_package(catalog_package)
    diagnostics_package = _read_diagnostics_package(catalog_package)
    catalog = catalog_package['page']
    roots = {page['map_id']: page for page in roots_package['pages']}
    planned = {page['map_id']: page for page in planned_package['pages']}
    diagnostics = {page['map_id']: page for page in diagnostics_package['pages']}
    contracts = {
        catalog['page_id']: (catalog, _services_payload(catalog)),
        roots['MAP-012']['page_id']:
            (roots['MAP-012'], _service_root_payload(roots['MAP-012'])),
        roots['MAP-014']['page_id']:
            (roots['MAP-014'], _service_root_payload(roots['MAP-014'])),
        planned['MAP-011']['page_id']:
            (planned['MAP-011'], _service_detail_payload(planned['MAP-011'])),
        diagnostics['MAP-013']['page_id']:
            (diagnostics['MAP-013'], _diagnostics_payload(diagnostics['MAP-013'])),
    }
    return catalog, roots, contracts


def _combined_expected_link(page, catalog, roots):
    if page['map_id'] == 'MAP-010':
        group = catalog['groups'][0]
        return {'name': group['name'], 'href': group['href']}
    if page['parent_id'] == next(
            candidate['page_id'] for candidate in roots.values()
            if candidate['map_id'] == 'MAP-014'):
        if page['position'] in (5, 6):
            return None
        return roots['MAP-014']['tiles'][page['position']]
    if page['parent_id'] == roots['MAP-012']['page_id']:
        return roots['MAP-012']['tiles'][page['position']]
    if page['parent_id'] == catalog['page_id'] and page['map_id'] == 'MAP-115':
        return None
    if page['parent_id'] == catalog['page_id']:
        return None
    group_by_parent = {
        catalog['groups'][1]['href']: catalog['groups'][1],
        catalog['groups'][3]['href']: catalog['groups'][3],
    }
    for group in group_by_parent.values():
        if page['url'] in {item['href'] for item in group['items']}:
            return group['items'][page['position']]
    return None


def _combined_infographic_preflight(package, storage):
    row = package['media']
    expected = {'sha256': row['sha256'], 'byte_size': row['bytes']}
    try:
        actual = storage.manifest(row['storage_key'])
    except (OSError, ValidationError):
        _fault('MIGRATION_MEDIA_UNAVAILABLE')
    if actual != expected:
        _fault('MIGRATION_MEDIA_UNAVAILABLE')
    return schema.digest({'key': row['storage_key'], **actual})


def _combined_infographic_recapture(package, storage, evidence):
    row = package['media']
    folder = MediaFolder.objects.select_for_update().filter(
        pk=row['folder_id']).first()
    asset = Asset.objects.select_for_update().filter(pk=row['asset_id']).first()
    files = list(AssetFile.objects.select_for_update().filter(
        asset_id=row['asset_id']).order_by('pk'))
    if (folder is None or folder.path != row['folder_path'] or asset is None
            or asset.status != Asset.Status.READY
            or not _combined_infographic_exact_asset(package, asset, files)):
        _fault('MIGRATION_MEDIA_UNAVAILABLE')
    try:
        actual = storage.manifest(row['storage_key'])
    except (OSError, ValidationError):
        _fault('MIGRATION_MEDIA_UNAVAILABLE')
    if (actual != {'sha256': row['sha256'], 'byte_size': row['bytes']}
            or schema.digest({'key': row['storage_key'], **actual}) != evidence):
        _fault('MIGRATION_MEDIA_UNAVAILABLE')


def apply_combined_services(*, storage=None):
    """Create the reviewed hidden DEV-09M aggregate, or exact-replay it."""
    _enabled()
    package = _read_combined_services_package()
    infographic = _read_combined_infographic_package()
    storage = storage or MediaStorage()
    media_evidence = _combined_infographic_preflight(infographic, storage)
    catalog, roots, parent_contracts = _combined_parent_context()
    pages = package['pages']
    routes_by_page = {page['page_id']: [] for page in pages}
    for route in package['routes']:
        routes_by_page[route['page_id']].append(route)
    payloads = [_combined_payload(page, infographic) for page in pages]
    rendered_bytes = sum(
        len(payload['intro_text'].encode('utf-8'))
        + len(payload['main_text'].encode('utf-8')) for payload in payloads)
    _combined_enforce_rendered_caps(package_bytes=rendered_bytes)
    expected_links = {
        page['page_id']: _combined_expected_link(page, catalog, roots)
        for page in pages
    }
    group = catalog['groups'][0]
    for page in pages:
        if page['parent_id'] == pages[0]['page_id']:
            expected_links[page['page_id']] = group['items'][page['position']]
    for page in pages:
        link = expected_links[page['page_id']]
        if link is not None and link['href'] != page['url']:
            _fault('MIGRATION_PARENT_REQUIRED')
    with transaction.atomic():
        _identity()
        lock_content('default')
        lock_auth()
        actor = _owner()
        _combined_infographic_recapture(
            infographic, storage, media_evidence)
        parent_ids = [UUID(page_id) for page_id in parent_contracts]
        list(Page.objects.select_for_update().filter(pk__in=parent_ids))
        list(Route.objects.select_for_update().filter(page_id__in=parent_ids))
        list(PageContentState.objects.select_for_update().filter(
            page_id__in=parent_ids))
        list(PageRevision.objects.select_for_update().filter(
            page_id__in=parent_ids))
        list(Page.objects.select_for_update().filter(parent_id__in=parent_ids))
        if not all(_exact_aggregate(parent, actor, payload)
                   for parent, payload in parent_contracts.values()):
            _fault('MIGRATION_PARENT_REQUIRED')
        page_ids = [UUID(page['page_id']) for page in pages]
        existing = list(Page.objects.select_for_update().filter(pk__in=page_ids))
        if len(existing) == len(pages):
            if not all(_exact_aggregate(
                    page, actor, payload, routes_by_page[page['page_id']])
                    for page, payload in zip(pages, payloads, strict=True)):
                _fault('MIGRATION_EXISTING_CONFLICT')
            children = {(str(pk), position) for pk, position in
                        Page.objects.select_for_update().filter(
                            parent_id=pages[0]['page_id']).values_list('pk', 'position')}
            expected = {(page['page_id'], page['position']) for page in pages
                        if page['parent_id'] == pages[0]['page_id']}
            if children != expected:
                _fault('MIGRATION_EXISTING_CONFLICT')
            return {'status': 'pass', 'replayed': True, 'pages': 24,
                    'routes': 25, 'published': 0}
        if existing:
            _fault('MIGRATION_EXISTING_CONFLICT')
        _preflight_absent(pages)
        if Route.objects.filter(
                target__in=[route['target'] for route in package['routes']]).exists():
            _fault('MIGRATION_EXISTING_CONFLICT')
        for page, payload in zip(pages, payloads, strict=True):
            _create_aggregate(
                page, actor, payload, routes_by_page[page['page_id']])
        return {'status': 'pass', 'replayed': False, 'pages': 24,
                'routes': 25, 'published': 0}

"""SH07 bounded transactional-DDL calibration, NOT product quota/Apply tests."""
import base64
from contextlib import contextmanager
import hashlib
import json
import os
import random

from django.conf import settings
from django.db import connection, transaction
from django.test import TransactionTestCase


RELATIONS = (
    'es_shared_probe_revision', 'es_shared_probe_draft', 'es_shared_probe_pin',
    'es_shared_probe_receipt', 'es_shared_probe_identity', 'es_shared_probe_budget',
)
PROBE_BYTES = 32 * 1024 * 1024


class SharedQuotaTransactionalProbeTests(TransactionTestCase):
    """Own app probe DDL always rolls back; teardown flushes dedicated unit DB."""

    def setUp(self):
        self.assertEqual(os.environ.get('ESTAKADA_LOCAL_ENV'), 'test')
        self.assertEqual(os.environ.get('DJANGO_SETTINGS_MODULE'), 'estakada.settings.local_http')
        self.assertEqual(settings.ENVIRONMENT, 'test')
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertEqual(connection.settings_dict['NAME'], 'estakada_foundation_unit')
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(),current_user,current_setting('server_version'),"
                           "current_setting('block_size')::int")
            database, role, version, block_size = cursor.fetchone()
        self.assertEqual(database, 'estakada_foundation_unit')
        self.assertEqual(role, 'app_migrator')
        self.database_facts = {'version': version, 'blockSize': block_size}

    def create_relations(self):
        self.assertTrue(connection.in_atomic_block)
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout='30s'")
            cursor.execute("SET LOCAL lock_timeout='5s'")
            cursor.execute("""SELECT n.oid,n.nspowner,r.oid,
                has_schema_privilege(current_user,n.oid,'CREATE')
                FROM pg_namespace n JOIN pg_roles r ON r.rolname=current_user
                WHERE n.nspname='app'""")
            row = cursor.fetchone()
            self.assertIsNotNone(row, 'PROBE_APP_SCHEMA_MISSING')
            self.schema_oid, schema_owner, self.role_oid, can_create = row
            self.assertEqual(schema_owner, self.role_oid, 'PROBE_SCHEMA_OWNER')
            self.assertTrue(can_create, 'PROBE_SCHEMA_CREATE_DENIED')
            self.assert_no_prefix(cursor)
            self.ddl_started = True
            cursor.execute("""CREATE TABLE app.es_shared_probe_revision (
                id uuid PRIMARY KEY, kind text NOT NULL CHECK(kind IN ('header','footer')),
                sequence bigint NOT NULL, schema_version text NOT NULL,
                payload text NOT NULL, author_id bigint NOT NULL,
                created_at timestamptz NOT NULL, UNIQUE(kind,sequence)
            )""")
            cursor.execute("""CREATE TABLE app.es_shared_probe_draft (
                kind text PRIMARY KEY, base_id uuid NOT NULL
                REFERENCES app.es_shared_probe_revision(id), payload text NOT NULL
            )""")
            cursor.execute("""CREATE TABLE app.es_shared_probe_pin (
                id uuid PRIMARY KEY, revision_id uuid NOT NULL
                REFERENCES app.es_shared_probe_revision(id)
            )""")
            cursor.execute("""CREATE TABLE app.es_shared_probe_receipt (
                operation_id uuid PRIMARY KEY, revision_id uuid NOT NULL
                REFERENCES app.es_shared_probe_revision(id), fingerprint text NOT NULL
            )""")
            cursor.execute("""CREATE TABLE app.es_shared_probe_identity (
                id uuid PRIMARY KEY, purpose text NOT NULL
            )""")
            cursor.execute("""CREATE TABLE app.es_shared_probe_budget (
                singleton boolean PRIMARY KEY CHECK(singleton),
                snapshot_count bigint NOT NULL, charged_bytes bigint NOT NULL
            )""")
            cursor.execute("""SELECT c.oid,c.relname,c.relpersistence,c.reltoastrelid,
                c.relowner,c.relkind,c.relnamespace FROM pg_class c
                WHERE c.relnamespace=%s AND c.relname=ANY(%s)
                ORDER BY c.relname""", [self.schema_oid, list(RELATIONS)])
            rows = cursor.fetchall()
        self.assertEqual({row[1] for row in rows}, set(RELATIONS))
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(row[2] == 'p' and row[4] == self.role_oid
                            and row[5] == 'r' and row[6] == self.schema_oid for row in rows))
        self.own_oids = tuple(row[0] for row in rows)
        self.initial_inventory = rows

    def assert_no_prefix(self, cursor):
        cursor.execute("""SELECT count(*) FROM pg_class WHERE relnamespace=%s
            AND starts_with(relname,'es_shared_probe_')""", [self.schema_oid])
        self.assertEqual(cursor.fetchone()[0], 0, 'PROBE_PREFIX_COLLISION_OR_REMAINDER')

    @contextmanager
    def probe_relations(self):
        self.own_oids, self.ddl_started = (), False
        try:
            with transaction.atomic():
                try:
                    self.create_relations()
                    yield
                finally:
                    # Never commit experimental DDL, including successful assertions.
                    transaction.set_rollback(True)
        finally:
            if self.ddl_started:
                self.assert_rollback_cleanup()

    def sizes(self):
        # Validate every saved OID still refers to our newly created app relation.
        with connection.cursor() as cursor:
            cursor.execute("""SELECT c.oid,c.relname,c.relpersistence,c.reltoastrelid,
                c.relowner,c.relkind,c.relnamespace FROM pg_class c
                WHERE c.oid=ANY(%s) AND c.relnamespace=%s ORDER BY c.relname""",
                [list(self.own_oids), self.schema_oid])
            inventory = cursor.fetchall()
            self.assertEqual(inventory, self.initial_inventory)
            result = []
            for oid, name, persistence, toast_oid, owner, kind, namespace in inventory:
                cursor.execute("""SELECT pg_total_relation_size(%s),pg_table_size(%s),
                    pg_indexes_size(%s),pg_relation_size(%s,'main'),
                    pg_relation_size(%s,'fsm'),pg_relation_size(%s,'vm'),
                    pg_relation_size(%s,'init')""", [oid] * 7)
                total, table, indexes, main, fsm, vm, init = cursor.fetchone()
                self.assertEqual(total, table + indexes)
                self.assertGreaterEqual(table, main + fsm + vm + init)
                toast_total = 0
                if toast_oid:
                    cursor.execute("""SELECT c.relpersistence,n.nspname,c.relowner,c.relkind,
                        pg_total_relation_size(c.oid) FROM pg_class c
                        JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.oid=%s""", [toast_oid])
                    toast_persistence, toast_namespace, toast_owner, toast_kind, toast_total = cursor.fetchone()
                    self.assertEqual(toast_persistence, persistence)
                    self.assertEqual(toast_namespace, 'pg_toast')
                    self.assertEqual(toast_owner, owner)
                    self.assertEqual(toast_kind, 't')
                    self.assertGreaterEqual(table, main + fsm + vm + init + toast_total)
                result.append({'relation': name, 'oid': oid, 'total': total,
                    'tableIncludingToast': table, 'indexes': indexes,
                    'main': main, 'fsm': fsm, 'vm': vm, 'init': init,
                    'toastTotalAlreadyIncluded': toast_total})
        return {'totalBytes': sum(row['total'] for row in result), 'relations': result}

    def bounded_sizes(self):
        value = self.sizes()
        self.assertLess(value['totalBytes'], PROBE_BYTES, 'OWN_RELATION_PROBE_LIMIT')
        return value

    def manifest(self):
        digest, count = hashlib.sha256(), 0
        with connection.cursor() as cursor:
            cursor.execute("""SELECT id::text,kind,sequence,schema_version,payload,
                author_id,created_at::text FROM app.es_shared_probe_revision
                ORDER BY kind,sequence""")
            while rows := cursor.fetchmany(256):
                for row in rows:
                    wire = json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode()
                    digest.update(len(wire).to_bytes(8, 'big'))
                    digest.update(wire)
                    count += 1
        return {'count': count, 'sha256': digest.hexdigest()}

    def assert_rollback_cleanup(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_class WHERE oid=ANY(%s)", [list(self.own_oids)])
            self.assertEqual(cursor.fetchone()[0], 0)
            self.assert_no_prefix(cursor)

    def report(self, case, **facts):
        print(json.dumps({'scope': 'SH07-transactional-DDL-calibration', 'case': case,
            'database': self.database_facts, 'capBytes': PROBE_BYTES,
            'productQuotaImplemented': False, 'productApplyTested': False,
            **facts}, sort_keys=True), flush=True)

    def test_sh07_qexp001_actual_empty_relation_inventory(self):
        with self.probe_relations():
            measured = self.bounded_sizes()
            self.assertEqual(self.manifest()['count'], 0)
            self.assertGreater(measured['totalBytes'], 0)
        self.report('QEXP001-experimental-shape', measured=measured, outerRollbackCleanup=True)

    def test_sh07_qexp002_actual_10000_rows_manifest_read_stability(self):
        with self.probe_relations():
            before = self.bounded_sizes()
            self.assertLess(before['totalBytes'] + 16 * 1024 * 1024, PROBE_BYTES)
            with connection.cursor() as cursor:
                cursor.execute("""INSERT INTO app.es_shared_probe_revision
                    SELECT md5('SH07-fixed-revision-'||g)::uuid,
                        CASE WHEN g<=5000 THEN 'header' ELSE 'footer' END,
                        (g-1)%5000+1,'experimental-v1','SH07-payload-'||g,
                        1,'2026-11-01 00:00:00+00'::timestamptz
                    FROM generate_series(1,10000) AS g""")
                cursor.execute("""SELECT kind,count(*),min(sequence),max(sequence),
                    count(DISTINCT sequence) FROM app.es_shared_probe_revision
                    GROUP BY kind ORDER BY kind""")
                counts = cursor.fetchall()
            self.assertEqual(counts, [('footer', 5000, 1, 5000, 5000), ('header', 5000, 1, 5000, 5000)])
            first = self.manifest()
            self.assertEqual(first['count'], 10000)
            measured = self.bounded_sizes()
            second = self.manifest()
            self.assertEqual(second, first)
        self.report('QEXP002-count-only', before=before, measured=measured,
                    manifest=first, repeatedReadUnchanged=True, outerRollbackCleanup=True,
                    admission10001Tested=False)

    def test_sh07_qexp006_rollback_keeps_physical_growth(self):
        payload = base64.b64encode(random.Random(730061).randbytes(786432)).decode('ascii')
        self.assertEqual(len(payload.encode()), 1048576)
        with self.probe_relations():
            before_manifest = self.manifest()
            before = self.bounded_sizes()
            self.assertLess(before['totalBytes'] + 16 * 1024 * 1024, PROBE_BYTES)
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("""INSERT INTO app.es_shared_probe_revision VALUES
                        ('00000000-0000-0000-0000-000000730061','header',1,
                        'experimental-v1',%s,1,'2026-11-01 00:00:00+00')""", [payload])
                during = self.bounded_sizes()
                self.assertEqual(self.manifest()['count'], 1)
                self.assertGreater(during['totalBytes'], before['totalBytes'])
                transaction.set_rollback(True)
            after_manifest = self.manifest()
            after = self.bounded_sizes()
            self.assertEqual(after_manifest, before_manifest)
            self.assertGreater(after['totalBytes'], before['totalBytes'])
            self.assertGreaterEqual(after['totalBytes'], during['totalBytes'])
        self.report('QEXP006-insert-rollback-only', before=before, during=during,
                    after=after, manifest=after_manifest, logicalRollback=True,
                    physicalGrowthRetained=True, outerRollbackCleanup=True,
                    payloadBytes=len(payload), payloadSha256=hashlib.sha256(payload.encode()).hexdigest())

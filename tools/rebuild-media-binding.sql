BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='2000ms';
SET LOCAL lock_timeout='250ms';
SET LOCAL idle_in_transaction_session_timeout='5000ms';
DO $$
BEGIN
  IF current_user <> 'estakada_rebuild_reader'
     OR current_database() <> 'estakada_foundation'
     OR current_setting('transaction_read_only') <> 'on'
     OR current_setting('transaction_isolation') <> 'repeatable read'
     OR NOT COALESCE((SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()),false)
  THEN RAISE EXCEPTION 'identity'; END IF;
END $$;
WITH
candidate(sha256,byte_size,cohort) AS (
  VALUES __CANDIDATE_VALUES__
),
selected_current AS (
  SELECT s.page_id,r.id,r.sequence
  FROM app.page_versions_pagecontentstate s
  JOIN app.page_versions_pagerevision r ON r.id=s.current_revision_id AND r.page_id=s.page_id
  WHERE r.kind IN ('initial','automatic')
),
selected_previous AS (
  SELECT c.page_id,p.id
  FROM selected_current c
  LEFT JOIN LATERAL (
    SELECT r.id
    FROM app.page_versions_pagerevision r
    WHERE r.page_id=c.page_id AND r.sequence<c.sequence AND r.kind IN ('initial','automatic')
    ORDER BY r.sequence DESC LIMIT 1
  ) p ON true
  WHERE p.id IS NOT NULL
),
selected_revision AS (
  SELECT id FROM selected_current UNION SELECT id FROM selected_previous
),
current_shared AS (
  SELECT r.id
  FROM app.shared_content_sharedblock b
  JOIN app.shared_content_sharedrevision r ON r.id=b.current_revision_id AND r.block_id=b.id
),
usage_class AS (
  SELECT u.id,u.asset_id,u.kind,
    CASE
      WHEN u.kind='current_page' AND p.id IS NOT NULL THEN 'eligible'
      WHEN u.kind IN ('ordinary_version','stable_version') AND sr.id IS NOT NULL THEN 'eligible'
      WHEN u.kind='shared_block' AND cs.id IS NOT NULL THEN 'eligible'
      WHEN u.kind IN ('ordinary_version','stable_version') AND r.id IS NOT NULL THEN 'excluded'
      WHEN u.kind='shared_block' AND sh.id IS NOT NULL THEN 'excluded'
      WHEN u.kind IN ('draft','retained_html') THEN 'excluded'
      ELSE 'unclassified'
    END AS class,
    CASE
      WHEN u.kind='current_page' AND p.id IS NULL THEN 1
      WHEN u.kind IN ('ordinary_version','stable_version') AND r.id IS NULL THEN 1
      WHEN u.kind='shared_block' AND sh.id IS NULL THEN 1
      ELSE 0
    END AS orphan
  FROM app.media_library_assetusage u
  LEFT JOIN app.content_page p ON u.kind='current_page' AND p.id=u.consumer_id
  LEFT JOIN app.page_versions_pagerevision r
    ON u.kind IN ('ordinary_version','stable_version') AND r.id=u.consumer_id
  LEFT JOIN selected_revision sr
    ON u.kind IN ('ordinary_version','stable_version') AND sr.id=u.consumer_id
  LEFT JOIN app.shared_content_sharedrevision sh
    ON u.kind='shared_block' AND sh.id=u.consumer_id
  LEFT JOIN current_shared cs ON u.kind='shared_block' AND cs.id=u.consumer_id
),
file_match AS (
  SELECT f.id,f.asset_id,f.kind,f.key,f.sha256,f.byte_size,a.status,a.is_legacy,a.source_sha256,
    c.sha256 AS candidate_sha,c.cohort
  FROM app.media_library_assetfile f
  JOIN app.media_library_asset a ON a.id=f.asset_id
  LEFT JOIN candidate c ON c.sha256=f.sha256 AND c.byte_size=f.byte_size
),
duplicate_matched_pair AS (
  SELECT sha256,byte_size
  FROM file_match
  WHERE candidate_sha IS NOT NULL
  GROUP BY sha256,byte_size HAVING count(*)>1
),
duplicate_matched_file AS (
  SELECT f.*
  FROM file_match f
  JOIN duplicate_matched_pair d ON d.sha256=f.sha256 AND d.byte_size=f.byte_size
),
unmatched_db_pair AS (
  SELECT sha256,byte_size
  FROM file_match
  WHERE candidate_sha IS NULL
  GROUP BY sha256,byte_size
),
unmatched_db_file AS (
  SELECT * FROM file_match WHERE candidate_sha IS NULL
),
facts(query_id,value) AS (
  SELECT 'COUNT-ASSET',count(*)::bigint FROM app.media_library_asset UNION ALL
  SELECT 'COUNT-ASSETFILE',count(*) FROM app.media_library_assetfile UNION ALL
  SELECT 'COUNT-ASSETUSAGE',count(*) FROM app.media_library_assetusage UNION ALL
  SELECT 'BIND-DB-MATCHED',count(*) FROM file_match WHERE candidate_sha IS NOT NULL UNION ALL
  SELECT 'BIND-DB-UNMATCHED',count(*) FROM file_match WHERE candidate_sha IS NULL UNION ALL
  SELECT 'BIND-CANDIDATE-MATCHED',count(*) FROM candidate c WHERE EXISTS (
    SELECT 1 FROM app.media_library_assetfile f WHERE f.sha256=c.sha256 AND f.byte_size=c.byte_size) UNION ALL
  SELECT 'BIND-CANDIDATE-ONLY',count(*) FROM candidate c WHERE NOT EXISTS (
    SELECT 1 FROM app.media_library_assetfile f WHERE f.sha256=c.sha256 AND f.byte_size=c.byte_size) UNION ALL
  SELECT 'BIND-GALLERY-MATCHED',count(*) FROM candidate c WHERE c.cohort='gallery' AND EXISTS (
    SELECT 1 FROM app.media_library_assetfile f WHERE f.sha256=c.sha256 AND f.byte_size=c.byte_size) UNION ALL
  SELECT 'BIND-GALLERY-MISSING',count(*) FROM candidate c WHERE c.cohort='gallery' AND NOT EXISTS (
    SELECT 1 FROM app.media_library_assetfile f WHERE f.sha256=c.sha256 AND f.byte_size=c.byte_size) UNION ALL
  SELECT 'USAGE-ELIGIBLE',count(*) FROM usage_class WHERE class='eligible' UNION ALL
  SELECT 'USAGE-ELIGIBLE-CURRENT-PAGE',count(*) FROM usage_class WHERE class='eligible' AND kind='current_page' UNION ALL
  SELECT 'USAGE-ELIGIBLE-ORDINARY',count(*) FROM usage_class WHERE class='eligible' AND kind='ordinary_version' UNION ALL
  SELECT 'USAGE-ELIGIBLE-STABLE',count(*) FROM usage_class WHERE class='eligible' AND kind='stable_version' UNION ALL
  SELECT 'USAGE-ELIGIBLE-SHARED',count(*) FROM usage_class WHERE class='eligible' AND kind='shared_block' UNION ALL
  SELECT 'USAGE-EXCLUDED',count(*) FROM usage_class WHERE class='excluded' UNION ALL
  SELECT 'USAGE-EXCLUDED-ORDINARY',count(*) FROM usage_class WHERE class='excluded' AND kind='ordinary_version' UNION ALL
  SELECT 'USAGE-EXCLUDED-STABLE',count(*) FROM usage_class WHERE class='excluded' AND kind='stable_version' UNION ALL
  SELECT 'USAGE-EXCLUDED-SHARED',count(*) FROM usage_class WHERE class='excluded' AND kind='shared_block' UNION ALL
  SELECT 'USAGE-EXCLUDED-DRAFT',count(*) FROM usage_class WHERE class='excluded' AND kind='draft' UNION ALL
  SELECT 'USAGE-EXCLUDED-RETAINED',count(*) FROM usage_class WHERE class='excluded' AND kind='retained_html' UNION ALL
  SELECT 'USAGE-UNCLASSIFIED',count(*) FROM usage_class WHERE class='unclassified' UNION ALL
  SELECT 'USAGE-PARTITION-DELTA',abs(
    (SELECT count(*) FROM app.media_library_assetusage)
    -(SELECT count(*) FROM usage_class WHERE class IN ('eligible','excluded'))) UNION ALL
  SELECT 'ANOM-CANDIDATE-DUPLICATE',count(*) FROM (
    SELECT sha256,byte_size FROM candidate GROUP BY sha256,byte_size HAVING count(*)<>1) d UNION ALL
  SELECT 'ANOM-DB-PAIR-DUPLICATE',count(*) FROM (
    SELECT sha256,byte_size FROM app.media_library_assetfile GROUP BY sha256,byte_size HAVING count(*)<>1) d UNION ALL
  SELECT 'ANOM-DESCRIPTOR',count(*) FROM file_match WHERE
    kind NOT IN ('private-source','main','preview','legacy-public')
    OR sha256 !~ '^[0-9a-f]{64}$' OR byte_size<0 OR length(key)>1024
    OR key !~ '^(img|private/sources)/[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*$'
    OR (kind='private-source') IS DISTINCT FROM (key LIKE 'private/sources/%')
    OR (kind='legacy-public') IS DISTINCT FROM is_legacy
    OR (is_legacy AND source_sha256<>sha256) UNION ALL
  SELECT 'ANOM-ELIGIBLE-ASSET-STATE',count(*) FROM usage_class u
    JOIN app.media_library_asset a ON a.id=u.asset_id
    WHERE u.class='eligible' AND a.status<>'ready' UNION ALL
  SELECT 'ANOM-ELIGIBLE-NO-FILE',count(*) FROM usage_class u
    WHERE u.class='eligible' AND NOT EXISTS (
      SELECT 1 FROM app.media_library_assetfile f WHERE f.asset_id=u.asset_id) UNION ALL
  SELECT 'ANOM-ORPHAN-CONSUMER',COALESCE(sum(orphan),0)::bigint FROM usage_class UNION ALL
  SELECT 'ANOM-UNKNOWN-KIND',count(*) FROM usage_class
    WHERE kind NOT IN ('current_page','shared_block','ordinary_version','stable_version','draft','retained_html') UNION ALL
  SELECT 'ANOM-SELECTED-OVERLAP',count(*) FROM (
    SELECT id FROM (
      SELECT id FROM selected_current UNION ALL SELECT id FROM selected_previous
    ) s GROUP BY id HAVING count(*)<>1) d UNION ALL
  SELECT 'STRUCT-CURRENT-INVALID',count(*) FROM app.page_versions_pagecontentstate s
    LEFT JOIN app.page_versions_pagerevision r ON r.id=s.current_revision_id AND r.page_id=s.page_id
    WHERE r.id IS NULL OR r.kind NOT IN ('initial','automatic') OR r.sequence<>s.sequence UNION ALL
  SELECT 'STRUCT-CURRENT-NEWER',count(*) FROM selected_current c
    WHERE EXISTS (SELECT 1 FROM app.page_versions_pagerevision r
      WHERE r.page_id=c.page_id AND r.sequence>c.sequence AND r.kind IN ('initial','automatic')) UNION ALL
  SELECT 'STRUCT-PAGE-WITHOUT-STATE',count(*) FROM app.content_page p
    LEFT JOIN app.page_versions_pagecontentstate s ON s.page_id=p.id WHERE s.page_id IS NULL UNION ALL
  SELECT 'STRUCT-SHARED-CURRENT-INVALID',count(*) FROM app.shared_content_sharedblock b
    LEFT JOIN app.shared_content_sharedrevision r
      ON r.id=b.current_revision_id AND r.block_id=b.id
    WHERE b.current_revision_id IS NOT NULL AND r.id IS NULL UNION ALL
  SELECT 'RECON-DUP-PAIR-GROUPS',count(*) FROM duplicate_matched_pair UNION ALL
  SELECT 'RECON-DUP-FILE-ROWS',count(*) FROM duplicate_matched_file UNION ALL
  SELECT 'RECON-DUP-DISTINCT-ASSETS',count(DISTINCT asset_id) FROM duplicate_matched_file UNION ALL
  SELECT 'RECON-DUP-READY-ROWS',count(*) FROM duplicate_matched_file WHERE status='ready' UNION ALL
  SELECT 'RECON-DUP-LEGACY-ROWS',count(*) FROM duplicate_matched_file WHERE is_legacy UNION ALL
  SELECT 'RECON-DUP-KIND-PRIVATE-SOURCE',count(*) FROM duplicate_matched_file WHERE kind='private-source' UNION ALL
  SELECT 'RECON-DUP-KIND-MAIN',count(*) FROM duplicate_matched_file WHERE kind='main' UNION ALL
  SELECT 'RECON-DUP-KIND-PREVIEW',count(*) FROM duplicate_matched_file WHERE kind='preview' UNION ALL
  SELECT 'RECON-DUP-KIND-LEGACY-PUBLIC',count(*) FROM duplicate_matched_file WHERE kind='legacy-public' UNION ALL
  SELECT 'RECON-DUP-ELIGIBLE-USAGES',count(*) FROM usage_class u WHERE u.class='eligible' AND EXISTS (
    SELECT 1 FROM duplicate_matched_file f WHERE f.asset_id=u.asset_id) UNION ALL
  SELECT 'RECON-DUP-EXCLUDED-USAGES',count(*) FROM usage_class u WHERE u.class='excluded' AND EXISTS (
    SELECT 1 FROM duplicate_matched_file f WHERE f.asset_id=u.asset_id) UNION ALL
  SELECT 'RECON-UNMATCHED-PAIR-GROUPS',count(*) FROM unmatched_db_pair UNION ALL
  SELECT 'RECON-UNMATCHED-FILE-ROWS',count(*) FROM unmatched_db_file UNION ALL
  SELECT 'RECON-UNMATCHED-DISTINCT-ASSETS',count(DISTINCT asset_id) FROM unmatched_db_file UNION ALL
  SELECT 'RECON-UNMATCHED-READY-ROWS',count(*) FROM unmatched_db_file WHERE status='ready' UNION ALL
  SELECT 'RECON-UNMATCHED-LEGACY-ROWS',count(*) FROM unmatched_db_file WHERE is_legacy UNION ALL
  SELECT 'RECON-UNMATCHED-KIND-PRIVATE-SOURCE',count(*) FROM unmatched_db_file WHERE kind='private-source' UNION ALL
  SELECT 'RECON-UNMATCHED-KIND-MAIN',count(*) FROM unmatched_db_file WHERE kind='main' UNION ALL
  SELECT 'RECON-UNMATCHED-KIND-PREVIEW',count(*) FROM unmatched_db_file WHERE kind='preview' UNION ALL
  SELECT 'RECON-UNMATCHED-KIND-LEGACY-PUBLIC',count(*) FROM unmatched_db_file WHERE kind='legacy-public' UNION ALL
  SELECT 'RECON-UNMATCHED-ELIGIBLE-USAGES',count(*) FROM usage_class u WHERE u.class='eligible' AND EXISTS (
    SELECT 1 FROM unmatched_db_file f WHERE f.asset_id=u.asset_id) UNION ALL
  SELECT 'RECON-UNMATCHED-EXCLUDED-USAGES',count(*) FROM usage_class u WHERE u.class='excluded' AND EXISTS (
    SELECT 1 FROM unmatched_db_file f WHERE f.asset_id=u.asset_id)
)
SELECT query_id||'|'||value::text FROM facts ORDER BY query_id;
ROLLBACK;

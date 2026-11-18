\set ON_ERROR_STOP on
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='2000ms';
SET LOCAL lock_timeout='250ms';
SET LOCAL idle_in_transaction_session_timeout='30000ms';
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
  SELECT u.asset_id,
    CASE
      WHEN u.kind='current_page' AND p.id IS NOT NULL THEN 'eligible'
      WHEN u.kind IN ('ordinary_version','stable_version') AND sr.id IS NOT NULL THEN 'eligible'
      WHEN u.kind='shared_block' AND cs.id IS NOT NULL THEN 'eligible'
      WHEN u.kind IN ('ordinary_version','stable_version') AND r.id IS NOT NULL THEN 'excluded'
      WHEN u.kind='shared_block' AND sh.id IS NOT NULL THEN 'excluded'
      WHEN u.kind IN ('draft','retained_html') THEN 'excluded'
      ELSE 'unclassified'
    END AS class
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
unmatched AS (
  SELECT f.asset_id,f.key,f.sha256,f.byte_size,a.status,a.is_legacy,f.kind,
    count(*) FILTER (WHERE u.class='eligible')::bigint AS eligible_usages,
    count(*) FILTER (WHERE u.class='excluded')::bigint AS excluded_usages,
    count(*) FILTER (WHERE u.class='unclassified')::bigint AS unclassified_usages
  FROM app.media_library_assetfile f
  JOIN app.media_library_asset a ON a.id=f.asset_id
  LEFT JOIN usage_class u ON u.asset_id=f.asset_id
  WHERE NOT EXISTS (
    SELECT 1 FROM candidate c WHERE c.sha256=f.sha256 AND c.byte_size=f.byte_size)
  GROUP BY f.asset_id,f.id,f.key,f.sha256,f.byte_size,a.status,a.is_legacy,f.kind
),
approved AS (
  SELECT * FROM unmatched
  WHERE status='ready' AND NOT is_legacy AND kind='main'
    AND key ~ '^img/[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*$'
    AND key !~ '(^|/)[^/]*\.(?:/|$)'
    AND key !~* '(^|/)(con|prn|aux|nul|com[1-9]|lpt[1-9])(\.[^/]*)?(/|$)'
    AND length(key)<=1024 AND sha256 ~ '^[0-9a-f]{64}$' AND byte_size>=0
    AND eligible_usages=2 AND excluded_usages=1 AND unclassified_usages=0
),
guard AS (
  SELECT a.* FROM approved a
  WHERE (SELECT count(*) FROM unmatched)=1
    AND (SELECT count(*) FROM approved)=1
    AND (SELECT count(*) FROM candidate)=301
    AND (SELECT count(*) FROM app.media_library_assetfile)=238
    AND (SELECT count(*) FROM app.media_library_assetusage)=736
)
SELECT 'RB1SRC|' || replace(encode(convert_to(key,'UTF8'),'base64'),E'\n','') || '|' || sha256 || '|' || byte_size::text ||
       '|1|' || eligible_usages::text || '|' || excluded_usages::text
FROM guard;
\echo RB1SRC_READY

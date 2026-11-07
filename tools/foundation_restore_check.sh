#!/bin/sh
set -eu

umask 077
phase=artifacts
started=0

cleanup() {
    if [ "$started" -eq 1 ]; then
        pg_ctl -D /restore-db/data -m immediate -w stop >/dev/null 2>&1 || true
        started=0
    fi
}

fail() {
    printf 'LOCAL_RESTORE_CHECK_UNAVAILABLE phase=%s\n' "$phase" >&2
    exit 1
}

trap cleanup EXIT
trap 'exit 1' HUP INT TERM

[ -d /backup ] || fail
cd /backup || fail
sha256sum -c checksums.sha256 >/dev/null 2>&1 || fail
pg_restore --list database.dump >/dev/null 2>&1 || fail
tar -tf media.tar > /tmp/media.list 2>/dev/null || fail
tar -tvf media.tar > /tmp/media.verbose 2>/dev/null || fail
awk -F/ '
    index($0,"\\") {exit 1}
    $1 != "media" {exit 1}
    {for(i=1;i<=NF;i++){if($i=="." || $i==".." || ($i=="" && i<NF)){exit 1}}}
' /tmp/media.list || fail
awk 'substr($0,1,1)!="-" && substr($0,1,1)!="d" {exit 1}' /tmp/media.verbose || fail

phase=media
mkdir -p /restore-media/media || fail
tar --extract --file=/backup/media.tar --directory=/restore-media \
    --no-same-owner --no-same-permissions >/dev/null 2>&1 || fail
[ -z "$(find /restore-media ! -type f ! -type d -print -quit)" ] || fail

phase=database-init
mkdir /restore-db/data /restore-db/socket || fail
initdb -D /restore-db/data --no-locale --encoding=UTF8 \
    --auth-local=trust --auth-host=reject >/dev/null 2>&1 || fail
pg_ctl -D /restore-db/data -l /restore-db/postgres.log \
    -o "-c listen_addresses= -c unix_socket_directories=/restore-db/socket -c fsync=on -c synchronous_commit=on" \
    -w start >/dev/null 2>&1 || fail
started=1
createdb -h /restore-db/socket restore_check >/dev/null 2>&1 || fail

phase=database-restore
pg_restore -h /restore-db/socket -d restore_check --exit-on-error \
    --single-transaction --no-owner --no-privileges /backup/database.dump \
    >/dev/null 2>&1 || fail

phase=smoke
table_count=$(psql -h /restore-db/socket -d restore_check -Atq \
    -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='app' AND table_type='BASE TABLE'" \
    2>/dev/null) || fail
migration_count=$(psql -h /restore-db/socket -d restore_check -Atq \
    -c "SELECT count(*) FROM app.django_migrations" 2>/dev/null) || fail
case "$table_count:$migration_count" in
    *[!0-9:]*|0:*|*:0) fail ;;
esac
psql -h /restore-db/socket -d restore_check -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<'SQL' || fail
DO $$
DECLARE item record; rows_read bigint;
BEGIN
    FOR item IN
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema = 'app' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    LOOP
        EXECUTE format('SELECT count(*) FROM %I.%I', item.table_schema, item.table_name)
            INTO rows_read;
    END LOOP;
END
$$;
SQL

media_files=$(find /restore-media/media -type f | wc -l | tr -d ' ') || fail
media_bytes=$(find /restore-media/media -type f -printf '%s\n' | awk '{sum+=$1} END {printf "%.0f",sum+0}') || fail
case "$media_files:$media_bytes" in
    *[!0-9:]*) fail ;;
esac

phase=stop
pg_ctl -D /restore-db/data -m fast -w stop >/dev/null 2>&1 || fail
started=0
trap - EXIT HUP INT TERM
printf 'LOCAL_RESTORE_CHECK_OK tables=%s migrations=%s media_files=%s media_bytes=%s\n' \
    "$table_count" "$migration_count" "$media_files" "$media_bytes"

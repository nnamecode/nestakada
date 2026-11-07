#!/bin/sh
set -eu

umask 077
phase=preflight

fail() {
    printf 'LOCAL_BACKUP_TOOL_UNAVAILABLE phase=%s\n' "$phase" >&2
    exit 1
}

case "${BACKUP_GENERATION:-}" in
    ''|*[!0-9a-f-]*) fail ;;
esac
case "${BACKUP_CREATED_AT:-}" in
    ????-??-??T??:??:??Z) ;;
    *) fail ;;
esac

password=$(tr -d '\r\n' < /run/secrets/migrator-password) || fail
case "$password" in
    *[!0-9a-fA-F]*) fail ;;
esac
[ "${#password}" -eq 96 ] || fail

printf 'db:5432:estakada_foundation:app_migrator:%s\n' "$password" > /run/backup/.pgpass || fail
unset password
chmod 0600 /run/backup/.pgpass || fail

[ -d /backup ] || fail
[ -z "$(find /backup -mindepth 1 -maxdepth 1 -print -quit)" ] || fail

phase=database
PGPASSFILE=/run/backup/.pgpass pg_dump \
    --host=db --port=5432 --username=app_migrator \
    --dbname=estakada_foundation --format=custom \
    --schema=app --no-owner --no-privileges \
    --file=/backup/database.dump || fail

phase=media
if [ -d /var/lib/estakada/media ]; then
    [ -z "$(find /var/lib/estakada/media -type l -print -quit)" ] || fail
    [ -z "$(find /var/lib/estakada/media ! -type f ! -type d -print -quit)" ] || fail
    tar --format=posix --numeric-owner --owner=10001 --group=10001 \
        -cf /backup/media.tar -C /var/lib/estakada media || fail
else
    tar --format=posix -cf /backup/media.tar --files-from /dev/null || fail
fi

phase=archive-validation
pg_restore --list /backup/database.dump > /dev/null || fail
tar -tf /backup/media.tar > /dev/null || fail
[ -s /backup/database.dump ] || fail
[ -s /backup/media.tar ] || fail

cd /backup || fail
phase=checksums
sha256sum database.dump media.tar > checksums.sha256 || fail
sha256sum -c checksums.sha256 > /dev/null || fail

phase=manifest
cat > manifest.json <<EOF
{"schemaVersion":1,"generation":"${BACKUP_GENERATION}","createdAt":"${BACKUP_CREATED_AT}","database":"estakada_foundation","databaseArchive":"database.dump","mediaArchive":"media.tar","consistency":"maintenance-gate","checksumAlgorithm":"SHA-256"}
EOF

[ "$(find /backup -mindepth 1 -maxdepth 1 -type f | wc -l | tr -d ' ')" -eq 4 ] || fail
[ -z "$(find /backup -mindepth 1 -maxdepth 1 ! -type f -print -quit)" ] || fail
printf '%s\n' 'LOCAL_BACKUP_TOOL_OK'

#!/bin/sh
set -eu

fail() {
    printf '%s\n' 'R7_POSTGRES_UNAVAILABLE' >&2
    exit 1
}

[ "$#" -eq 1 ] || fail
mode=$1
[ "$mode" = dump ] || [ "$mode" = restore ] || fail
[ -n "${ESTAKADA_DB_NAME:-}" ] || fail
[ -n "${ESTAKADA_DB_USER:-}" ] || fail
[ -r /run/secrets/db-password ] || fail
[ -r /run/secrets/database-ca ] || fail
[ -d /output ] || fail

password=$(cat /run/secrets/db-password) || fail
[ -n "$password" ] || fail
umask 077
printf 'db:5432:%s:%s:%s\n' "$ESTAKADA_DB_NAME" "$ESTAKADA_DB_USER" "$password" > /tmp/.pgpass || fail
unset password
export PGPASSFILE=/tmp/.pgpass PGSSLMODE=verify-full PGSSLROOTCERT=/run/secrets/database-ca

if [ "$mode" = dump ]; then
    [ ! -e /output/database.dump ] || fail
    pg_dump --host=db --port=5432 --username="$ESTAKADA_DB_USER" \
        --dbname="$ESTAKADA_DB_NAME" --format=custom --compress=0 \
        --no-owner --no-privileges --file=/output/database.dump || fail
    pg_restore --list /output/database.dump >/dev/null || fail
    [ -s /output/database.dump ] || fail
    printf '%s\n' 'R7_POSTGRES_DUMP_OK'
else
    [ -r /output/database.dump ] || fail
    pg_restore --host=db --port=5432 --username="$ESTAKADA_DB_USER" \
        --dbname="$ESTAKADA_DB_NAME" --exit-on-error --single-transaction \
        --no-owner --no-privileges /output/database.dump || fail
    printf '%s\n' 'R7_POSTGRES_RESTORE_OK'
fi

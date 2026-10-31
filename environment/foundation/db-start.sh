#!/bin/sh
# Own new DB only. Do not weaken private-key permissions on the Windows bind.
set -eu
cp /run/secrets/database-server-key /var/run/postgresql/server.key
if [ "$(id -u)" = 0 ]; then
    chown 999:999 /var/run/postgresql/server.key
fi
chmod 600 /var/run/postgresql/server.key
exec /usr/local/bin/docker-entrypoint.sh "$@"

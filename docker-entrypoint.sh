#!/bin/sh
# Starts as root only long enough to give the nova user the database
# directory, then drops privileges for good. Needed on Fly.io, whose
# volumes are mounted root-owned; a no-op for Docker named volumes,
# which already inherit the image's ownership.
set -e
DATA_DIR="$(dirname "${NOVA_DB_PATH:-/data/nova.db}")"
if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA_DIR"
    chown nova:nova "$DATA_DIR"
    # setpriv keeps the environment, so HOME would still be /root, which
    # nova can't read (Streamlit looks for ~/.streamlit/secrets.toml).
    export HOME=/home/nova USER=nova
    exec setpriv --reuid=nova --regid=nova --init-groups "$@"
fi
exec "$@"

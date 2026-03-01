#!/bin/sh
set -e

mkdir -p /data/avatars
chown 10001:10001 /data/avatars 2>/dev/null || true

exec gosu kidtube "$@"

#!/usr/bin/env bash
#
# Run a command against the CosmaSignal local PostgreSQL cluster.
#
#   ./scripts/with-database.sh uv run pytest
#   ./scripts/with-database.sh sh -c 'psql -h "$COSMA_DB_HOST" "$COSMA_DB_NAME"'
#   ./scripts/with-database.sh --stop
#
# The cluster lives under var/, which is ignored by Git, and listens on a local
# Unix socket only. It has no password and no TCP listener.
#
# That combination is deliberate. config/env.example classifies a connection
# string carrying a password as a credential, and docs/conventions/secret-setup.md
# defers credential resolution to P0-B. A passwordless local socket is the only
# shape that satisfies both today: there is no credential to resolve, so nothing
# has to be resolved early, and nothing reachable off this machine is exposed.
# This script never touches COSMA_SECRET_SOURCE; scripts/with-secret-source.sh
# owns that.
#
# See docs/conventions/p0-security.md and docs/p0-execution-plan.md, A1.

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)

PGDATA="$repo_root/var/postgres"
startup_log="$repo_root/var/postgres.startup.log"
db_name="cosma_p0"
db_user="$(id -un)"

EX_USAGE=64
EX_CONFIG=78

# Regenerated on every run rather than edited in place, so repeated runs and a
# moved repository both converge on the same result.
conf_begin="# BEGIN cosma-signal managed settings"
conf_end="# END cosma-signal managed settings"

cluster_is_running() {
  pg_ctl --pgdata="$PGDATA" status >/dev/null 2>&1
}

if [ "$#" -eq 0 ]; then
  echo "usage: ${0##*/} <command> [args...]" >&2
  echo "       ${0##*/} --stop" >&2
  exit "$EX_USAGE"
fi

for tool in initdb pg_ctl createdb psql; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "error: $tool not found on PATH" >&2
    echo "install PostgreSQL 18, or enter the optional Nix shell: nix develop" >&2
    exit "$EX_CONFIG"
  fi
done

# Stopping an absent or already-stopped cluster is the requested end state, so
# it succeeds quietly instead of reporting a failure.
if [ "$1" = "--stop" ]; then
  if [ -d "$PGDATA" ] && cluster_is_running; then
    pg_ctl --pgdata="$PGDATA" --mode=fast --wait stop
  fi
  exit 0
fi

if [ ! -d "$PGDATA" ]; then
  mkdir -p "$(dirname "$PGDATA")"
  # --auth=trust is safe only because the cluster is unreachable over TCP; the
  # listener settings written below are what make that true.
  initdb \
    --auth=trust \
    --username="$db_user" \
    --encoding=UTF8 \
    --locale=C \
    --pgdata="$PGDATA" >/dev/null
fi

conf="$PGDATA/postgresql.conf"
conf_next="$conf.cosma-next"

awk -v begin="$conf_begin" -v end="$conf_end" '
  $0 == begin { inside = 1 }
  inside == 0 { print }
  $0 == end   { inside = 0 }
' "$conf" >"$conf_next"

{
  printf '%s\n' "$conf_begin"
  # listen_addresses = '' removes the TCP listener entirely: the cluster is
  # reachable only through the socket directory below, which sits inside PGDATA.
  printf "listen_addresses = ''\n"
  printf "unix_socket_directories = '%s'\n" "$PGDATA"
  printf '%s\n' "$conf_end"
} >>"$conf_next"

mv "$conf_next" "$conf"

if ! cluster_is_running; then
  pg_ctl --pgdata="$PGDATA" --log="$startup_log" --wait start >/dev/null
fi

if ! psql --host="$PGDATA" --username="$db_user" --dbname=postgres \
  --no-align --tuples-only --quiet \
  --command="SELECT 1 FROM pg_database WHERE datname = '$db_name'" | grep -q 1; then
  createdb --host="$PGDATA" --username="$db_user" "$db_name"
fi

# The socket directory takes the place of a hostname. No password exists to pass,
# and none is created.
export COSMA_DB_HOST="$PGDATA"
export COSMA_DB_NAME="$db_name"
export COSMA_DB_USER="$db_user"

exec "$@"

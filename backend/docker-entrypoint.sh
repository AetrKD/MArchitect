#!/bin/sh
set -eu

# Docker bind mounts do not all support chown (for example rootless Docker,
# Docker Desktop, NFS/root-squash). Prefer the requested host UID/GID when
# possible, but do not abort before SQLite initialization solely because a
# mount rejected chown.
uid="${MARCHITECT_UID:-1000}"
gid="${MARCHITECT_GID:-1000}"
auth_database="${MARCHITECT_AUTH_DB:-/data/marchitect.sqlite3}"
export MARCHITECT_AUTH_DB="$auth_database"
auth_dir="$(dirname "$auth_database")"

mkdir -p /data /java "$auth_dir"

for path in /data /java "$auth_dir"; do
    if ! chown "$uid:$gid" "$path" 2>/dev/null; then
        echo "[marchitect] warning: could not chown $path to $uid:$gid; checking actual write access instead." >&2
    fi
done

if [ -e "$auth_database" ]; then
    if ! chown "$uid:$gid" "$auth_database" 2>/dev/null; then
        echo "[marchitect] warning: could not chown existing SQLite database $auth_database to $uid:$gid." >&2
    fi
fi

can_write() {
    runner="$1"
    shift

    if [ "$runner" = "target" ]; then
        gosu "$uid:$gid" sh -c '
            db="$1"
            shift
            if [ -e "$db" ] && [ ! -w "$db" ]; then
                exit 1
            fi
            for dir do
                probe="$dir/.marchitect-write-test.$$"
                if ! : >"$probe" 2>/dev/null; then
                    exit 1
                fi
                rm -f "$probe" 2>/dev/null || exit 1
            done
        ' sh "$auth_database" "$@"
    else
        sh -c '
            db="$1"
            shift
            if [ -e "$db" ] && [ ! -w "$db" ]; then
                exit 1
            fi
            for dir do
                probe="$dir/.marchitect-write-test.$$"
                if ! : >"$probe" 2>/dev/null; then
                    exit 1
                fi
                rm -f "$probe" 2>/dev/null || exit 1
            done
        ' sh "$auth_database" "$@"
    fi
}

if can_write target /data /java "$auth_dir"; then
    gosu "$uid:$gid" python -m modules.auth
    exec gosu "$uid:$gid" "$@"
fi

# Some bind-mount implementations allow the container's current user to write
# but reject remapping ownership to an arbitrary numeric UID/GID. In that case
# keep the service available instead of dying before the database can be
# created. Rootless Docker maps container root back to the invoking host user.
if can_write current /data /java "$auth_dir"; then
    echo "[marchitect] warning: $uid:$gid cannot write the mounted data directories; continuing as $(id -u):$(id -g)." >&2
    echo "[marchitect] warning: set MARCHITECT_UID/MARCHITECT_GID to writable host IDs if you want non-root execution inside the container." >&2
    python -m modules.auth
    exec "$@"
fi

echo "[marchitect] error: neither $uid:$gid nor the current container user can write $auth_dir." >&2
echo "[marchitect] error: ensure the data bind mount is writable and verify MARCHITECT_UID/MARCHITECT_GID." >&2
exit 1

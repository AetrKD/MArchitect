#!/bin/sh
set -eu

# Docker creates a missing bind-mounted host directory as root. Repair just
# the mount roots before dropping privileges, so a fresh deployment can create
# its database and all later files are owned by the host project user.
uid="${MARCHITECT_UID:-1000}"
gid="${MARCHITECT_GID:-1000}"
mkdir -p /data /java
chown "$uid:$gid" /data /java

exec gosu "$uid:$gid" "$@"

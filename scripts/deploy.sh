#!/usr/bin/env bash
# Executed over SSH using bash -s. No server .env is sourced as shell code.
set -Eeuo pipefail
umask 077

fail() { echo "Deployment refused: $*" >&2; exit 1; }
[[ $# == 4 ]] || fail "Expected path, commit, project and upload filename"
deploy_root=$1
release=$2
project=$3
upload=$4
[[ "$deploy_root" =~ ^/[a-zA-Z0-9_./-]+$ && "$deploy_root" != / ]] || fail "Invalid deployment directory"
[[ "/$deploy_root/" != *"/../"* && "/$deploy_root/" != *"/./"* ]] || fail "Invalid deployment directory"
[[ "$release" =~ ^[0-9a-f]{40}$ ]] || fail "Invalid release commit"
[[ "$project" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || fail "Invalid Compose project"
[[ "$upload" =~ ^$release-[0-9]+-[0-9]+\.tar$ ]] || fail "Invalid upload filename"
for command in docker flock python3 tar realpath; do
  command -v "$command" > /dev/null || fail "Missing $command"
done
docker compose version > /dev/null
deploy_root=$(realpath -e -- "$deploy_root")
[[ "$deploy_root" != / ]] || fail "Invalid resolved directory"
cd "$deploy_root"
exec 9> .deploy.lock
flock -w 30 9 || fail "Another deployment is running"
[[ -f .env && ! -L .env ]] || fail "Create a private server .env first"
# Refuse the example code, without logging the resolved Compose configuration.
chmod 600 .env
if [[ -f .failed-release && "$(cat .failed-release)" == "$release" ]]; then
  fail "This release previously failed. Inspect the server and remove .failed-release to retry"
fi
mkdir -p releases
archive="$deploy_root/incoming/$upload"
[[ -f "$archive" && ! -L "$archive" ]] || fail "Release archive is missing"
release_dir="$deploy_root/releases/$release"
if [[ ! -d "$release_dir" ]]; then
  staging=$(mktemp -d "$deploy_root/releases/.staging.XXXXXX")
  (umask 022; tar --extract --file "$archive" --directory "$staging" --no-same-owner --no-same-permissions)
  [[ -f "$staging/docker-compose.deploy.yml" && -f "$staging/backend/Dockerfile.production" && -f "$staging/frontend/Dockerfile.production" ]] || fail "Incomplete archive"
  mv -- "$staging" "$release_dir"
fi
rm -f -- "$archive"
export MARCHITECT_DATA_DIR="$deploy_root/data"
export MARCHITECT_JAVA_DIR="$deploy_root/backend/JAVA"
export MARCHITECT_RELEASE="$release"
compose() {
  docker compose --project-name "$project" --project-directory "$release_dir" \
    --env-file "$deploy_root/.env" -f "$release_dir/docker-compose.deploy.yml" "$@"
}
compose config --quiet
# Read only selected settings; never print .env or the rendered configuration.
compose config --format json | python3 -c '
import json, os, sqlite3, sys
from pathlib import Path
from urllib.parse import quote
config = json.load(sys.stdin)
code = config["services"]["backend"]["environment"]["MARCHITECT_INITIAL_ADMIN_CODE"]
initialized = False
database = Path(os.environ["MARCHITECT_DATA_DIR"]) / "marchitect.sqlite3"
if database.is_file():
    try:
        with sqlite3.connect("file:" + quote(str(database)) + "?mode=ro", uri=True) as connection:
            initialized = connection.execute(
                "SELECT 1 FROM settings WHERE key = ? AND value <> ?", ("admin_code_hash", "")
            ).fetchone() is not None
    except sqlite3.Error:
        pass
if not initialized and (len(code.strip()) < 8 or code.strip() in {"ADMIN", "replace-with-a-long-unique-admin-code"}):
    sys.exit("Set a unique administrator code of at least 8 characters in the server .env for a new installation")
'

previous=""
if [[ -f .current-release ]]; then
  previous=$(cat .current-release)
  [[ "$previous" =~ ^[0-9a-f]{40}$ && -f "$deploy_root/releases/$previous/docker-compose.deploy.yml" ]] || fail "Invalid previous release state"
fi
if [[ "$previous" == "$release" ]]; then
  container_output=$(compose ps --all --quiet backend frontend)
  mapfile -t container_ids <<< "$container_output"
  if [[ ${#container_ids[@]} == 2 ]]; then
    health=$(docker inspect "${container_ids[@]}" --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}')
    if [[ "$health" == $'running healthy\nrunning healthy' ]]; then
      echo "Commit $release is already deployed and healthy."
      exit 0
    fi
  fi
fi
# A wrong project/path must not silently switch the app to empty storage.
backend_ids=$(docker ps -aq --filter "label=com.docker.compose.project=$project" --filter label=com.docker.compose.service=backend)
if [[ -n "$backend_ids" ]]; then
  [[ "$backend_ids" != *$'\n'* ]] || fail "Expected a single backend container"
  docker inspect "$backend_ids" --format '{{json .Mounts}}' | python3 -c '
import json, os, sys
mounts = {m["Destination"]: m for m in json.load(sys.stdin)}
for target, expected in [("/data", sys.argv[1]), ("/java", sys.argv[2])]:
    mount = mounts.get(target, {})
    if mount.get("Type") != "bind" or os.path.realpath(mount.get("Source", "")) != os.path.realpath(expected):
        sys.exit("Existing container data mounts differ from DEPLOY_PATH; preserve the original data location")
' "$MARCHITECT_DATA_DIR" "$MARCHITECT_JAVA_DIR"
fi
mkdir -p "$MARCHITECT_DATA_DIR" "$MARCHITECT_JAVA_DIR"

# Once a release has been built, keep its tags immutable for retries/rollback.
if ! docker image inspect "marchitect-backend:$release" "marchitect-frontend:$release" > /dev/null 2>&1; then
  compose build --pull
fi

running_ids=$(docker ps -q --filter "label=com.docker.compose.project=$project" --filter label=com.docker.compose.service=backend)
if [[ -n "$running_ids" ]]; then
  processes=$(docker top "$running_ids" -eo pid,comm)
  if awk 'NR > 1 && $2 ~ /^java/ {found=1} END {exit !found}' <<< "$processes"; then
    fail "Minecraft is running. Stop game servers normally in the web console and retry"
  fi
fi

# First migration: snapshot the actual Compose stack recorded on the old container.
legacy=false
legacy_args=()
if [[ -z "$previous" && -n "$backend_ids" ]]; then
  config_files=$(docker inspect "$backend_ids" --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}')
  [[ -n "$config_files" && "$config_files" != "<no value>" ]] || fail "Existing installation has no recorded Compose files"
  IFS=',' read -r -a config_paths <<< "$config_files"
  legacy_index=0
  for config_path in "${config_paths[@]}"; do
    config_path=$(realpath -e -- "$config_path")
    [[ "$config_path" == "$deploy_root/"* && -f "$config_path" ]] || fail "Existing Compose files must be inside DEPLOY_PATH"
    snapshot="$release_dir/legacy-compose-$legacy_index.yml"
    cp -- "$config_path" "$snapshot"
    legacy_args+=(-f "$snapshot")
    legacy_index=$((legacy_index + 1))
  done
  frontend_id=$(docker ps -aq --filter "label=com.docker.compose.project=$project" --filter label=com.docker.compose.service=frontend)
  [[ -n "$frontend_id" && "$frontend_id" != *$'\n'* ]] || fail "Cannot snapshot the previous frontend"
  backend_image=$(docker inspect "$backend_ids" --format '{{.Image}}')
  frontend_image=$(docker inspect "$frontend_id" --format '{{.Image}}')
  docker image tag "$backend_image" "marchitect-backend:legacy-$release"
  docker image tag "$frontend_image" "marchitect-frontend:legacy-$release"
  printf 'services:\n  backend:\n    image: marchitect-backend:legacy-%s\n  frontend:\n    image: marchitect-frontend:legacy-%s\n' "$release" "$release" > "$release_dir/legacy-images.yml"
  legacy=true
fi
changed=false
frontend_stopped=""
rollback() {
  local status=${1:-$?}
  trap - ERR INT TERM HUP
  if [[ "$changed" == true ]]; then
    printf '%s\n' "$release" > "$deploy_root/.failed-release"
    echo "Deployment failed; restoring the previous application version." >&2
    if [[ -n "$previous" ]]; then
      export MARCHITECT_RELEASE="$previous"
      release_dir="$deploy_root/releases/$previous"
      if compose up -d --no-build --force-recreate --wait --wait-timeout 120; then
        echo "Previous release restored." >&2
      else
        echo "Automatic rollback failed; inspect the server before retrying." >&2
      fi
    elif [[ "$legacy" == true ]]; then
      if docker compose -p "$project" --project-directory "$deploy_root" --env-file "$deploy_root/.env" \
        "${legacy_args[@]}" -f "$deploy_root/releases/$release/legacy-images.yml" up -d --no-build --force-recreate --wait --wait-timeout 120; then
        echo "Previous Compose installation restored; verify it manually." >&2
      else
        echo "Migration rollback failed; inspect the server before retrying." >&2
      fi
    else
      # Failed first installation: stop only this project's new containers.
      compose stop || true
      echo "No previous release exists. Data was retained." >&2
    fi
  elif [[ -n "$frontend_stopped" ]]; then
    docker start "$frontend_stopped" > /dev/null || true
  fi
  exit "$status"
}
trap rollback ERR
trap 'rollback 130' INT
trap 'rollback 143' TERM
trap 'rollback 129' HUP
# Prevent new web requests from starting games during the final process check.
# First check above avoids disrupting the console when games are already running.
frontend_running=$(docker ps -q --filter "label=com.docker.compose.project=$project" --filter label=com.docker.compose.service=frontend)
if [[ -n "$frontend_running" ]]; then
  [[ "$frontend_running" != *$'\n'* ]] || fail "Expected a single frontend container"
  frontend_stopped="$frontend_running"
  docker stop --time 15 "$frontend_running" > /dev/null
fi
if [[ -n "$running_ids" ]]; then
  processes=$(docker top "$running_ids" -eo pid,comm)
  if awk 'NR > 1 && $2 ~ /^java/ {found=1} END {exit !found}' <<< "$processes"; then
    echo "A game started during deployment preparation; restoring the web console." >&2
    false
  fi
fi
changed=true
# Recreate the proxy too, so Nginx resolves the backend's new container address.
compose up -d --no-build --force-recreate --wait --wait-timeout 120
printf '%s\n' "$release" > .current-release.tmp
mv -- .current-release.tmp .current-release
changed=false
rm -f -- .failed-release
trap - ERR INT TERM HUP
echo "Deployed commit $release successfully."

#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

fail() { echo "Deployment configuration: $*" >&2; exit 1; }
SOURCE_SHA=${SOURCE_SHA:-${GITHUB_SHA:-}}
for name in DEPLOY_HOST DEPLOY_USER DEPLOY_KNOWN_HOSTS DEPLOY_PATH DEPLOY_PROJECT; do
  [[ -n "${!name:-}" ]] || fail "Missing $name"
done
if [[ -n "${DEPLOY_SSH_KEY_PATH:-}" ]]; then
  [[ "$DEPLOY_SSH_KEY_PATH" == /* && -f "$DEPLOY_SSH_KEY_PATH" && -r "$DEPLOY_SSH_KEY_PATH" ]] || fail "The VM deployment key is missing or unreadable"
else
  [[ -n "${DEPLOY_SSH_KEY:-}" ]] || fail "Set DEPLOY_SSH_KEY_PATH or DEPLOY_SSH_KEY"
fi
# shellcheck disable=SC2153 # Required external input is checked indirectly above.
[[ "$DEPLOY_HOST" =~ ^[a-zA-Z0-9][a-zA-Z0-9.:-]*$ ]] || fail "Invalid host"
[[ "$DEPLOY_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] || fail "Invalid SSH user"
[[ "${DEPLOY_PORT:=22}" =~ ^[0-9]+$ ]] || fail "Invalid SSH port"
(( DEPLOY_PORT >= 1 && DEPLOY_PORT <= 65535 )) || fail "SSH port out of range"
# A conservative path alphabet also makes remote-shell argument quoting safe.
[[ "$DEPLOY_PATH" =~ ^/[a-zA-Z0-9_./-]+$ && "$DEPLOY_PATH" != / ]] || fail "Use an absolute deployment directory without spaces"
[[ "/$DEPLOY_PATH/" != *"/../"* && "/$DEPLOY_PATH/" != *"/./"* ]] || fail "Path traversal is not allowed"
[[ "$DEPLOY_PROJECT" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || fail "Invalid Compose project name"
[[ "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]] || fail "Invalid commit"
[[ "$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT" =~ ^[0-9]+-[0-9]+$ ]] || fail "Invalid run identifier"
[[ "$(git rev-parse HEAD)" == "$SOURCE_SHA" ]] || fail "Checkout differs from the tested commit"

latest=$(git ls-remote origin refs/heads/master | cut -f1)
[[ -n "$latest" ]] || fail "Cannot verify the master branch"
if [[ "$latest" != "$SOURCE_SHA" ]]; then
  echo "Skipping superseded commit $SOURCE_SHA"
  exit 0
fi

ssh_dir=$(mktemp -d "$RUNNER_TEMP/marchitect-ssh.XXXXXX")
cleanup() { rm -f -- "$ssh_dir/key" "$ssh_dir/known_hosts" "$ssh_dir/release.tar"; rmdir -- "$ssh_dir"; }
trap cleanup EXIT
if [[ -n "${DEPLOY_SSH_KEY_PATH:-}" ]]; then
  cp -- "$DEPLOY_SSH_KEY_PATH" "$ssh_dir/key"
else
  printf '%s\n' "$DEPLOY_SSH_KEY" > "$ssh_dir/key"
fi
printf '%s\n' "$DEPLOY_KNOWN_HOSTS" > "$ssh_dir/known_hosts"
unset DEPLOY_SSH_KEY DEPLOY_KNOWN_HOSTS
chmod 600 "$ssh_dir/key" "$ssh_dir/known_hosts"
ssh-keygen -y -P '' -f "$ssh_dir/key" > /dev/null 2>&1 || fail "The deployment key is invalid or requires a passphrase"
# Do not discover and trust host keys during deployment.
ssh_opts=(-i "$ssh_dir/key" -p "$DEPLOY_PORT" -o BatchMode=yes
  -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes
  -o "UserKnownHostsFile=$ssh_dir/known_hosts" -o GlobalKnownHostsFile=/dev/null
  -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=4
  -o ForwardAgent=no -o ClearAllForwardings=yes)
target="$DEPLOY_USER@$DEPLOY_HOST"
upload="$SOURCE_SHA-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT.tar"
# Only tracked build inputs and the deployment Compose file travel to the server.
git archive --format=tar HEAD backend frontend docker-compose.deploy.yml > "$ssh_dir/release.tar"
# shellcheck disable=SC2029 # Validated values intentionally expand on this runner.
ssh "${ssh_opts[@]}" "$target" \
  "umask 077; mkdir -p '$DEPLOY_PATH/incoming' && cat > '$DEPLOY_PATH/incoming/$upload'" < "$ssh_dir/release.tar"
# shellcheck disable=SC2029 # Validated values intentionally expand on this runner.
ssh "${ssh_opts[@]}" "$target" \
  "bash -s -- '$DEPLOY_PATH' '$SOURCE_SHA' '$DEPLOY_PROJECT' '$upload'" < scripts/deploy.sh

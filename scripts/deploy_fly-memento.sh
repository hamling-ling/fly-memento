#!/usr/bin/env bash
# Stop fly-memento on the Uno Q, copy this tree, and start it again.
#
# Python and python/brain are bind-mounted at /app, so a Python-only
# copy runs on the next start. app.yaml and sketch/ are hashed. When
# that hash matches ~/ArduinoApps/fly-memento/.sketch-hash the sketch
# cache stays, and start reuses the build and the venv. A different
# hash, a leftover .sketch-hash.pending from a wipe whose start did
# not finish, or --rebuild removes .cache so the next start compiles.
# The stamp is written only after app start succeeds. A missing stamp
# keeps the cache: the last deploy already compiled this sketch.
# app start refuses while a container for this app is still running,
# and app stop can report success after resetting the microcontroller
# with that container left up. Remove it before start.
#
#   scripts/deploy_fly-memento.sh
#   scripts/deploy_fly-memento.sh --rebuild
#   scripts/deploy_fly-memento.sh arduino@other.local
#   scripts/deploy_fly-memento.sh --rebuild arduino@other.local
#   scripts/deploy_fly-memento.sh --dry-run
#
# --dry-run checks the local archives and prints the remote steps.
# It does not open SSH. This app has no frame JPEGs, so there is no
# --jpeg switch.
#
# Run from anywhere. The default host matches scripts/logs_fly-memento.sh.
#
# Learned memories are ~/fly-memento-data/memories, outside the app
# directory. This script never deletes that tree. A redeploy replaces
# ~/ArduinoApps/fly-memento and leaves the saved brains where they are.

set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
rebuild=0
dry_run=0
host=arduino@uno-q-1.local
for arg in "$@"; do
  case "$arg" in
    --rebuild) rebuild=1 ;;
    --dry-run) dry_run=1 ;;
    -*)
      echo "unknown option: ${arg}" >&2
      exit 2
      ;;
    *) host=$arg ;;
  esac
done
remote=ArduinoApps/fly-memento
ssh=(ssh -o BatchMode=yes -o ConnectTimeout=10)

if [[ ! "$remote" =~ ^[A-Za-z0-9_./-]+$ ]]; then
  echo "remote path rejected" >&2
  exit 1
fi
# Refuse to point the deploy at the memory tree. The rm calls below only
# ever expand under ~/$remote.
case "$remote" in
  fly-memento-data|fly-memento-data/*)
    echo "refusing to deploy onto the memory directory" >&2
    exit 1
    ;;
esac
echo "memory dir kept: ~/fly-memento-data/memories"

sketch_hash=$(
  tar -C "$root/robot" \
    --sort=name \
    --mtime='@0' \
    --owner=0 \
    --group=0 \
    --numeric-owner \
    -cf - app.yaml sketch \
    | sha256sum \
    | awk '{print $1}'
)
if [[ ! "$sketch_hash" =~ ^[0-9a-f]{64}$ ]]; then
  echo "sketch hash failed" >&2
  exit 1
fi

work=$(mktemp -d)
cleanup() {
  rm -rf -- "$work"
}
trap cleanup EXIT

tar -C "$root/robot" \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.cache' \
  -cf "$work/robot.tar" .
tar -C "$root" \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  -cf "$work/brain.tar" brain

robot_listing=$(tar -tf "$work/robot.tar")
brain_listing=$(tar -tf "$work/brain.tar")

has_member() {
  local listing=$1
  local name=$2
  if printf '%s\n' "$listing" | grep -Fxq -- "./${name}"; then
    return 0
  fi
  if printf '%s\n' "$listing" | grep -Fxq -- "${name}"; then
    return 0
  fi
  echo "missing from archive: ${name}" >&2
  return 1
}

require_archive() {
  local listing=$1
  shift
  local name
  for name in "$@"; do
    has_member "$listing" "$name" || exit 1
  done
}

require_archive "$robot_listing" \
  app.yaml \
  python/main.py \
  python/bootstrap.py \
  python/trace.py \
  python/config.py \
  sketch/sketch.ino \
  sketch/sketch.yaml \
  assets/index.html
require_archive "$brain_listing" \
  brain/__init__.py \
  brain/brain.py \
  brain/memory.py \
  brain/constants.py \
  brain/dan.py \
  brain/wheels.py

echo "archive robot ok: app.yaml python/ sketch/ assets/"
echo "archive brain ok: brain/ -> python/brain"
echo "sketch hash ${sketch_hash}"

board() {
  if [[ "$dry_run" -eq 1 ]]; then
    printf 'dry-run: %s\n' "$1"
    return 0
  fi
  "${ssh[@]}" "$host" "$1"
}

echo "stop ${host}:~/${remote}"
board "arduino-app-cli app stop ~/${remote}" || true

robot_bytes=$(wc -c < "$work/robot.tar" | tr -d ' ')
echo "copy robot/ (${robot_bytes} bytes)"
if [[ "$dry_run" -eq 1 ]]; then
  echo "dry-run: tar -C ~/${remote} -xf robot.tar"
else
  "${ssh[@]}" "$host" "mkdir -p ~/${remote} && tar -C ~/${remote} -xf -" < "$work/robot.tar"
fi

echo "copy brain/"
board "rm -rf ~/${remote}/python/brain"
if [[ "$dry_run" -eq 1 ]]; then
  echo "dry-run: tar -C ~/${remote}/python -xf brain.tar"
else
  "${ssh[@]}" "$host" "mkdir -p ~/${remote}/python && tar -C ~/${remote}/python -xf -" < "$work/brain.tar"
fi

board "find ~/${remote} -type d -name __pycache__ -prune -exec rm -rf {} +"

echo "sketch cache ${host}:~/${remote}/.cache"
if [[ "$dry_run" -eq 1 ]]; then
  echo "dry-run: compare .sketch-hash with ${sketch_hash} (rebuild ${rebuild})"
else
  "${ssh[@]}" "$host" "sh -s -- ${sketch_hash} ${rebuild} ${remote}" <<'EOF'
set -eu
want=$1
rebuild=$2
remote=$HOME/$3
stamp=$remote/.sketch-hash
pending=$remote/.sketch-hash.pending
wipe=0
if [ "$rebuild" = 1 ]; then
  echo "rebuild: clear sketch cache"
  wipe=1
elif [ -f "$pending" ]; then
  echo "previous compile did not finish: clear sketch cache"
  wipe=1
elif [ -f "$stamp" ]; then
  got=$(tr -d '[:space:]' < "$stamp")
  if [ "$got" != "$want" ]; then
    echo "sketch changed: clear sketch cache"
    wipe=1
  else
    echo "sketch unchanged: keep cache"
  fi
else
  echo "sketch cache kept (no stamp yet)"
fi
if [ "$wipe" = 1 ]; then
  rm -rf "$remote/.cache"
  printf '%s\n' "$want" > "$pending"
fi
EOF
fi

echo "remove leftover container ${host}:~/${remote}"
if [[ "$dry_run" -eq 1 ]]; then
  echo "dry-run: docker rm leftover fly-memento"
else
  "${ssh[@]}" "$host" "{
    docker ps -aq --filter label=cc.arduino.app.path=\"\$HOME/${remote}\"
    docker ps -aq --filter name=fly-memento
    docker ps -aq --filter name=fly_memento
  } | sort -u | xargs -r docker rm -f"
fi

echo "start ${host}:~/${remote}"
board "arduino-app-cli app start ~/${remote} && printf '%s\n' '${sketch_hash}' > ~/${remote}/.sketch-hash && rm -f ~/${remote}/.sketch-hash.pending"

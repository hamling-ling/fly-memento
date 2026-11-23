#!/usr/bin/env bash
# Stream fly-memento logs to this terminal and to a file in logs/.
#
# Ctrl-C stops the stream. The file stays. Pass another destination when
# the board is not uno-q-1:
#
#   scripts/logs_fly-memento.sh
#   scripts/logs_fly-memento.sh arduino@other.local
#   scripts/logs_fly-memento.sh --dry-run
#
# Run from anywhere. The default matches scripts/deploy_fly-memento.sh.
# This app does not write JPEGs, so nothing is copied off the board.

set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
dry_run=0
host=arduino@uno-q-1.local
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=1 ;;
    -*)
      echo "unknown option: ${arg}" >&2
      exit 2
      ;;
    *) host=$arg ;;
  esac
done
remote=ArduinoApps/fly-memento
stamp=$(date +%Y%m%d-%H%M%S)
out=$root/logs/fly-memento-$stamp.log

echo "follow ${host}:~/${remote}"
echo "save ${out}"
echo "Ctrl-C で切る。ログが残る。"

if [[ "$dry_run" -eq 1 ]]; then
  echo "dry-run: arduino-app-cli app logs ~/${remote} --follow --tail 30"
  exit 0
fi

mkdir -p "$root/logs"
ssh=(ssh -o BatchMode=yes -o ConnectTimeout=10)
"${ssh[@]}" "$host" "arduino-app-cli app logs ~/${remote} --follow --tail 30" \
  | tee "$out"

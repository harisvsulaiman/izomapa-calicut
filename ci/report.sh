#!/bin/sh
# Push a job's status and log tail to the "status" branch, so progress can be read with plain git.
# usage: ci/report.sh <name> <status> [logfile...]
NAME=$1; ST=$2; shift 2
TMP=$(mktemp -d); git clone -q --depth 1 --branch status "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" "$TMP" 2>/dev/null || {
  git clone -q --depth 1 "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" "$TMP"; cd "$TMP"; git checkout -q --orphan status; git rm -rqf . ; cd - >/dev/null; }
{ echo "$ST $(date -u +%FT%TZ) run=${GITHUB_RUN_ID}"; for f in "$@"; do [ -f "$f" ] && { echo "== $f"; tail -60 "$f"; }; done; } > "$TMP/$NAME.txt"
cd "$TMP"; git config user.name ci; git config user.email ci@users.noreply.github.com
git add -A; git commit -qm "$NAME $ST" || exit 0
for i in 1 2 3 4 5 6 7 8; do git push -q origin status && exit 0; sleep $((i * 3)); git pull -q --rebase origin status; done

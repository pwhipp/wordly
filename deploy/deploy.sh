#!/usr/bin/env bash
set -euo pipefail

trap 'echo "Deployment failed." >&2' ERR

run_cmd() {
  echo "+ $*" >&2
  "$@"
}

section() {
  echo "" >&2
  echo "==> $*" >&2
}

WORDLY_REPO_DIR="/home/wordly/wordly"
BACKEND_DIR="${WORDLY_REPO_DIR}/backend"
FRONTEND_DIR="${WORDLY_REPO_DIR}/frontend"
CONFIG_URL="${CONFIG_URL:-https://wordly.qclub.au/api/config}"

section "Stopping wordly service as invoking user"
run_cmd sudo systemctl stop wordly

section "Updating repository as wordly user"
run_cmd sudo -u wordly -H bash -lc "cd ${WORDLY_REPO_DIR} && git pull"

section "Updating backend dependencies as wordly user"
run_cmd sudo -u wordly -H bash -lc "cd ${BACKEND_DIR} \
  && python3 -m venv .venv \
  && . .venv/bin/activate \
  && pip install -r requirements.txt"

section "Building frontend as wordly user"
run_cmd sudo -u wordly -H bash -lc "cd ${FRONTEND_DIR} \
  && npm install \
  && VITE_API_BASE_URL=/api npm run build"

section "Rebuilding database as wordly user"
run_cmd sudo -u wordly -H bash -lc "cd ${BACKEND_DIR} \
  && . .venv/bin/activate \
  && python db.py rebuild"

section "Starting services as invoking user"
run_cmd sudo systemctl start wordly
run_cmd sudo systemctl restart nginx

section "Verifying deployed git metadata"
echo "+ curl -fsS ${CONFIG_URL}" >&2
config_json=$(curl -fsS "${CONFIG_URL}")

echo "+ sudo -u wordly -H bash -lc \"cd ${WORDLY_REPO_DIR} && git rev-parse --abbrev-ref HEAD\"" >&2
expected_branch=$(sudo -u wordly -H bash -lc "cd ${WORDLY_REPO_DIR} && git rev-parse --abbrev-ref HEAD")

echo "+ sudo -u wordly -H bash -lc \"cd ${WORDLY_REPO_DIR} && git rev-parse HEAD\"" >&2
expected_head=$(sudo -u wordly -H bash -lc "cd ${WORDLY_REPO_DIR} && git rev-parse HEAD")

reported_branch=$(printf '%s' "${config_json}" | python3 -c "import json,sys; print(json.load(sys.stdin).get('git', {}).get('branch', '') or '')")
reported_head=$(printf '%s' "${config_json}" | python3 -c "import json,sys; print(json.load(sys.stdin).get('git', {}).get('head', '') or '')")

if [[ -z "${reported_branch}" || -z "${reported_head}" ]]; then
  echo "Config endpoint did not report git metadata." >&2
  echo "Response: ${config_json}" >&2
  exit 1
fi

if [[ "${reported_branch}" != "${expected_branch}" || "${reported_head}" != "${expected_head}" ]]; then
  echo "Git metadata mismatch." >&2
  echo "Expected branch: ${expected_branch}" >&2
  echo "Reported branch: ${reported_branch}" >&2
  echo "Expected head: ${expected_head}" >&2
  echo "Reported head: ${reported_head}" >&2
  exit 1
fi

echo "Deployment succeeded. Git metadata matches (${reported_branch}@${reported_head})." >&2

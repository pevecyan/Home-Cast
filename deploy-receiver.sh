#!/usr/bin/env bash
# Deploy receiver files to remote host via scp over SSH.
# Usage: ./deploy-receiver.sh [user@host] [remote-path]

set -e

REMOTE="${1:-root@192.168.1.13}"
REMOTE_PATH="${2:-/data/home-cast-receiver}"
LOCAL_PATH="$(cd "$(dirname "$0")/receiver" && pwd)"

echo "Deploying receiver to ${REMOTE}:${REMOTE_PATH} ..."

# Use a persistent control socket so the passphrase is only entered once
SOCKET="/tmp/deploy-receiver-$$"

ssh -MNf -o ControlPath="${SOCKET}" "${REMOTE}"

ssh -o ControlPath="${SOCKET}" "${REMOTE}" "mkdir -p ${REMOTE_PATH}"

scp -o ControlPath="${SOCKET}" \
    "${LOCAL_PATH}/index.html" \
    "${LOCAL_PATH}/receiver.js" \
    "${LOCAL_PATH}/receiver.css" \
    "${REMOTE}:${REMOTE_PATH}/"

echo "Done. Files deployed:"
ssh -o ControlPath="${SOCKET}" "${REMOTE}" "find ${REMOTE_PATH} -type f | sort"

ssh -O exit -o ControlPath="${SOCKET}" "${REMOTE}" 2>/dev/null || true

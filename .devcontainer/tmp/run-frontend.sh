#!/usr/bin/env bash
set -uo pipefail
cd /workspaces/enterprise-doc-qa/frontend
pkill -f "vite" 2>/dev/null
sleep 1
export NODE_OPTIONS="--max-old-space-size=2048"
nohup pnpm dev > /tmp/vite.log 2>&1 &
echo "vite starting, pid $!"

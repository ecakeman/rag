#!/usr/bin/env bash
# 一键拉起 app 容器内的开发进程(WSL 抖动导致容器重启后执行本脚本恢复)
# 用法: dev-up.sh [--force]   --force 强制重启 backend+vite(代码更新后必须,
#        否则存活旧进程不会加载新代码)
set -uo pipefail

C=enterprise-doc-qa_devcontainer-app-1
WS=/workspaces/enterprise-doc-qa
FORCE="${1:-}"

# 容器活着吗
if ! docker inspect $C >/dev/null 2>&1 || [ "$(docker inspect -f "{{.State.Status}}" $C)" != "running" ]; then
  docker start $C >/dev/null 2>&1 || { echo "[dev-up] app 容器无法启动"; exit 1; }
  sleep 3
fi

# backend 活着吗(8080 ping);--force 时无条件重启
if [ "$FORCE" = "--force" ] || ! docker exec $C curl -s --max-time 2 localhost:8080/api/ping | grep -q pong; then
  echo "[dev-up] 拉起 backend..."
  docker exec -u vscode $C bash $WS/.devcontainer/tmp/run-backend.sh
else
  echo "[dev-up] backend 存活"
fi

# vite 活着吗(5173);--force 时无条件重启
if [ "$FORCE" = "--force" ] || ! docker exec $C curl -s -o /dev/null --max-time 2 localhost:5173/; then
  echo "[dev-up] 拉起 vite..."
  docker exec -u vscode $C bash $WS/.devcontainer/tmp/run-frontend.sh
else
  echo "[dev-up] vite 存活"
fi

sleep 1
docker exec $C curl -s --max-time 2 localhost:8080/api/ping || true

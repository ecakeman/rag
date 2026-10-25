#!/usr/bin/env bash
# M1W2-3 一次性验收:自适应等待存活后立即断言,按实际结果写结论
set -uo pipefail
WS=/home/sancho/projects/enterprise-doc-qa
APP=enterprise-doc-qa_devcontainer-app-1
E=$WS/docs/evidence/M1W2-3-fe.md

wait_backend() {
  for i in $(seq 1 40); do
    docker exec $APP curl -s --max-time 2 localhost:8080/api/ping 2>/dev/null | grep -q pong && return 0
    sleep 3
  done
  return 1
}
wait_vite() {
  for i in $(seq 1 20); do
    docker exec $APP curl -s -o /dev/null --max-time 2 localhost:5173/ 2>/dev/null && return 0
    sleep 3
  done
  return 1
}

bash $WS/.devcontainer/tmp/dev-up.sh >/dev/null 2>&1

R_HTML=""; R_LOGIN=""; R_401=""; R_LIST=""; R_WIN=""

if wait_backend; then
  if ! wait_vite; then
    docker exec -u vscode $APP bash $WS/.devcontainer/tmp/run-frontend.sh >/dev/null 2>&1
    wait_vite || true
  fi
  R_HTML=$(docker exec $APP curl -s -o /dev/null -w "%{http_code}" --max-time 5 localhost:5173/ 2>/dev/null)
  R_LOGIN=$(docker exec $APP curl -s --max-time 8 -X POST localhost:5173/api/auth/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"admin123\"}" 2>/dev/null | head -c 90)
  R_401=$(docker exec $APP curl -s -o /dev/null -w "%{http_code}" --max-time 8 -X POST localhost:5173/api/auth/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"bad\"}" 2>/dev/null)
  TOKEN=$(docker exec $APP curl -s --max-time 8 -X POST localhost:5173/api/auth/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"admin123\"}" 2>/dev/null | sed "s/.*\"token\":\"\([^\"]*\)\".*/\1/")
  R_LIST=$(docker exec $APP curl -s --max-time 8 localhost:5173/api/documents -H "Authorization: Bearer $TOKEN" 2>/dev/null | head -c 130)
  R_WIN=$(curl -s --max-time 5 -o /dev/null -w "%{http_code}" http://localhost:5173/ 2>/dev/null || echo unreachable)
fi

PASS="FAIL"
if [[ "$R_HTML" == "200" && "$R_LOGIN" == *token* && "$R_401" == "401" && "$R_LIST" == *records* ]]; then
  PASS="PASS"
fi

{
  echo "# M1W2-3 前端骨架 验收证据(自适应等待版) — $(date +%F\ %T)"
  echo "## git rev: $(git -C $WS rev-parse --short HEAD)+工作区"
  echo "## 背景: WSL 抖动约2-5分钟一次,容器重启会杀手动进程;本脚本自适应等待存活后立即断言"
  echo
  echo "## ① pnpm build: exit=0, 2.24MB(修复: only-allow→pnpm; vue-demi→devDep)"
  echo
  echo "## ② 容器内 vite 链路(localhost:5173)"
  echo "### GET / (SPA): http_code=$R_HTML"
  echo "### POST /api/auth/login(vite proxy→8080): $R_LOGIN"
  echo "### 错误密码: http_code=$R_401 (期望401)"
  echo "### GET /api/documents(带token): $R_LIST"
  echo
  echo "## ③ Windows 侧尽力而为(经 socat 转发): ${R_WIN:-未测}"
  echo
  echo "## ④ 上传拦截(代码级): 白名单+50MB(beforeUpload, src/views/docs/index.vue L73-77)"
  echo
  echo "## 截图项(挂起,如实记录): 宿主 IAB 无法访问 Docker 转发端口 + WSL 高频抖动;登录页/文档页视觉确认留给用户浏览器"
  echo
  echo "## 结论: $PASS (判定标准: html=200 且登录返回token 且错误密码401 且列表含records)"
} > "$E"

echo "VERDICT=$PASS html=$R_HTML 401=$R_401 win=$R_WIN"

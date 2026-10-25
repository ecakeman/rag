# M1W2-3 前端骨架 验收证据(自适应等待版) — 2026-10-25 16:29:13
## git rev: aa2a88e+工作区
## 背景: WSL 抖动约2-5分钟一次,容器重启会杀手动进程;本脚本自适应等待存活后立即断言

## ① pnpm build: exit=0, 2.24MB(修复: only-allow→pnpm; vue-demi→devDep)

## ② 容器内 vite 链路(localhost:5173)
### GET / (SPA): http_code=200
### POST /api/auth/login(vite proxy→8080): {"code":0,"message":"ok","data":{"token":"eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIiwidXNlcm5hbWU
### 错误密码: http_code=401 (期望401)
### GET /api/documents(带token): {"code":0,"message":"ok","data":{"total":7,"records":[{"id":15,"title":"employee-handbook","fileName":"employee-handbook.md","file

## ③ Windows 侧尽力而为(经 socat 转发): 000unreachable

## ④ 上传拦截(代码级): 白名单+50MB(beforeUpload, src/views/docs/index.vue L73-77)

## 截图项(挂起,如实记录): 宿主 IAB 无法访问 Docker 转发端口 + WSL 高频抖动;登录页/文档页视觉确认留给用户浏览器

## 结论: PASS (判定标准: html=200 且登录返回token 且错误密码401 且列表含records)

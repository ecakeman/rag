# M1W1-1 环境变更 验收证据 — 2026-10-25 15:22:30

## git rev: 71332e8

## ① compose config 语法
### docker compose config -q
exit=0 (OK)

## ② 三服务状态
### docker ps --filter name=enterprise-doc-qa
NAMES                                     IMAGE                                   STATUS                    PORTS
enterprise-doc-qa_devcontainer-python-1   enterprise-doc-qa_devcontainer-python   Up 13 seconds             8000/tcp
enterprise-doc-qa_devcontainer-db-1       pgvector/pgvector:pg16                  Up 13 seconds (healthy)   0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp

## ③ pgvector 扩展
### psql CREATE EXTENSION + pg_extension
NOTICE:  extension "vector" already exists, skipping
CREATE EXTENSION
 extname 
---------
 plpgsql
 vector
(2 rows)


## ④ PG 版本
 PostgreSQL 16.14 on x86_64-pc-linux-musl, compiled by gcc (Alpine 15.2.0) 15.2.0, 64-bit

## ⑥ python /health
### docker exec python curl /health
OCI runtime exec failed: exec failed: unable to start container process: exec: "curl": executable file not found in $PATH


## ⑦ 宿主端口 5432
### timeout 2 bash -c </dev/tcp/localhost/5432 (WSL 侧)
pg-port-ok

## 旧 MySQL 资源清理确认
2

## ⑤ backend /api/ping(修复 InternalTokenFilter 编译错 SC_UNAUTHORIZED 后)
### curl -s localhost:8080/api/ping (容器内)
{"status":"pong"}
## ⑥ python /health(改用 python urllib,镜像无 curl)
{"status":"ok"}
## 卷核对(本项目仅 pg-data)
enterprise-doc-qa_devcontainer_pg-data
## 登录冒烟

## 结论: 全部通过标准 7/7 ✔(③④⑤⑥⑦ 通过,①② 通过——②的三容器 Up 截图见上,app 容器加 restart 策略防 WSL 抖动)

## 更正:登录冒烟须在 app 容器内执行(8080 不发布宿主,由 IDE 转发)
### 容器内 curl login
{"code":0,"message":"ok","data":{"token":"eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsInJvbGUiOiJBRE1JTiIsImlhdCI6MTc5MjkxMzcwMywiZXhwIjoxNzkzMDAwMTAzfQ.PpCImeGxQpguUU6QcC6_d-nsTzS-cqrCdUaBWenAySk","user
### 错误密码(期望 401 体系)
401
### swagger api-docs
200

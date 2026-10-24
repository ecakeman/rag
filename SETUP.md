# 毕设项目开发环境搭建交接文档(enterprise-doc-qa)

> 本文档写给负责执行的 ZCode 会话:按章节顺序执行,做完验证清单(§6)后按 §8 向用户汇报。**业务代码不在本阶段范围**,目标只是搭好可运行的 devcontainer 开发环境。

## 0. 背景与硬性约束(必读)

- 项目:毕业设计《基于 SpringBoot+Vue 的 AI 问答知识库的企业内部文档智能检索系统》。本阶段目标:**devcontainer 环境 + SpringBoot 空项目 + Vue 空项目 + MySQL,三者都能启动**。
- **一切命令在 WSL(Ubuntu-24.04)内执行**,从 Windows 侧用 `wsl.exe -e bash -lc '<命令>'` 进入。项目路径:`/home/sancho/projects/enterprise-doc-qa`(已存在,当前为空)。WSL 用户:`sancho`。
- WSL 已是 mirrored 网络模式,WSL 内可直接用 Windows 代理 `127.0.0.1:7897`(需要时)。**注意:容器内的 127.0.0.1 指容器自身**,容器内要用代理须写 `http://host.docker.internal:7897`。本方案默认不依赖代理,依赖下载统一走国内镜像源(见 §3)。
- Docker 可用(Docker Desktop,引擎 29.6,已验证能拉取 Docker Hub 镜像)。若 `docker ps` 连不上 daemon,先在 Windows 侧启动 Docker Desktop 并等其就绪。
- 用户日常用 Cursor 打开项目(WSL 远程方式);VS Code 同理。需要 Dev Containers 扩展。
- WSL 侧现状(2026-10-24 已验证):node 22 / npm 10.9 / git 2.43 已装,java、maven 未装(将由 devcontainer 提供,不要装在 WSL 系统里)。

## 1. 技术选型(已定,勿改)

| 项 | 选择 |
|---|---|
| 后端 | Java 21 (LTS) + SpringBoot 3.5.x + Maven(用项目自带 mvnw,不全局装 Maven) |
| 前端 | Node 22 (LTS) + Vue 3 + Vite + TypeScript |
| 数据库 | MySQL 8.4(LTS),devcontainer compose 服务名 `db`,库名 `doc_qa` |
| 开发方式 | devcontainer:app 开发容器 + db 容器,Cursor/VS Code "Reopen in Container" |

不引入 mise/conda 等额外工具链管理,运行时全部由容器镜像锁定。

## 2. 目标目录结构

```
enterprise-doc-qa/
├── .devcontainer/
│   ├── devcontainer.json
│   ├── docker-compose.yml
│   ├── post-create.sh
│   └── maven-settings.xml
├── backend/                  # SpringBoot(spring initializr 生成,含 mvnw)
├── frontend/                 # Vue3 + Vite + TS
├── .gitignore
└── SETUP.md                  # 本文档(搭建完成后去留由用户定)
```

## 3. 创建 .devcontainer 四个文件(内容照抄)

**`.devcontainer/devcontainer.json`**

```jsonc
{
  "name": "enterprise-doc-qa",
  "dockerComposeFile": "docker-compose.yml",
  "service": "app",
  "workspaceFolder": "/workspaces/enterprise-doc-qa",
  "features": {
    "ghcr.io/devcontainers/features/node:1": { "version": "22" }
  },
  "customizations": {
    "vscode": {
      "extensions": [
        "vscjava.vscode-java-pack",
        "vmware.vscode-boot-dev-pack",
        "Vue.volar",
        "dbaeumer.vscode-eslint"
      ]
    }
  },
  "forwardPorts": [8080, 5173],
  "portsAttributes": {
    "8080": { "label": "SpringBoot" },
    "5173": { "label": "Vite" }
  },
  "postCreateCommand": "bash .devcontainer/post-create.sh",
  "remoteUser": "vscode"
}
```

**`.devcontainer/docker-compose.yml`**

```yaml
services:
  app:
    image: mcr.microsoft.com/devcontainers/java:21
    command: sleep infinity
    volumes:
      - ..:/workspaces/enterprise-doc-qa:cached
    depends_on:
      db:
        condition: service_healthy

  db:
    image: mysql:8.4
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: root123
      MYSQL_DATABASE: doc_qa
      TZ: Asia/Shanghai
    command: --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
    ports:
      - "3306:3306"        # 若宿主 3306 被占,改成 "13306:3306" 并在汇报里说明
    volumes:
      - mysql-data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-proot123"]
      interval: 5s
      timeout: 3s
      retries: 30

volumes:
  mysql-data:
```

**`.devcontainer/post-create.sh`**(容器构建后自动执行,配国内源)

```bash
#!/usr/bin/env bash
set -euo pipefail
# Maven 走阿里云镜像
mkdir -p ~/.m2
cp .devcontainer/maven-settings.xml ~/.m2/settings.xml
# npm 走 npmmirror
npm config set registry https://registry.npmmirror.com
echo "[post-create] mirrors configured"
```

**`.devcontainer/maven-settings.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0 https://maven.apache.org/xsd/settings-1.0.0.xsd">
  <mirrors>
    <mirror>
      <id>aliyun-public</id>
      <mirrorOf>central</mirrorOf>
      <name>Aliyun Public</name>
      <url>https://maven.aliyun.com/repository/public</url>
    </mirror>
  </mirrors>
</settings>
```

注意:文件用 LF 换行、shell 脚本要有可执行权限(`chmod +x .devcontainer/post-create.sh`,在 WSL 内做)。

**`.gitignore`**(项目根)

```
# backend
backend/target/
*.class

# frontend
frontend/node_modules/
frontend/dist/

# misc
*.log
.env
.idea/
*.iml
```

## 4. 生成后端骨架(SpringBoot)

在**容器内**(Reopen in Container 之后)执行,容器里已有 JDK 和 Maven:

```bash
cd /workspaces/enterprise-doc-qa
curl -fsSL "https://start.spring.io/starter.tgz" \
  -d type=maven-project -d language=java -d bootVersion=3.5.0 \
  -d baseDir=backend -d groupId=com.enterprise -d artifactId=backend \
  -d name=backend -d packageName=com.enterprise.docqa \
  -d javaVersion=21 -d dependencies=web,data-jpa,validation,mysql,lombok \
  | tar -xz
```

- 若 start.spring.io 访问慢/失败,给该次 curl 临时挂代理:`export https_proxy=http://host.docker.internal:7897`,或换用 `https://start.aliyun.com/starter.tgz`(参数含义相同,bootVersion 选 3.5.x 最新)。
- 生成后写两个文件:

**`backend/src/main/resources/application.yml`**(覆盖)

```yaml
spring:
  application:
    name: backend
  datasource:
    url: jdbc:mysql://${DB_HOST:db}:3306/doc_qa?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=Asia/Shanghai&characterEncoding=utf8
    username: root
    password: ${DB_PASSWORD:root123}
    driver-class-name: com.mysql.cj.jdbc.Driver
  jpa:
    hibernate:
      ddl-auto: update
    open-in-view: false
server:
  port: 8080
```

**`backend/src/main/java/com/enterprise/docqa/controller/PingController.java`**(路径按实际包名调整)

```java
package com.enterprise.docqa.controller;

import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class PingController {

    @GetMapping("/ping")
    public Map<String, String> ping() {
        return Map.of("status", "pong");
    }
}
```

## 5. 生成前端骨架(Vue 3 + Vite + TS)

容器内执行:

```bash
cd /workspaces/enterprise-doc-qa
npm create vite@latest frontend -- --template vue-ts
cd frontend && npm install
```

然后把 `frontend/vite.config.ts` 里 dev server 加上 `server: { host: true }`,保证从 Windows 浏览器可访问。

## 6. 验证清单(全部通过才算完成)

- [ ] WSL 内 `docker ps` 正常(daemon 可用)
- [ ] `.devcontainer/` 四文件 + `.gitignore` 就位,`post-create.sh` 有执行权限
- [ ] Cursor/VS Code 以 WSL 远程方式打开 `\\wsl.localhost\Ubuntu-24.04\home\sancho\projects\enterprise-doc-qa`,装 Dev Containers 扩展,执行 **Reopen in Container** 构建成功(首次拉镜像+构建约几分钟)
- [ ] 容器内终端:`java -version` 为 21、`mvn -v` 正常、`node -v` 为 22(扩展装不上可忽略,不影响环境)
- [ ] 容器内:`timeout 2 bash -c '</dev/tcp/db/3306' && echo db-ok` 输出 `db-ok`
- [ ] 容器内:`cd backend && ./mvnw spring-boot:run` 能启动;`curl -s localhost:8080/api/ping` 返回 `{"status":"pong"}`
- [ ] 容器内:`cd frontend && npm run dev` 能启动;**Windows 浏览器**打开 http://localhost:5173 看到 Vite/Vue 初始页
- [ ] (可选)Windows 图形客户端连 `localhost:3306`,root/root123,能看到 `doc_qa` 库

## 7. git 初始化(在 WSL 宿主侧执行即可,容器内外同一目录)

```bash
cd ~/projects/enterprise-doc-qa
git init -b main
git add -A
git commit -m "chore: bootstrap devcontainer dev environment (SpringBoot 3.5 + Vue 3 + MySQL 8.4)"
```

宿主侧已有 git 身份配置;若提示未配置,先 `git config user.name/user.email`(用宿主已有值)。

## 8. 完成后的汇报要求

向用户汇报:① 验证清单逐项结果;② 任何偏离本文档的调整及原因(如端口被占改 13306);③ 凭据与端口汇总(MySQL root/root123、库 doc_qa、3306;后端 8080;前端 5173);④ 日常启动方式一句话(Cursor 打开项目 → Reopen in Container → 容器终端跑 `./mvnw spring-boot:run` 和 `npm run dev`)。

## 9. 故障排查提示(执行时遇到再看)

- **镜像拉取慢/失败**:确认 Docker Desktop 已运行且其代理设置为系统代理;`mysql:8.4`、`mcr.microsoft.com/devcontainers/java:21` 均为公开镜像。
- **node feature(ghcr.io)拉取失败**:重试一次;仍失败可在 Docker Desktop 里确认代理后重建容器(Dev Containers: Rebuild Container)。
- **3306 端口冲突**:改宿主映射端口为 13306,后端连接不受影响(容器内部走服务名 `db:3306`)。
- **start.spring.io 不可达**:见 §4 的代理/阿里云备选。

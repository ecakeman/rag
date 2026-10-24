#!/usr/bin/env bash
set -euo pipefail
# Maven 走阿里云镜像
mkdir -p ~/.m2
cp .devcontainer/maven-settings.xml ~/.m2/settings.xml
# npm 走 npmmirror
npm config set registry https://registry.npmmirror.com
echo "[post-create] mirrors configured"

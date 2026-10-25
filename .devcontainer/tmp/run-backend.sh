#!/usr/bin/env bash
set -uo pipefail
cd /workspaces/enterprise-doc-qa/backend
pkill -f "org.springframework.boot" 2>/dev/null
sleep 1
pkill -9 -f "maven" 2>/dev/null
sleep 1
export MAVEN_OPTS="-Xmx512m"
nohup ./mvnw spring-boot:run > /tmp/backend.log 2>&1 &
echo "backend starting, pid $!"

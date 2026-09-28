#!/usr/bin/env bash
# Собирает бинарник timetrace внутри Docker-контейнера на Debian 12
# (glibc 2.36), а не на хосте, чтобы итоговый бинарник не требовал
# более новую glibc, чем есть у конечных пользователей. Без этого
# сборка на rolling-release дистрибутивах (Arch/CachyOS) с более
# новой glibc даёт бинарник, который падает на Fedora/Debian/Ubuntu
# с ошибкой вида "GLIBC_2.xx not found". Подробности: packaging/docker/README.md.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_TAG="timetrace-build"

docker build -f "$SCRIPT_DIR/docker/Dockerfile" -t "$IMAGE_TAG" "$REPO_ROOT"

CONTAINER_ID="$(docker create "$IMAGE_TAG")"
trap 'docker rm -f "$CONTAINER_ID" >/dev/null' EXIT

mkdir -p "$SCRIPT_DIR/dist"
docker cp "$CONTAINER_ID:/build/packaging/dist/timetrace" "$SCRIPT_DIR/dist/timetrace"
chmod 755 "$SCRIPT_DIR/dist/timetrace"

echo "Собрано: $SCRIPT_DIR/dist/timetrace"

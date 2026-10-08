#!/usr/bin/env bash
# Собирает бинарники timetrace внутри Docker-контейнеров на разных базах,
# а не на хосте, чтобы итоговый бинарник не требовал более новую glibc,
# чем есть у конечных пользователей, и не тащил с собой библиотеки, которые
# конфликтуют с системными на новых дистрибутивах. Подробности:
# packaging/docker/README.md.
#
# Использование: build_in_docker.sh [legacy|standard|modern ...]
# Без аргументов собираются все варианты. Результат: dist/timetrace-<вариант>.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

declare -A BASES=(
    [legacy]="ubuntu:20.04"    # glibc 2.31
    [standard]="ubuntu:22.04"  # glibc 2.35
    [modern]="ubuntu:24.04"    # glibc 2.39
)

VARIANTS=("$@")
[ ${#VARIANTS[@]} -gt 0 ] || VARIANTS=(legacy standard modern)

mkdir -p "$SCRIPT_DIR/dist"

for variant in "${VARIANTS[@]}"; do
    base="${BASES[$variant]:-}"
    [ -n "$base" ] || { echo "Неизвестный вариант: $variant (доступны: ${!BASES[*]})" >&2; exit 1; }
    image="timetrace-build-$variant"

    docker build -f "$SCRIPT_DIR/docker/Dockerfile" --build-arg "BASE_IMAGE=$base" \
        -t "$image" "$REPO_ROOT"

    container="$(docker create "$image")"
    docker cp "$container:/build/packaging/dist/timetrace" "$SCRIPT_DIR/dist/timetrace-$variant"
    docker rm -f "$container" >/dev/null
    chmod 755 "$SCRIPT_DIR/dist/timetrace-$variant"

    echo "Собрано: $SCRIPT_DIR/dist/timetrace-$variant (база $base)"
done

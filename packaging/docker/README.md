# Сборка в Docker (фикс несовместимости glibc)

## Проблема

При запуске `timetrace`, собранного на Arch/CachyOS, на Fedora падает с:

```
ImportError: /lib64/libm.so.6: version `GLIBC_2.44' not found
```

Причина: PyInstaller не бандлит glibc (она жёстко привязана к системному
загрузчику ядра), поэтому нативные расширения линкуются с той версией glibc,
что стоит на машине сборки. CachyOS — rolling-release с glibc 2.44, а у
целевых систем (Fedora, Debian, Ubuntu) glibc обычно старее. Результат —
бинарник, который не запускается нигде, кроме машин с glibc >= 2.44.

## Решение

Собирать `timetrace` не на хосте, а внутри Docker-контейнера на Debian 12
(bookworm, glibc 2.36) — она достаточно старая, чтобы бинарник запускался на
любой актуальной Fedora/Debian/Ubuntu, и достаточно новая для PySide6/Qt6
(wheels ориентированы на manylinux_2_28+).

```bash
./packaging/build_in_docker.sh
```

Скрипт соберёт образ `timetrace-build`, прогонит PyInstaller внутри него и
скопирует результат в `packaging/dist/timetrace` — дальше `build_deb_rpm.sh`
работает без изменений.

## Важно: не проверено в этой сессии

В песочнице, где выполнялась эта задача, у Docker-контейнеров нет доступа к
DNS/сети (подтверждено: `apt-get update` внутри контейнера не резолвит
`deb.debian.org` даже с `--network host`), хотя у хоста сеть есть. Это
ограничение конкретной среды выполнения, а не Dockerfile. Поэтому
`Dockerfile` и `build_in_docker.sh` не были прогнаны до конца — запустите
`./packaging/build_in_docker.sh` на обычной машине (или в CI) и, если
`apt-get`/`pip install` упадут на каком-то пакете, добавьте недостающую
зависимость в список в `Dockerfile`.

После сборки стоит проверить сам бинарник:

```bash
docker run --rm -v "$PWD/packaging/dist:/dist" debian:12-slim /dist/timetrace --help
```

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

Собирать `timetrace` не на хосте, а внутри Docker-контейнеров на Ubuntu
20.04 (`legacy`, glibc 2.31), 22.04 (`standard`, 2.35) и 24.04 (`modern`, 2.39).
Самый старый вариант запускается на системах с glibc 2.31+, а самый новый
бандлит свежие `libstdc++` и др., которые не конфликтуют с системными
библиотеками на rolling-дистрибутивах. Таблица «вариант → ОС» — в корневом README.
`pywayland` собирается из исходников (`--no-binary`), так как его колесо
на PyPI требует glibc 2.34+.

```bash
./packaging/build_in_docker.sh            # все варианты
./packaging/build_in_docker.sh legacy     # один вариант
```

Скрипт соберёт образ `timetrace-build`, прогонит PyInstaller внутри него и
скопирует результат в `packaging/dist/timetrace-<вариант>` — дальше `build_deb_rpm.sh`
работает без изменений.

## Проверка

Все три варианта проверены запуском (`--help`, `QT_QPA_PLATFORM=offscreen`) в контейнерах Ubuntu 20.04/22.04/24.04, Debian 11/12/13, Fedora и Arch. Реальную работу под X11/Wayland и трей в контейнерах проверить нельзя.

После сборки стоит проверить сам бинарник:

```bash
docker run --rm -v "$PWD/packaging/dist:/dist" ubuntu:22.04 /dist/timetrace-standard --help
```

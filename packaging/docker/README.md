# Единые пакеты TimeTrace

Выпуск содержит три установщика: `.deb`, `.rpm`, Arch `.pkg.tar.zst`.
Поддерживаются Linux x86_64 с glibc ≥2.31. Имена вариантов сборки пользователю
выбирать не требуется.

В каждом пакете `/usr/bin/timetrace` — небольшой POSIX shell launcher. Внутри
`/usr/lib/timetrace/` находятся три private runtime, собранные на Ubuntu
20.04 (glibc 2.31), 22.04 (2.35), 24.04 (2.39). Launcher читает
`getconf GNU_LIBC_VERSION` и запускает новейший совместимый runtime, передавая
аргументы без изменений. Выбор выполняется при каждом запуске, поэтому обновление
дистрибутива или смена DE не требует переустановки пакета. Объём пакета больше,
чем у прежнего отдельного runtime: это цена автоматического выбора.

Runtime для glibc 2.31 использует Qt/PySide6 6.9.3; для 2.35 и 2.39 — 6.12.0.
Qt/Python находятся внутри runtime, glibc берётся из системы. Fontconfig и FreeType
также остаются системными: их копии из старой Ubuntu конфликтовали с конфигурацией
новых Fedora/openSUSE. Системные GL/EGL, XKB, Wayland, D-Bus и библиотеки шрифтов
объявлены зависимостями пакетов. Рабочие API выбирает сама программа при входе
пользователя; installer не включает расширения оболочки от root.

## Сборка

```sh
bash packaging/build_in_docker.sh
docker build -f packaging/docker/Dockerfile.fpm -t timetrace-fpm .
docker run --rm -v "$PWD:/source" -w /source timetrace-fpm bash packaging/build_deb_rpm.sh
bash packaging/build_arch.sh
bash packaging/test_packages.sh
```

Результат: три пакета в `packaging/out/`. Версия берётся из `pyproject.toml`.
Arch-пакет сохраняет имя `timetrace-git` для обновления существующих установок;
`PKGBUILD` использует payload того же `.deb` и проверяет его SHA256. При локальной
сборке `build_arch.sh` подставляет checksum собранного `.deb`; перед релизом этот
checksum записывается и в опубликованный `packaging/PKGBUILD`.

`test_packages.sh` устанавливает пакеты с зависимостями в чистые контейнеры Ubuntu
20.04/22.04/24.04, Debian 12/13, Fedora и Arch и проверяет запуск Qt через offscreen.
Отдельные тесты проверяют настоящий headless Sway и labwc с нативными Wayland-клиентами,
COSMIC wire protocol на тестовом C-сервере и X11 fallback на Xvfb.
`_cffi_backend` включается явно: он загружается pywayland динамически и без него
frozen-приложение не может использовать Wayland даже при успешном запуске Qt.

Проверки glibc и offscreen не заменяют проверки графических драйверов и полноценного
сеанса каждого DE. Матрица конкретных API и ограничений — в
[docs/compatibility.md](../../docs/compatibility.md).

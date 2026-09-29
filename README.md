# TimeTrace

Трекер времени для KDE и GNOME (Linux). Показывает, в каких приложениях и окнах вы провели день, отслеживает простой (idle) и переходы в спящий режим, живёт в системном трее.

## Возможности

- **Таймлайн дня** — две дорожки: активность по приложениям и простой/активность, с переходом по дням.
- **Обнаружение простоя (idle)** — через X11, GNOME (Mutter/IdleMonitor) или KDE Wayland (`ext-idle-notify-v1`), порог настраивается.
- **Обнаружение сна** — засыпание/пробуждение системы отмечаются на таймлайне отдельно от простоя.
- **Системный трей** — окно сворачивается в трей вместо закрытия; иконка трея пропускается, если у окружения нет `StatusNotifierWatcher` (например, GNOME без соответствующего расширения).
- **Автозагрузка** — запуск при входе в систему сразу в трей, без открытия окна на рабочем столе.
- **Тема** — светлая, тёмная или системная, со слежением за сменой темы GTK/Qt на лету.
- **Один экземпляр приложения** — повторный запуск через D-Bus поднимает и активирует уже открытое окно вместо второго процесса.

## Поддерживаемые окружения

| DE / сессия      | Определение простоя         | Определение активного окна |
|-------------------|------------------------------|------------------------------|
| GNOME / Wayland   | GNOME IdleMonitor (D-Bus)    | GNOME Shell extension        |
| KDE / Wayland      | `ext-idle-notify-v1`         | KWin script                  |
| X11 (любое DE)     | XScreenSaver extension       | X11 (`_NET_ACTIVE_WINDOW`)   |

## Установка

Готовые пакеты — на странице [Releases](https://github.com/post-code-FF/timetrace/releases):

- `.deb` / `.rpm` — через `dpkg -i` / `rpm -i` (или менеджер пакетов дистрибутива);
- Arch Linux — `PKGBUILD` в `packaging/PKGBUILD` (`makepkg -si`), качает бинарник из GitHub Releases;
- отдельный бинарник `timetrace` — скачать и положить в `$PATH` (например, `/usr/bin/timetrace`).

### Из исходников

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
timetrace
```

Требуется Python ≥ 3.11.

## Разработка

```bash
# тесты
pip install -e ".[dev]"
pytest

# ручной запуск
python -m timetrace
```

Структура проекта:

- `src/timetrace/backends/` — бэкенды простоя/активного окна/сна для X11, GNOME, KDE Wayland;
- `src/timetrace/tracking/` — координатор, склеивающий события бэкендов в записи БД;
- `src/timetrace/ui/` — главное окно, таймлайн, список приложений, трей, диалог настроек;
- `src/timetrace/assets/` — GNOME Shell extension и KWin script, устанавливаемые бэкендами активного окна;
- `packaging/` — PyInstaller-спека, сборка `.deb`/`.rpm` через `fpm`, Arch `PKGBUILD`, сборка бинарника в Docker (для совместимости по glibc).

## Сборка пакетов

См. скрипты в `packaging/`:

- `packaging/build_in_docker.sh` — собирает бинарник `timetrace` в Docker-контейнере на Debian 12 (совместимость по glibc с более старыми дистрибутивами);
- `packaging/build_deb_rpm.sh` — упаковывает собранный бинарник в `.deb` и `.rpm` через [`fpm`](https://github.com/jordansissel/fpm).

## Лицензия

MIT

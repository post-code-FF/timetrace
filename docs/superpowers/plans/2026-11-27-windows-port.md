# Windows Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Выпустить один нативный TimeTrace.exe x64 для Windows 8.1/10/11, сохранив Linux-версию, UI и учёт времени.

**Architecture:** Общие PySide6 UI, SQLite и TrackingCoordinator остаются источником поведения. Платформенные фабрики выбирают Linux- или Windows-адаптеры; Windows-адаптеры используют Win32 для фокуса, idle, сна, темы, автозагрузки и single-instance. PyInstaller собирает Windows onefile отдельно от существующей Linux-упаковки.

**Tech Stack:** Python 3.12 x64, PySide6 6.12, ctypes/Win32, sqlite3, pytest/pytest-qt, PyInstaller 6.22.

**Spec:** `docs/superpowers/specs/2026-11-27-windows-port-design.md`

## Global Constraints

- Целевые ОС: Windows 8.1, 10, 11 x64; Windows 7/8.0 не поддерживаются.
- Один пользовательский артефакт: `TimeTrace.exe`, PyInstaller onefile, без консоли.
- Не менять Linux-бэкенды, Linux packaging, схему SQLite, алгоритм координатора и визуальные тексты/палитры UI.
- Не использовать Docker; все проверки выполняются локально.
- Не устанавливать `pywayland` на Windows; Linux-only тесты маркировать, а не удалять.
- Не заявлять фактическую проверку Windows 8.1 без запуска на этой ОС.
- Коммиты и push выполняются от настроенного пользователя, без Co-authored-by ассистента.

## Review Focus

1. Смена фокуса между процессами с одинаковым заголовком: интервал приложения должен переключаться по стабильному идентификатору процесса, а не склеиваться.
2. Порог idle и полноэкранное окно: ввод должен возобновлять активность, fullscreen должен сохранять активность без ввода.
3. Сон/пробуждение и завершение процесса: открытые интервалы должны закрываться корректно, heartbeat не должен создавать фиктивную активность после сна.
4. Повторный запуск и автозагрузка: второй exe поднимает первое окно; Run-ключ содержит актуальный абсолютный путь и удаляется при выключении.
5. Пути с пробелами/Unicode и отсутствие APPDATA: настройки и БД остаются в пользовательском каталоге, запуск не падает.

---

### Task 1: Платформенные зависимости и базовая совместимость

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Modify: `src/timetrace/package_restart.py`
- Modify: `tests/conftest.py`
- Create: `tests/test_platform_support.py`

**Interfaces:**
- Produces: `timetrace.platform_support.IS_WINDOWS`, `IS_LINUX`; безопасный импорт Linux maintenance только на Linux.

- [ ] Написать тесты, что Windows-зависимости не требуют pywayland/Xlib, а Linux markers сохраняют текущие зависимости; проверить импорт `package_restart` на Windows.
- [ ] Запустить новые тесты и зафиксировать ожидаемый провал до реализации.
- [ ] Добавить platform markers и условный Linux-only импорт `pwd`/maintenance; сохранить Linux API без изменения поведения.
- [ ] Маркировать Linux-only тесты по платформе и добавить Windows-маршрут тестов.
- [ ] Запустить базовый Windows-набор и общие тесты; зафиксировать результат.
- [ ] Commit: `feat: add Windows platform dependency boundaries`.

### Task 2: Пути, конфигурация и автозагрузка Windows

**Files:**
- Modify: `src/timetrace/paths.py`
- Modify: `src/timetrace/autostart.py`
- Create: `tests/test_windows_paths.py`
- Create: `tests/test_windows_autostart.py`

**Interfaces:**
- Produces: существующие `config_dir()`, `data_dir()`, `config_file_path()`, `db_file_path()` с Windows-ветвью; `is_autostart_enabled()` и `set_autostart_enabled(enabled, exec_path=...)` с HKCU Run.

- [ ] Написать failing tests для APPDATA/LOCALAPPDATA, Unicode/пробелов, fallback и сохранения TOML.
- [ ] Написать failing tests для создания/удаления Run-значения с подменяемым реестром и абсолютным путём exe.
- [ ] Реализовать Windows-пути и реестр через стандартный `winreg`, сохранив XDG и `.desktop` на Linux.
- [ ] Проверить новые тесты и существующие `test_paths.py`, `test_config.py`, `test_autostart.py`.
- [ ] Commit: `feat: add Windows storage and autostart integration`.

### Task 3: Win32 active-window backend

**Files:**
- Create: `src/timetrace/backends/window_windows.py`
- Modify: `src/timetrace/backends/window_factory.py`
- Create: `tests/test_window_windows.py`

**Interfaces:**
- Consumes: `ActiveWindowBackend.start(on_window_changed)` и `stop()`.
- Produces: `WindowsActiveWindowBackend` с событиями `(resource_class, window_title, timestamp_ms)`; опциональные `start_fullscreen_monitor(callback)` и `update_threshold(ms)` совместимы с координатором.

- [ ] Написать failing tests с fake Win32 layer: фокус, заголовок, PID/путь, смена приложения, отсутствие окна, fullscreen и остановка таймера.
- [ ] Реализовать backend на ctypes: foreground window, текст, PID, путь процесса, геометрия монитора; не трогать координатор.
- [ ] Подключить выбор Windows в фабрике до Linux-ветвей; Linux-выбор оставить прежним.
- [ ] Проверить Windows backend tests и существующие factory/coordinator tests.
- [ ] Commit: `feat: track active Windows applications`.

### Task 4: Idle и сон Windows

**Files:**
- Create: `src/timetrace/backends/idle_windows.py`
- Create: `src/timetrace/backends/sleep_windows.py`
- Modify: `src/timetrace/backends/idle_factory.py`
- Modify: `src/timetrace/__main__.py`
- Create: `tests/test_idle_windows.py`
- Create: `tests/test_sleep_windows.py`

**Interfaces:**
- Consumes: `IdleBackend.start(threshold_ms, on_idle, on_resume)`, `update_threshold`, `stop`; `SleepBackend.start(on_sleep, on_wake)`, `stop`.
- Produces: `WindowsIdleBackend` на `GetLastInputInfo`; `WindowsSleepMonitor` на сообщениях питания.

- [ ] Написать failing tests для перехода idle/resume ровно на пороге, изменения порога, tick counter wraparound и остановки.
- [ ] Написать failing tests для suspend/resume сообщений и идемпотентного stop.
- [ ] Реализовать адаптеры и платформенный выбор; сохранить Null fallback при недоступном API.
- [ ] Проверить новые тесты и coordinator tests на активный/idle/sleep интервалы.
- [ ] Commit: `feat: add Windows idle and sleep tracking`.

### Task 5: Имена, иконки и тема Windows

**Files:**
- Modify: `src/timetrace/app_names.py`
- Modify: `src/timetrace/icons.py`
- Modify: `src/timetrace/theme.py`
- Create: `src/timetrace/windows_apps.py`
- Create: `tests/test_windows_apps.py`
- Create: `tests/test_windows_theme.py`

**Interfaces:**
- Produces: Windows resolver имени/иконки по пути exe; `read_system_color_scheme()` и `watch_system_color_scheme()` с Windows-реализацией, сохраняющие существующий контракт.

- [ ] Написать failing tests для имён exe, version metadata, Steam libraryfolders.vdf/acf, fallback и извлечения иконки.
- [ ] Написать failing tests для светлой/тёмной системной темы и смены настройки без изменения палитр.
- [ ] Реализовать Windows-ветви, оставив Linux `.desktop`/XDG/портал нетронутыми.
- [ ] Проверить app_names/icons/theme tests и визуальные snapshot/widget tests.
- [ ] Commit: `feat: integrate Windows application metadata and theme`.

### Task 6: Single-instance и жизненный цикл Windows

**Files:**
- Modify: `src/timetrace/__main__.py`
- Create: `src/timetrace/single_instance_windows.py`
- Create: `tests/test_single_instance_windows.py`
- Create: `tests/test_main_bootstrap_windows.py`

**Interfaces:**
- Produces: `WindowsSingleInstance.acquire(name, on_raise)` с mutex и локальным IPC; возвращает primary/secondary и cleanup.

- [ ] Написать failing tests: первый запуск владеет mutex, второй вызывает raise, cleanup освобождает ресурсы, ошибка IPC не создаёт второе окно.
- [ ] Написать failing bootstrap tests для `--minimized`, `--version`, сигналов/выхода и отсутствия D-Bus на Windows.
- [ ] Реализовать Windows single-instance и платформенную сборку приложения; Linux D-Bus путь сохранить.
- [ ] Проверить lifecycle tests и ручной запуск двух процессов.
- [ ] Commit: `feat: add Windows single-instance lifecycle`.

### Task 7: Windows exe и документация

**Files:**
- Create: `packaging/windows.spec`
- Create: `packaging/build_windows.ps1`
- Create: `packaging/windows_entry_point.py`
- Create: `docs/windows.md`
- Modify: `README.md`
- Create: `tests/test_windows_packaging.py`

**Interfaces:**
- Produces: `packaging/out/TimeTrace.exe` и `SHA256SUMS`; команда локальной сборки без Docker.

- [ ] Написать failing packaging tests: onefile, x64, console=False, assets включены, Linux-only modules исключены, имя артефакта стабильно.
- [ ] Создать Windows spec/entry point/script, не меняя Linux spec и release workflow.
- [ ] Собрать exe локально в `.venv`; проверить запуск, PE machine type, размер и SHA256.
- [ ] Провести ручной smoke test: окно, настройки, трей, история, смена дня, повторный запуск, автозагрузка.
- [ ] Обновить README и Windows-инструкцию с честной границей Windows 8.1+ и отсутствием теста на 8.1.
- [ ] Commit: `feat: package TimeTrace as a Windows executable`.

### Task 8: Финальная проверка и публикация

**Files:**
- Modify only if verification reveals a defect in files above.

- [ ] Запустить полный Windows-набор тестов и доступные общие тесты; сохранить точный вывод.
- [ ] Проверить `git diff main...windows-port`, отсутствие изменений Linux-бэкендов/packaging и отсутствие секретов/временных файлов.
- [ ] Провести финальное ревью всего порта и исправить подтверждённые замечания.
- [ ] Объединить проверенную ветку в `main`, запушить от имени пользователя.
- [ ] Создать новый релиз с `TimeTrace.exe` и SHA256; не перезаписывать существующие Linux-артефакты.
- [ ] Сообщить пользователю ссылки, результаты проверок и ограничение по фактическому тесту Windows 8.1.
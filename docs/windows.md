# TimeTrace для Windows

## Готовый файл

`TimeTrace.exe` — один x64-файл для Windows 8.1, 10 и 11. Python и Docker пользователю не нужны.

Запустите файл двойным щелчком. При закрытии окна приложение остаётся в системном трее; выход доступен через меню трея. Повторный запуск поднимает уже открытое окно.

## Хранение данных

- настройки: `%APPDATA%\TimeTrace\config.toml`;
- история: `%LOCALAPPDATA%\TimeTrace\data.db`.

Автозагрузка включается в настройках и создаёт значение `TimeTrace` в `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` только для текущего пользователя.

## Возможности

Учёт активного приложения и заголовка окна, простой по вводу мыши/клавиатуры, освобождение от простоя для полноэкранного окна, отметки сна/пробуждения, таймлайн дня, список приложений, светлая/тёмная/системная тема и трей. Интерфейс и формат истории общие с Linux-версией.

## Сборка из исходников

Требуется Python 3.12 x64:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e . pyinstaller pillow
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```

Результат: `packaging\out\TimeTrace.exe` и `packaging\out\SHA256SUMS`.

## Совместимость

Windows 7 и Windows 8.0 не поддерживаются. Современные Python/Qt не гарантируют запуск на этих системах.

Сборка проверяется локально на Windows 11 x64. Фактический запуск на Windows 8.1 требует отдельного устройства или VM и не заявляется как выполненный без такой проверки.
# TimeTrace GNOME Fork — Arch Linux x86_64

Самостоятельная PyInstaller-сборка: Python и .venv для запуска не нужны.
Пакет собран на Arch Linux; не предназначен для старых дистрибутивов.
Оригинальный timetrace-git может оставаться установленным.

Установка (выполняется пользователем):

    sudo pacman -U ./timetrace-gnome-fork-0.1.4.gnome51.1-1-x86_64.pkg.tar.zst

Запуск из меню: TimeTrace GNOME Fork (синяя иконка).
Команда: timetrace-gnome-fork
Диагностика: TIMETRACE_DEBUG=1 timetrace-gnome-fork

Оригинальная база не изменяется. Форк использует:
~/.local/share/timetrace-gnome-fork/data.db
~/.config/timetrace-gnome-fork/config.toml
В этом сеансе копия истории уже создана.

Пакет содержит расширение в /usr/share/gnome-shell/extensions/timetrace-fork@local.
Ранее установленная пользовательская копия того же UUID имеет приоритет.
Для текущей сборки обе копии одинаковы; менять их при установке не требуется.
При будущих обновлениях пользовательскую копию нужно отдельно обновить либо
сохранить за пределами каталога extensions и перейти на системную копию,
после чего выйти/войти. Не удаляйте оригинальное timetrace@timetrace.app.

На новой системе после установки выйдите и войдите в GNOME, затем выполните:

    gnome-extensions enable timetrace-fork@local
    gnome-extensions info timetrace-fork@local

Нужно состояние ACTIVE. Автозагрузка включается только через настройки форка.
Перед переходом с запущенной версии из исходников закройте её через трей/терминал:
одновременно запускается только один экземпляр форка.

Откат: закройте форк и запустите /usr/bin/timetrace. Удаление пакета не удаляет
пользовательские базы; удалять их для отката не нужно.

Upstream: https://github.com/post-code-FF/timetrace, c9c7bf2.
Upstream README и Arch-пакет объявляют MIT; отдельный LICENSE в дереве отсутствует.
Новая синяя иконка подготовлена для локального форка.

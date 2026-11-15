# Совместимость TimeTrace с окружениями Linux

Проверка исходников окружений: **15 ноября 2026 года**. Документ описывает реализацию
этой ветки TimeTrace и доступные upstream API. Название DE само по себе не определяет
совместимость: важны тип сеанса, оконный менеджер, его версия и включённые протоколы.
**Наличие backend и подходящего upstream API не означает проверку в живом сеансе.**
Строки ниже описывают совместимость по коду/протоколу. Проверен настоящий headless
Sway 1.9 и labwc 0.7.1: два нативных клиента, focus, fullscreen после отображения
окна, закрытие и ext-idle-notify. Для labwc 0.7.1 обнаружено upstream-ограничение:
fullscreen, запрошенный клиентом до map, не всегда публикуется в foreign-toplevel.
Проверены также: готовые frozen runtime → Sway → SQLite; ICCCM input focus на
Xvfb без WM; COSMIC v2 на тестовом C-сервере с настоящим Wayland wire protocol;
Cinnamon snapshot и GNOME/KWin scripts на GJS, GNOME bridge на private D-Bus.
Это не заменяет живой сеанс COSMIC/Cinnamon. Остальные строки не следует читать
как сертификацию всех версий окружения.

Исходный инвентарь названий: [каталог OpenNET](https://opennet.dev/mp/x/),
[новости окружений](https://opennet.ru/opennews/index.shtml?lines=20&mid_lines=00&news=open&section=126&template=0),
[новости оконных менеджеров](https://opennet.ru/opennews/index.shtml?news=open&section=26&skip=15&template=0).
Дополнительно проверены [каталог Pingvinus](https://pingvinus.ru/gui),
[его список DE](https://pingvinus.ru/gui/desktop-environment) и
[список WM](https://pingvinus.ru/gui/window-managers): все 19 названий учтены.
[DistroWatch](https://distrowatch.com/) блокировал доступ к каталогу, поэтому
полнота его актуального списка не подтверждена; исторические списки не выдаются
за состояние всех проектов на текущую дату.
Каталог помогает находить проекты; технические выводы ниже опираются на первичные источники.

## Как читать поддержку

Полный маршрут означает три независимые возможности: активное приложение/заголовок,
простой пользователя и fullscreen активного окна. Последняя нужна, чтобы просмотр
полноэкранного видео не превращался в «Не у компьютера». Без подтверждённого fullscreen
TimeTrace продолжает обычный учёт простоя; размер окна не служит доказательством fullscreen.
Значения «условно» и «частично» указывают конкретное ограничение, а не проведённый runtime-тест.

Готовые пакеты предназначены для **Linux x86_64 с glibc ≥2.31**. Подходящий
встроенный runtime выбирается автоматически. Это отдельное условие от поддержки DE/WM;
набор и версии окружений определяются дистрибутивом. Для запуска из исходников нужен
Python ≥3.11 и зависимости проекта. ARM, musl и другие ОС этой матрицей не покрываются.

## X11: общий backend вместо адаптера на каждый DE

TimeTrace читает EWMH `_NET_ACTIVE_WINDOW`, имя, класс и fullscreen активного окна.
Если EWMH focus недоступен, используется core X11 `GetInputFocus` с подъёмом по
предкам к ICCCM `WM_STATE`, затем к подходящему `WM_CLASS`. `None`, `PointerRoot`
и корневое окно не считаются приложением. Простой поступает из XScreenSaver extension.
Fallback помогает старым WM, но не создаёт отсутствующую поддержку fullscreen.
Дополнительно проверены [Moksha](https://github.com/JeffHoogland/moksha/blob/master/src/bin/e_hints.c),
[AfterStep](https://github.com/afterstep/afterstep/blob/master/src/afterstep/ewmh.c),
[WMFS](https://github.com/xorg62/wmfs/blob/master/src/ewmh.c) — общий EWMH;
[flwm](https://github.com/bbidulock/flwm) — ICCCM focus fallback, fullscreen не подтверждён.
Regolith использует i3 на X11 и Sway на Wayland: [официальная установка](https://regolith-desktop.com/docs/using-regolith/install/).
Основания: [EWMH](https://specifications.freedesktop.org/wm/latest-single/),
[XGetInputFocus](https://xorg.freedesktop.org/archive/X11R7.5/doc/man/man3/XGetInputFocus.3.html),
[ICCCM WM_STATE](https://xorg.freedesktop.org/archive/current/doc/xorg-docs/icccm/icccm.html#WM_STATE_Property).

| DE / WM в сеансе X11 | Маршрут и подтверждение upstream |
|---|---|
| GNOME / Mutter; Cinnamon / Muffin | EWMH: [Mutter](https://github.com/GNOME/mutter/blob/main/src/x11/meta-x11-display.c), [Muffin](https://github.com/linuxmint/muffin/blob/master/src/x11/meta-x11-display.c). Нужен существующий X11-сеанс соответствующей версии. |
| KDE Plasma / KWin | Общий X11 backend; Wayland bridge не используется. Проверять свойства фактического WM. |
| MATE / Marco | EWMH: [Marco](https://github.com/mate-desktop/marco/blob/master/src/core/display.c). |
| Xfce / Xfwm4 | Active/fullscreen: [netwm.c](https://github.com/xfce-mirror/xfwm4/blob/master/src/netwm.c). |
| LXDE / Openbox | EWMH: [Openbox](https://openbox.org/credits); [LXDE session](https://github.com/lxde/lxsession/blob/master/data/desktop.conf.example). |
| LXQt | Зависит от выбранного WM: Openbox, KWin, Xfwm4 и др.; [официальный список](https://github.com/lxqt/lxqt/wiki/Window-managers-%28X11%29). |
| Budgie ≤10.9 / Magpie; Pantheon / Gala | Mutter-производные: [Magpie](https://github.com/BuddiesOfBudgie/magpie), [Gala](https://github.com/elementary/gala/blob/master/README.md); версия сеанса требует проверки. |
| Deepin с deepin-metacity | EWMH подтверждён [исходником](https://github.com/linuxdeepin/deepin-metacity/blob/master/src/core/display.c); не переносить на все современные Deepin-сеансы. |
| Lumina / Fluxbox | Общий EWMH; [Lumina session](https://github.com/lumina-desktop/lumina/blob/master/src-qt5/core/lumina-desktop/LSession.cpp). |
| Unity / Compiz | EWMH active/fullscreen: [Compiz](https://github.com/compiz-reloaded/compiz/blob/master/src/display.c); зависит от реального WM. |
| FVWM3, Window Maker, IceWM | EWMH active/fullscreen: [FVWM3](https://github.com/fvwmorg/fvwm3/blob/master/fvwm/ewmh.c), [Window Maker](https://github.com/window-maker/wmaker/blob/master/src/wmspec.c), [IceWM](https://github.com/ice-wm/icewm/blob/master/src/wmapp.cc). |
| Fluxbox, Blackbox, JWM, pekwm | EWMH: [Fluxbox](https://github.com/fluxbox/fluxbox/blob/master/src/Ewmh.cc), [Blackbox](https://github.com/bbidulock/blackboxwm/blob/master/src/blackbox.cc), [JWM](https://joewing.net/projects/jwm/ewmh.html), [pekwm](https://github.com/pekdon/pekwm/blob/master/src/wm/WindowManager.cc). |
| i3, bspwm, awesome | EWMH: [i3](https://github.com/i3/i3/blob/next/src/ewmh.c), [bspwm](https://github.com/baskerville/bspwm/blob/master/src/ewmh.c), [awesome](https://github.com/awesomeWM/awesome/blob/master/ewmh.c). |
| Qtile X11, dwm | EWMH: [Qtile](https://github.com/qtile/qtile/blob/master/libqtile/backend/x11/core.py), [vanilla dwm](https://git.suckless.org/dwm/file/dwm.c.html); обязательный патч для dwm не требуется. |
| xmonad | Нужны `ewmh`, для fullscreen — `ewmhFullscreen`: [документация hooks](https://xmonad.github.io/xmonad-docs/xmonad-contrib-0.18.1/XMonad-Hooks-EwmhDesktops.html). |
| herbstluftwm, spectrwm | EWMH active/fullscreen: [herbstluftwm](https://herbstluftwm.org/NEWS), [spectrwm](https://github.com/conformal/spectrwm/blob/master/spectrwm.c). |
| Sawfish, Notion, CTWM | EWMH: [Sawfish](https://github.com/SawfishWM/sawfish/blob/master/lisp/sawfish/wm/state/wm-spec.jl), [Notion](https://github.com/raboof/notion/blob/master/ioncore/netwm.c), [CTWM](https://github.com/ctwm-wm/ctwm/blob/master/ewmh.c). CTWM нельзя приравнивать к twm. |
| CDE / dtwm | Current upstream принял `_NET_ACTIVE_WINDOW`; старые пакеты требуют fallback: [проект CDE, MR #137](https://sourceforge.net/projects/cdesktopenv/). Fullscreen отдельно не подтверждён. |
| ratpoison | Core-focus fallback; в [1.4.9](https://download.savannah.nongnu.org/releases/ratpoison/ratpoison-1.4.9.tar.gz) EWMH active/fullscreen не найдены. Окно во весь frame не считается fullscreen. |
| twm, vtwm, mwm, olwm, aewm, lwm, evilwm, wmii, StumpWM, EXWM, LeftWM | Общий fallback предусмотрен; конкретные версии и поведение focus/fullscreen требуют живой проверки. |
| Trinity/TWin, Enlightenment X11, EDE/edeWM, Matchbox и другие forks | Выбирается общий X11 backend; отдельное подтверждение всех нужных свойств в этом исследовании не получено. |

## Wayland: возможности предоставляет композитор

Обычный Wayland-клиент не получает глобальный focus из `wl_seat`. TimeTrace выбирает
GNOME/KWin/Cinnamon bridge либо ищет подходящие globals в Wayland registry. Это
позволяет работать и в неназванном DE поверх поддерживаемого композитора.
`ext_foreign_toplevel_list_v1` **сам по себе не сообщает activated/fullscreen**:
нужен wlr-management или COSMIC info. См. [ext-list XML](https://gitlab.freedesktop.org/wayland/wayland-protocols/-/blob/main/staging/ext-foreign-toplevel-list/ext-foreign-toplevel-list-v1.xml).

В таблице **wlr** означает `zwlr_foreign_toplevel_manager_v1` с title/app_id,
activated и fullscreen (fullscreen требует версии ≥2); **idle** — отдельный
`ext_idle_notifier_v1`. Одного слова «wlroots» для гарантии обоих недостаточно.

| Сеанс / композитор | Активное окно и fullscreen | Простой / условие |
|---|---|---|
| GNOME 51 / Mutter | Расширение TimeTrace; [инструкция](gnome.md) | GNOME bridge передаёт input idle и блокировку; иногда нужен повторный вход. |
| KDE Plasma / KWin | Устанавливаемый KWin script | Общий ext-idle; тот же KWin-маршрут возможен для других оболочек. |
| Cinnamon / Muffin | Снимок `org.Cinnamon.Eval`: приложение, title, fullscreen | `Meta.IdleMonitor.get_core().get_idletime()` и lock; фиксированный read-only запрос каждые 500 мс, без расширения. Нужен доступный [Eval API](https://github.com/linuxmint/cinnamon/blob/master/js/ui/cinnamonDBus.js). |
| Sway, SwayFX | wlr | idle; [Sway server](https://github.com/swaywm/sway/blob/master/sway/server.c), [views](https://github.com/swaywm/sway/blob/master/sway/tree/view.c), [SwayFX](https://github.com/WillPower3309/swayfx/blob/master/sway/server.c). |
| labwc | wlr | idle; [window states](https://github.com/labwc/labwc/blob/master/src/foreign-toplevel/wlr-foreign.c), [idle](https://github.com/labwc/labwc/blob/master/src/idle.c). |
| Wayfire | wlr при включённом `foreign-toplevel` | idle; [плагин](https://github.com/WayfireWM/wayfire/blob/master/plugins/protocols/foreign-toplevel.cpp), [пример config](https://github.com/WayfireWM/wayfire/blob/master/wayfire.ini). |
| MangoWM / MangoWC 0.18.5 | wlr: фактическая публикация app_id/title/activated/fullscreen | ext idle. `idle_inhibit_when_fullscreen` и `idle_inhibit_when_focus` могут искусственно сбрасывать даже input idle; по умолчанию выключены. [manager/idle](https://github.com/mangowm/mango/blob/12ffe9f37fab6a5f8b7951ad37530213c98a9865/src/main.c), [fullscreen](https://github.com/mangowm/mango/blob/12ffe9f37fab6a5f8b7951ad37530213c98a9865/src/manage/client.c#L3653), [keep-awake](https://github.com/mangowm/mango/blob/12ffe9f37fab6a5f8b7951ad37530213c98a9865/src/manage/misc.c#L821). Живой сеанс не проверен: для сборки недоступны wlroots-0.20, SceneFX-0.5, libcjson. |
| UKUI с ukui-kwin | Отдельный профиль `org.ukui.KWin`, old-style script paths и `clientActivated` | ext idle либо KDE idle fallback; [D-Bus](https://github.com/ukui/ukui-kwin/blob/master/dbusinterface.cpp), [scripting](https://github.com/ukui/ukui-kwin/blob/master/scripting/scripting.cpp), [idle](https://github.com/ukui/ukui-kwin/blob/master/wayland_server.cpp). Точный fork определяется по D-Bus, не по имени DE. |
| Hyprland | wlr; запасной прямой IPC-сокет | idle; [protocol manager](https://github.com/hyprwm/Hyprland/blob/main/src/managers/ProtocolManager.cpp). IPC опрашивается раз в 500 мс без `hyprctl`. |
| niri | wlr; запасной прямой IPC-сокет для app/title | idle. Через wlr fullscreen доступен; **IPC `FocusedWindow` не даёт fullscreen**, исключение fullscreen из idle на этом fallback недоступно. [Протокол](https://raw.githubusercontent.com/niri-wm/niri/main/src/protocols/foreign_toplevel.rs). |
| Qtile Wayland | wlr, включая XWayland-окна | idle; [C backend](https://github.com/qtile/qtile/blob/master/libqtile/backend/wayland/qw/server.c), [idle docs](https://docs.qtile.org/en/latest/manual/idle.html). Старые пакеты проверять отдельно. |
| river-classic | wlr active/fullscreen | idle; [window state](https://codeberg.org/river/river-classic/src/branch/main/river/ForeignToplevelHandle.zig), [input](https://codeberg.org/river/river-classic/src/branch/main/river/InputManager.zig). |
| River ≥0.4 | wlr active/title/app_id; **fullscreen в проверенных 0.4.8/main не публикуется** | idle. Требуется upstream fix или API конкретного WM; [Window.zig](https://codeberg.org/river/river/src/tag/v0.4.8/river/Window.zig). Не приравнивать к river-classic. |
| COSMIC | ext-list + `zcosmic_toplevel_info_v1` ≥2 дают activated/fullscreen | idle при доступном global; [XML](https://raw.githubusercontent.com/pop-os/cosmic-protocols/main/unstable/cosmic-toplevel-info-unstable-v1.xml), [реализация](https://raw.githubusercontent.com/pop-os/cosmic-comp/master/src/wayland/protocols/toplevel_info.rs). Sandbox может скрывать globals. |
| Deepin / Treeland current upstream | wlr | idle; [surface controller](https://raw.githubusercontent.com/linuxdeepin/treeland/master/src/core/surfaceprotocolcontroller.cpp), [idle](https://raw.githubusercontent.com/linuxdeepin/treeland/master/src/idle/idlemanager.cpp). Первая стабильная версия с этими API не установлена. |
| dwl без патчей | **Нет activated API**: ext-list недостаточен | idle доступен; нужен [foreign-toplevel patch](https://codeberg.org/dwl/dwl-patches/src/branch/main/patches/foreign-toplevel-management). [Vanilla source](https://codeberg.org/dwl/dwl/src/branch/main/dwl.c). |
| Cage | wlr active/app/title; fullscreen не подтверждён | idle; [cage.c](https://github.com/cage-kiosk/cage/blob/master/cage.c), [view.c](https://github.com/cage-kiosk/cage/blob/master/view.c). Kiosk-режим не доказывает fullscreen state. |
| Hikari, fork thomasadam | wlr active/app/title; fullscreen не подтверждён | idle notifier не найден; [server](https://codeberg.org/thomasadam/hikari/src/branch/main/src/server.c), [view](https://codeberg.org/thomasadam/hikari/src/branch/main/src/view.c). |
| Mir / Miracle WM / Miriway | Условно wlr: расширение включается shell/config | Поддерживаемый источник input idle не подтверждён; полной поддержки нет. [Mir API](https://canonical.com/mir/docs/latest/api/classmiral_1_1_wayland_extensions/). |
| Lomiri | Конкретные globals shell не подтверждены | Полный маршрут не заявлен; происхождения от Mir недостаточно. [Lomiri](https://ubports.com/lomiri). |
| Enlightenment Wayland, Weston | Подтверждённого полного маршрута нет | Требуется исследование API/плагина; [Enlightenment](https://www.enlightenment.org/start), [Weston](https://github.com/wayland-mirror/weston/blob/main/README.md). |
| Phosh / phoc 0.59.0 | wlr: title/app_id/activated/fullscreen подтверждены исходниками | ext idle. Привилегированные globals доступны нативному пакету, sandbox может их скрывать; [upstream release source](https://deb.debian.org/debian/pool/main/p/phoc/phoc_0.59.0.orig.tar.xz). |
| Gamescope standalone | Готового общего маршрута не подтверждено | В nested-режиме host compositor видит окно Gamescope; отдельная игра внутри не гарантируется. [Source](https://github.com/ValveSoftware/gamescope/blob/master/src/wlserver.cpp). |

## Оболочки поверх композиторов наследуют их возможности

| Окружение | Как читать матрицу |
|---|---|
| Budgie 10.10 | Wayland-only, labwc; см. строку labwc. [Официальный FAQ](https://buddiesofbudgie.org/about/faq). |
| LXQt Wayland | KWin, labwc, Wayfire, Hyprland, niri, River, Sway; выбирается API композитора. [LXQt wiki](https://lxqt-project.org/wiki/Wayland-Session.html). |
| Xfce 4.20 Wayland | Предварительная поддержка с labwc/Wayfire; собственный xfwl4 развивается, его globals здесь не проверены. [Roadmap](https://wiki.xfce.org/releng/wayland_roadmap). |
| MATE Wayland | Экспериментальная сессия с Wayfire; нужен его `foreign-toplevel`. [README](https://raw.githubusercontent.com/mate-desktop/mate-wayland-session/master/README.md). |
| Deepin с dde-kwin | Проверять доступный KWin API фактической версии; не переносить гарантию с Treeland. |
| Pantheon, Trinity, Liri, Maui Shell, UKUI, Cutefish, Lingmo, PaperDE и новые forks | X11 — общий backend; Wayland — фактический compositor/registry. Отдельной проверки каждого fork нет. |
| Dux Shell, Orbitiny, CHasm, Noctalia, DankMaterialShell, CoW, MATE/Polo | Найдены в инвентаре OpenNET; конкретные версии и globals отдельно не проверены. Применяется общий X11 или Wayland маршрут по фактической сессии, полная поддержка по имени не заявляется. |
| Kera Desktop | Демонстрационная web shell; host/browser виден как одно приложение, внутренние web apps отдельно не гарантируются. [Kera README](https://gitlab.com/kerahq/Kera-Desktop). |

## Простой, fullscreen и проверка сеанса

При отсутствии ext-idle доступен резервный [KDE idle v1](https://github.com/KDE/plasma-wayland-protocols/blob/master/src/protocols/idle.xml), применяемый старым KWin и UKUI. Он не предоставляет input-only semantics.

ext-idle v2 позволяет считать именно ввод пользователя через
`get_input_idle_notification`, игнорируя idle inhibitors. На v1 применяется
`get_idle_notification`: блокировщики могут задерживать простой. Новый notification
отсчитывает время с момента создания, а не восстанавливает прежний last-input.
[Официальный XML](https://gitlab.freedesktop.org/wayland/wayland-protocols/-/blob/main/staging/ext-idle-notify/ext-idle-notify-v1.xml).

wlr-management и COSMIC подтверждают возможности протокола; исправность публикации
fullscreen зависит от композитора. River, Cage и Hikari показывают, почему нельзя
приравнивать наличие manager к проверенной работе всех состояний.
[Официальный wlr XML](https://gitlab.freedesktop.org/wlroots/wlr-protocols/-/blob/master/unstable/wlr-foreign-toplevel-management-unstable-v1.xml).

Для проверки конкретного сеанса нужны переключение двух приложений, изменение title,
простой до порога и возобновление ввода, fullscreen активного окна, переход в другое
окно/рабочее пространство, закрытие окна и блокировка. XWayland и native Wayland
окна проверяются отдельно. Автотесты с поддельными событиями подтверждают обработку
API, но не заменяют такой запуск в целевом окружении.

Трей зависит от `StatusNotifierWatcher`; его отсутствие не означает отсутствие
трекинга. Работоспособность трея и пакетных библиотек проверяется отдельно от window/idle API.

Для диагностики выбора API: `TIMETRACE_DEBUG=1 timetrace`. Журнал не содержит
заголовков пользовательских окон; недоступные window/idle API показаны в строке состояния.

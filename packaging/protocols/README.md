# Foreign-toplevel bindings

The XML files retain their upstream copyright/license notices. Generated Python
files live in `src/timetrace/_wayland_protocols/` beside the existing core bindings.
Generate with the same pywayland version used to build the application:

```sh
python -m pywayland.scanner -i packaging/protocols/*.xml /usr/share/wayland/wayland.xml -o /tmp/timetrace-protocols
cp /tmp/timetrace-protocols/idle.py src/timetrace/_wayland_protocols/kde_idle.py
cp /tmp/timetrace-protocols/{wlr_foreign_toplevel_management_unstable_v1,cosmic_toplevel_info_unstable_v1,cosmic_workspace_unstable_v1,ext_foreign_toplevel_list_v1,ext_workspace_v1}.py src/timetrace/_wayland_protocols/
```

Sources (retrieved 2026-11-15):

- [wlr-protocols](https://github.com/swaywm/wlr-protocols/blob/master/unstable/wlr-foreign-toplevel-management-unstable-v1.xml)
- [COSMIC toplevel info](https://github.com/pop-os/cosmic-protocols/blob/main/unstable/cosmic-toplevel-info-unstable-v1.xml)
- [COSMIC workspace](https://github.com/pop-os/cosmic-protocols/blob/main/unstable/cosmic-workspace-unstable-v1.xml)
- [ext foreign toplevel list](https://gitlab.freedesktop.org/wayland/wayland-protocols/-/blob/main/staging/ext-foreign-toplevel-list/ext-foreign-toplevel-list-v1.xml)
- [ext workspace](https://gitlab.freedesktop.org/wayland/wayland-protocols/-/blob/main/staging/ext-workspace/ext-workspace-v1.xml)

Workspace definitions are generated dependencies of COSMIC metadata. TimeTrace
does not bind workspace managers or request any window-management action.

KDE idle XML: [upstream](https://github.com/KDE/plasma-wayland-protocols/blob/master/src/protocols/idle.xml), LGPL-2.1-or-later. Used only if ext-idle-notify is absent; TimeTrace never calls simulate_user_activity.

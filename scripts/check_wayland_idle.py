"""Manual verification: run on a KDE Wayland session, do not touch input for
>3s, confirm 'idled' prints, then move the mouse and confirm 'resumed' prints.
Exit with Ctrl+C."""
from pywayland.client import Display

from timetrace._wayland_protocols.ext_idle_notify_v1 import ExtIdleNotifierV1

TIMEOUT_MS = 3000


def main() -> None:
    display = Display()
    display.connect()
    registry = display.get_registry()

    state: dict[str, object] = {}

    def handle_global(registry, id_, interface, version):
        if interface == "ext_idle_notifier_v1":
            state["notifier"] = registry.bind(id_, ExtIdleNotifierV1, version)
        elif interface == "wl_seat":
            from pywayland.protocol.wayland import WlSeat

            state["seat"] = registry.bind(id_, WlSeat, version)

    registry.dispatcher["global"] = handle_global
    display.roundtrip()

    notifier = state.get("notifier")
    seat = state.get("seat")
    if notifier is None or seat is None:
        raise SystemExit("ext_idle_notifier_v1 or wl_seat not available on this compositor")

    notification = notifier.get_idle_notification(TIMEOUT_MS, seat)

    def on_idled():
        print("idled")

    def on_resumed():
        print("resumed")

    notification.dispatcher["idled"] = lambda n: on_idled()
    notification.dispatcher["resumed"] = lambda n: on_resumed()

    print(f"watching idle with {TIMEOUT_MS}ms timeout, Ctrl+C to stop")
    while True:
        display.dispatch(block=True)


if __name__ == "__main__":
    main()

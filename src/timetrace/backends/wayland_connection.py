"""Bounded Wayland roundtrips for capability discovery and reconnect."""
import select
import time


def roundtrip(display, timeout=1.0):
    done = False
    def completed(callback, serial):
        nonlocal done
        done = True
    callback = display.sync()
    callback.dispatcher["done"] = completed
    deadline = time.monotonic() + timeout
    try:
        while not done:
            display.dispatch(block=False)
            if done:
                break
            display.flush()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Wayland compositor did not respond")
            readable, _, _ = select.select([display.get_fd()], [], [], remaining)
            if readable:
                display.dispatch(block=True)
    finally:
        callback.destroy()

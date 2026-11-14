// KDE 6 calls the focused client activeWindow; KDE 5 used activeClient.
function activeWindow() {
    return workspace.activeWindow !== undefined ? workspace.activeWindow : workspace.activeClient;
}

function report() {
    var client = activeWindow();
    // Shell surfaces can cover a screen without representing a fullscreen app.
    var fullscreen = !!(client && client.fullScreen && !client.minimized &&
        !client.desktopWindow && !client.dock && !client.notification && !client.tooltip);
    callDBus(
        "org.timetrace.App", "/ActiveWindow", "org.timetrace.ActiveWindow",
        "ReportWindowState",
        client ? (client.resourceClass || "unknown") : "",
        client ? (client.caption || "") : "",
        client ? (client.pid || 0) : 0,
        fullscreen
    );
}

// Subscribe only to the focused window; background animations and notifications
// are not input and must not reset the idle timer.
var watched = null;
function watchActiveWindow() {
    if (watched) {
        try { watched.fullScreenChanged.disconnect(report); } catch (e) {}
    }
    watched = activeWindow();
    if (watched) {
        watched.fullScreenChanged.connect(report);
    }
    report();
}
workspace.windowActivated.connect(watchActiveWindow);
watchActiveWindow();

function report(client) {
    if (!client) {
        return;
    }
    callDBus(
        "org.timetrace.App",
        "/ActiveWindow",
        "org.timetrace.ActiveWindow",
        "ReportActiveWindow",
        client.resourceClass || "unknown",
        client.caption || "",
        client.pid || 0
    );
}

workspace.windowActivated.connect(report);
report(workspace.activeClient);

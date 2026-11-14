// Run with node or gjs. Execute the bundled script against focused-window events.
const source = typeof require === 'function' ? require('fs').readFileSync(process.argv[2], 'utf8') : null;
function signal() {
    const slots = new Set();
    return {connect(fn) {slots.add(fn);}, disconnect(fn) {slots.delete(fn);},
        emit() {for (const fn of slots) fn();}};
}
function checkScript(text) {
    const reports = [];
    const first = {resourceClass: 'firefox', caption: 'YouTube', pid: 1,
        fullScreen: false, fullScreenChanged: signal()};
    const workspace = {activeWindow: first, windowActivated: signal()};
    new Function('workspace', 'callDBus', text)(workspace, (...args) => reports.push(args));
    function check(value, why) {if (!value) throw Error(why);}
    check(reports.at(-1).at(-1) === false, 'Initial normal window');
    first.fullScreen = true;
    first.fullScreenChanged.emit();
    check(reports.at(-1).at(-1) === true, 'Fullscreen without activation');
    workspace.activeWindow = {resourceClass: 'plasmashell', fullScreen: true,
        desktopWindow: true, fullScreenChanged: signal()};
    workspace.windowActivated.emit();
    check(reports.at(-1).at(-1) === false, 'Wallpaper cannot inhibit idle');
    const count = reports.length;
    first.fullScreenChanged.emit();
    check(reports.length === count, 'Background changes are disconnected');
    workspace.activeWindow = null;
    workspace.windowActivated.emit();
    check(reports.at(-1).at(-1) === false && reports.at(-1)[4] === '', 'Clear focus');
    check(reports.every(r => r[3] === 'ReportWindowState'), 'New D-Bus route');
}
if (source) {
    checkScript(source);
    console.log('PASS: KWin fullscreen, focus loss, wallpaper and background changes');
} else {
    // GJS classic supports imports.gi; run without -m.
    const [ok, bytes] = imports.gi.GLib.file_get_contents(ARGV[0]);
    if (!ok) throw Error('Cannot read script');
    checkScript(new TextDecoder().decode(bytes));
    print('PASS: KWin fullscreen, focus loss, wallpaper and background changes');
}

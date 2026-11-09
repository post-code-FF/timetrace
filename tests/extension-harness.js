// Run under the installed GJS engine. Shell API fakes exercise lifecycle and
// protocol only; this is deliberately not labelled a real Shell integration.
import GLib from 'gi://GLib';
const [ok, bytes] = GLib.file_get_contents(ARGV[0]);
if (!ok) throw Error('Cannot read extension');
const text = new TextDecoder().decode(bytes).replace(/^import .*;\n/gm, '').replace('export default class', 'class');
let seqId = 0;
let removed = 0;
function emitter(extra = {}) {
    return Object.assign({connect() { return ++seqId; }, disconnect() { removed++; }}, extra);
}
let idle = 0;
const monitor = {get_idletime() {return idle;}};
const display = emitter({focus_window: null});
const mode = emitter({isLocked: false, isGreeter: false});
const state = {display, workspace_manager: emitter(), backend: {get_core_idle_monitor() {return monitor;}}};
const dbus = {export() {}, emit_signal() {}, unexport() {this.unexported = true;}};
const shell = {WindowTracker: {get_default() {return {get_window_app(win) {return win.app;}};}}};
const glib = {uuid_string_random() {return 'test';}, get_real_time() {return 1000000;},
    get_monotonic_time() {return 500000;}, timeout_add() {return 1;}, source_remove() {},
    PRIORITY_DEFAULT: 0, SOURCE_CONTINUE: true};
const factory = new Function('GLib', 'Gio', 'Shell', 'Main', 'Extension', 'global', text + '\nreturn TimeTraceBridge;');
const Bridge = factory(glib, {DBusExportedObject: {wrapJSObject() {return dbus;}}, DBus: {session: {}}},
    shell, {sessionMode: mode}, class {}, state);
const bridge = new Bridge();
function assert(value, why) { if (!value) throw Error(why); }
bridge.enable();
function current() {return JSON.parse(bridge.GetEvents('')).events[0];}
assert(current().app_id === '', 'Initial empty focus must be represented');
display.focus_window = {app: {get_id() {return 'firefox.desktop';}}, get_title() {return 'Firefox';}};
bridge._sample();
assert(current().app_id === 'firefox.desktop', 'Desktop ID');
mode.isLocked = true;
bridge._sample();
assert(current().locked && current().app_id === '' && current().title === '', 'No title leak when locked');
mode.isLocked = false;
idle = 7000;
bridge._sample();
assert(current().idle_ms === 7000, 'Mutter idle');
assert(JSON.parse(bridge.GetEvents('test:1')).events.length === 3, 'Replay');
for (let i = 0; i < 610; i++) bridge._sample();
assert(JSON.parse(bridge.GetEvents('test:1')).overflow, 'Bounded history overflow');
bridge.disable();
assert(dbus.unexported && removed === 3 && bridge._events.length === 0, 'Full cleanup');
print('PASS: GJS protocol, focus, lock privacy, idle, replay, overflow, disable');

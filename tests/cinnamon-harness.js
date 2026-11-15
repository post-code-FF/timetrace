// Exercise the exact read-only snapshot code with Cinnamon/Muffin-shaped APIs.
const snapshot = new Function('global', 'imports', `return ${ARGV[0]};`);
const win = {get_wm_class: () => 'Editor', get_title: () => 'Привет, мир', is_fullscreen: () => true};
const main = {screensaverController: {locked: false}};
const globalMock = {
    display: {get_focus_window: () => win},
    settings: {get_boolean: key => {
        if (key !== 'session-locked-state') throw Error('unexpected setting read');
        return true;
    }},
};
const importsMock = {
    gi: {
        Meta: {IdleMonitor: {get_core: () => ({get_idletime: () => 1234})}},
        Cinnamon: {WindowTracker: {get_default: () => ({get_window_app: () => ({get_id: () => 'editor.desktop'})})}},
    },
    ui: {main},
};
function assert(value, message) { if (!value) throw Error(message); }
let result = snapshot(globalMock, importsMock);
assert(result.app_id === 'editor.desktop' && result.idle_ms === 1234, 'app and idle API');
assert(result.title === 'Привет, мир' && result.fullscreen && !result.locked, 'window snapshot');
delete main.screensaverController;
result = snapshot(globalMock, importsMock);
assert(result.locked, 'legacy session lock API');
globalMock.display.get_focus_window = () => null;
result = snapshot(globalMock, importsMock);
assert(result.app_id === '' && result.title === '' && !result.fullscreen, 'focus loss');
print('PASS: Cinnamon snapshot app, title, fullscreen, idle, old/new lock API and focus loss');

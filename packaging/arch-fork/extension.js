import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const XML = `<node><interface name="org.timetrace.GnomeFork.Bridge1">
<method name="GetEvents"><arg type="s" direction="in" name="cursor"/>
<arg type="s" direction="out" name="events"/></method>
<signal name="Changed"/>
</interface></node>`;
const LIMIT = 600;

// Read-only Shell APIs. No Eval, XWayland scraping, private window protocols,
// key capture, or persistent log of titles inside Shell.
export default class TimeTraceBridge extends Extension {
    enable() {
        this._signals = [];
        this._events = [];
        this._epoch = GLib.uuid_string_random();
        this._seq = 0;
        try {
            this._tracker = Shell.WindowTracker.get_default();
            this._idleMonitor = global.backend.get_core_idle_monitor();
            this._dbus = Gio.DBusExportedObject.wrapJSObject(XML, this);
            this._dbus.export(Gio.DBus.session, '/org/timetrace/GnomeFork/Bridge');
            this._connect(global.display, 'notify::focus-window', () => this._sample());
            this._connect(Main.sessionMode, 'updated', () => this._sample());
            this._connect(global.workspace_manager, 'active-workspace-changed', () => this._sample());
            this._timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => {
                try {
                    this._sample();
                } catch (error) {
                    // Keep the timer alive; the client pauses on missing heartbeat.
                    console.error(`TimeTrace bridge sample failed: ${error.message}`);
                }
                return GLib.SOURCE_CONTINUE;
            });
            this._sample();
        } catch (error) {
            this.disable();
            throw error;
        }
    }

    _connect(object, signal, callback) {
        this._signals.push([object, object.connect(signal, callback)]);
    }

    _sample(available = true) {
        const locked = Main.sessionMode.isLocked || Main.sessionMode.isGreeter;
        const win = locked ? null : global.display.focus_window;
        // WindowTracker follows transients and maps both native Wayland and
        // XWayland windows to desktop IDs. WM_CLASS is a labelled fallback.
        const app = win ? this._tracker.get_window_app(win) : null;
        const appId = app?.get_id() || (win?.get_wm_class() ? `wmclass:${win.get_wm_class()}` : '');
        const event = {
            version: 1, epoch: this._epoch, seq: ++this._seq,
            ts: Math.floor(GLib.get_real_time() / 1000),
            mono: Math.floor(GLib.get_monotonic_time() / 1000),
            available, locked: Boolean(locked), idle_ms: this._idleMonitor.get_idletime(),
            app_id: available ? appId.slice(0, 1024) : '', title: (win?.get_title() || '').slice(0, 4096),
        };
        this._events.push(event);
        if (this._events.length > LIMIT)
            this._events.shift();
        this._dbus.emit_signal('Changed', null);
    }

    GetEvents(cursor) {
        const [epoch, number] = cursor.split(':');
        const seq = Number(number) || 0;
        const same = epoch === this._epoch;
        // A new client starts from current state, never backfills time before
        // its own start. A connected client can recover missed notifications.
        const events = same ? this._events.filter(e => e.seq > seq) : this._events.slice(-1);
        const overflow = same && seq < this._events[0].seq - 1;
        return JSON.stringify({events, overflow});
    }

    disable() {
        if (this._timer)
            GLib.source_remove(this._timer);
        this._timer = null;
        for (const [object, id] of this._signals ?? []) {
            try {
                object.disconnect(id);
            } catch (error) {
                console.error(`TimeTrace bridge disconnect failed: ${error.message}`);
            }
        }
        this._signals = [];
        if (this._dbus) {
            try {
                this._sample(false);
            } catch (error) {
                console.error(`TimeTrace bridge final sample failed: ${error.message}`);
            } finally {
                this._dbus.unexport();
            }
        }
        this._dbus = null;
        this._events = [];
        this._tracker = null;
        this._idleMonitor = null;
    }
}

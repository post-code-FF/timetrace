import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import Shell from 'gi://Shell';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const IFACE_XML = `
<node>
  <interface name="org.timetrace.ActiveWindow">
    <method name="GetActiveWindow">
      <arg type="s" direction="out" name="resourceClass"/>
      <arg type="s" direction="out" name="title"/>
    </method>
    <signal name="ActiveWindowChanged">
      <arg type="s" name="resourceClass"/>
      <arg type="s" name="title"/>
    </signal>
  </interface>
</node>`;

export default class TimeTraceExtension extends Extension {
    enable() {
        this._dbusImpl = Gio.DBusExportedObject.wrapJSObject(IFACE_XML, this);
        this._dbusImpl.export(Gio.DBus.session, '/org/timetrace/ActiveWindow');
        this._tracker = Shell.WindowTracker.get_default();
        this._signalId = global.display.connect('notify::focus-window', () => this._report());
        this._report();
    }

    disable() {
        if (this._signalId) {
            global.display.disconnect(this._signalId);
            this._signalId = null;
        }
        if (this._dbusImpl) {
            this._dbusImpl.unexport();
            this._dbusImpl = null;
        }
    }

    _report() {
        const win = global.display.focus_window;
        if (!win) return;
        const app = this._tracker.get_window_app(win);
        const resourceClass = app ? app.get_id() : (win.get_wm_class() || 'unknown');
        const title = win.get_title() || '';
        this._dbusImpl.emit_signal('ActiveWindowChanged', new GLib.Variant('(ss)', [resourceClass, title]));
    }

    GetActiveWindow() {
        const win = global.display.focus_window;
        if (!win) return ['', ''];
        const app = this._tracker.get_window_app(win);
        const resourceClass = app ? app.get_id() : (win.get_wm_class() || 'unknown');
        return [resourceClass, win.get_title() || ''];
    }
}

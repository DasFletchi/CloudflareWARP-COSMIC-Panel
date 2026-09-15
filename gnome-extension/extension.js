import GObject from 'gi://GObject';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Clutter from 'gi://Clutter';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';

const INSTALL_COMMAND = 'curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg && echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list >/dev/null && sudo apt-get update && sudo apt-get install -y cloudflare-warp';

/**
 * Executes a command asynchronously without blocking the GNOME Shell thread.
 */
function runCommandAsync(argv) {
    return new Promise((resolve) => {
        try {
            let proc = new Gio.Subprocess({
                argv: argv,
                flags: Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE,
            });
            proc.init(null);
            proc.communicate_utf8_async(null, null, (proc, res) => {
                try {
                    let [, stdout, stderr] = proc.communicate_utf8_finish(res);
                    let success = proc.get_successful();
                    resolve({
                        ok: success,
                        output: (stdout || stderr || '').trim(),
                        status: proc.get_exit_status(),
                    });
                } catch (e) {
                    resolve({ ok: false, output: `${e}`, status: 1 });
                }
            });
        } catch (error) {
            resolve({ ok: false, output: `${error}`, status: 1 });
        }
    });
}

function getTerminalCommand(cmdString) {
    let terms = ['cosmic-term', 'gnome-terminal', 'ptyxis', 'x-terminal-emulator'];
    for (let term of terms) {
        if (GLib.find_program_in_path(term)) {
            if (term === 'gnome-terminal') {
                return ['gnome-terminal', '--', 'bash', '-lc', `${cmdString}; echo; read -n 1 -s -r -p 'Press any key to close...'`];
            }
            return [term, '-e', 'bash', '-lc', `${cmdString}; echo; read -n 1 -s -r -p 'Press any key to close...'`];
        }
    }
    return ['x-terminal-emulator', '-e', 'bash', '-lc', `${cmdString}; read -n 1`];
}

const WarpPanelButton = GObject.registerClass(
class WarpPanelButton extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'Cloudflare WARP');

        this._expanded = false;
        this._updatingToggle = false;
        this._advancedItems = [];

        // Top bar label
        this.label = new St.Label({
            text: 'WARP',
            y_expand: true,
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'warp-panel-label',
        });
        this.add_child(this.label);

        // Menu items
        this._statusItem = new PopupMenu.PopupMenuItem('Status: checking...', {
            reactive: false,
            can_focus: false,
        });
        this.menu.addMenuItem(this._statusItem);

        this._toggleItem = new PopupMenu.PopupSwitchMenuItem('On / Off', false);
        this._toggleSignalId = this._toggleItem.connect('toggled', (_item, state) => {
            if (this._updatingToggle)
                return;

            this._checkInstalled().then(installed => {
                if (!installed) {
                    this._withToggleUpdate(() => this._toggleItem.setToggleState(false));
                    this._notify('Cloudflare WARP', 'warp-cli not found. Open Settings for one-click install.');
                    return;
                }
                this._runWarpCommand(state ? ['connect', '--accept-tos'] : ['disconnect']);
            });
        });
        this.menu.addMenuItem(this._toggleItem);

        this._settingsItem = new PopupMenu.PopupMenuItem('Settings & Modes');
        this._settingsSignalId = this._settingsItem.connect('activate', () => {
            this._expanded = !this._expanded;
            this._buildAdvancedSection();
        });
        this.menu.addMenuItem(this._settingsItem);

        this._refreshStatus();
        this._refreshTimeoutId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 4, () => {
            this._refreshStatus();
            return GLib.SOURCE_CONTINUE;
        });
    }

    async _checkInstalled() {
        return GLib.find_program_in_path('warp-cli') !== null;
    }

    async _buildAdvancedSection() {
        this._advancedItems.forEach(item => item.destroy());
        this._advancedItems = [];

        if (!this._expanded)
            return;

        let separator = new PopupMenu.PopupSeparatorMenuItem();
        this.menu.addMenuItem(separator);
        this._advancedItems.push(separator);

        let isInstalled = await this._checkInstalled();
        if (!isInstalled) {
            let installItem = new PopupMenu.PopupMenuItem('Install Cloudflare WARP (One-Click)');
            installItem.connect('activate', () => {
                let termCmd = getTerminalCommand(INSTALL_COMMAND);
                Gio.Subprocess.new(termCmd, Gio.SubprocessFlags.NONE);
            });
            this.menu.addMenuItem(installItem);
            this._advancedItems.push(installItem);

            let copyItem = new PopupMenu.PopupMenuItem('Copy Install Command');
            copyItem.connect('activate', () => {
                St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, INSTALL_COMMAND);
                this._notify('Cloudflare WARP', 'Install command copied to clipboard.');
            });
            this.menu.addMenuItem(copyItem);
            this._advancedItems.push(copyItem);
            return;
        }

        // Mode switch buttons
        let modes = [
            ['warp', 'Set Mode: WARP (Full)'],
            ['warp+doh', 'Set Mode: WARP + DoH'],
            ['doh', 'Set Mode: 1.1.1.1 (DoH Only)'],
            ['proxy', 'Set Mode: Proxy (SOCKS5)'],
        ];

        for (let [mode, label] of modes) {
            let item = new PopupMenu.PopupMenuItem(label);
            item.connect('activate', () => this._runWarpCommand(['mode', mode]));
            this.menu.addMenuItem(item);
            this._advancedItems.push(item);
        }

        let sep2 = new PopupMenu.PopupSeparatorMenuItem();
        this.menu.addMenuItem(sep2);
        this._advancedItems.push(sep2);

        let termSettingsItem = new PopupMenu.PopupMenuItem('Terminal: warp-cli settings');
        termSettingsItem.connect('activate', () => {
            let termCmd = getTerminalCommand('warp-cli settings');
            Gio.Subprocess.new(termCmd, Gio.SubprocessFlags.NONE);
        });
        this.menu.addMenuItem(termSettingsItem);
        this._advancedItems.push(termSettingsItem);

        let logsItem = new PopupMenu.PopupMenuItem('Terminal: View warp-svc logs');
        logsItem.connect('activate', () => {
            let termCmd = getTerminalCommand('journalctl -u warp-svc -f');
            Gio.Subprocess.new(termCmd, Gio.SubprocessFlags.NONE);
        });
        this.menu.addMenuItem(logsItem);
        this._advancedItems.push(logsItem);
    }

    _withToggleUpdate(action) {
        this._updatingToggle = true;
        try {
            action();
        } finally {
            this._updatingToggle = false;
        }
    }

    async _refreshStatus() {
        let isInstalled = await this._checkInstalled();
        if (!isInstalled) {
            this._statusItem.label.text = 'Status: warp-cli not installed';
            this._withToggleUpdate(() => this._toggleItem.setToggleState(false));
            this._settingsItem.label.text = 'Settings (install available)';
            this.label.text = 'WARP (off)';
            return;
        }

        this._settingsItem.label.text = this._expanded ? 'Settings (hide)' : 'Settings & Modes';

        let res = await runCommandAsync(['warp-cli', '--json', 'status']);
        let connected = false;
        let statusText = 'Unknown';

        if (res.ok) {
            try {
                let data = JSON.parse(res.output);
                statusText = data.status || 'Unknown';
                connected = statusText.toLowerCase() === 'connected';
            } catch (e) {
                connected = res.output.toLowerCase().includes('connected');
                statusText = connected ? 'Connected' : 'Disconnected';
            }
        } else {
            let resPlain = await runCommandAsync(['warp-cli', 'status']);
            if (resPlain.ok) {
                statusText = resPlain.output.split('\n')[0] || 'Unknown';
                connected = resPlain.output.toLowerCase().includes('connected');
            } else {
                statusText = 'Daemon Inactive';
            }
        }

        this._statusItem.label.text = `Status: ${statusText}`;
        this._withToggleUpdate(() => this._toggleItem.setToggleState(connected));
        this.label.text = connected ? '● WARP' : '○ WARP';
    }

    async _runWarpCommand(args) {
        let res = await runCommandAsync(['warp-cli', ...args]);
        if (res.ok) {
            this._notify('Cloudflare WARP', res.output || `warp-cli ${args.join(' ')} executed.`);
        } else {
            this._notify('Cloudflare WARP', `Error: ${res.output || 'Command failed.'}`);
        }
        this._refreshStatus();
    }

    _notify(title, message) {
        Main.notify(title, message);
    }

    destroy() {
        if (this._toggleSignalId) {
            this._toggleItem.disconnect(this._toggleSignalId);
            this._toggleSignalId = 0;
        }

        if (this._settingsSignalId) {
            this._settingsItem.disconnect(this._settingsSignalId);
            this._settingsSignalId = 0;
        }

        if (this._refreshTimeoutId) {
            GLib.source_remove(this._refreshTimeoutId);
            this._refreshTimeoutId = 0;
        }

        super.destroy();
    }
});

export default class WarpCosmicExtension extends Extension {
    enable() {
        this._indicator = new WarpPanelButton();
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }

    disable() {
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
    }
}

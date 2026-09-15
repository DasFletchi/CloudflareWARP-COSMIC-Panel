const { GObject, GLib, St, Clutter } = imports.gi;
const Main = imports.ui.main;
const PanelMenu = imports.ui.panelMenu;
const PopupMenu = imports.ui.popupMenu;
const ByteArray = imports.byteArray;
const Util = imports.misc.util;

const INSTALL_COMMAND = 'curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg && echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list >/dev/null && sudo apt-get update && sudo apt-get install -y cloudflare-warp';
const ADVANCED_COMMANDS = [
    'status',
    'settings',
    'stats',
    'mode',
    'dns',
    'proxy',
    'target',
    'trusted',
    'tunnel',
    'vnet',
    'registration',
    'environment',
    'override',
    'mdm',
    'connector',
    'certs',
    'debug',
    'help',
    'generate-completions'
];

function runShell(command) {
    try {
        let [ok, stdout, stderr, exitStatus] = GLib.spawn_command_line_sync(`bash -lc ${GLib.shell_quote(command)}`);
        let output = ByteArray.toString(stdout || stderr || new Uint8Array());
        return {
            ok: ok && exitStatus === 0,
            output: output.trim(),
            exitStatus,
        };
    } catch (error) {
        return {
            ok: false,
            output: `${error}`,
            exitStatus: 1,
        };
    }
}

const WarpPanelButton = GObject.registerClass(
class WarpPanelButton extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'Cloudflare WARP');

        this._expanded = false;
        this._updatingToggle = false;

        this.add_child(new St.Label({
            text: 'WARP',
            y_expand: true,
            y_align: Clutter.ActorAlign.CENTER,
        }));

        this._statusItem = new PopupMenu.PopupMenuItem('Status: checking...', {
            reactive: false,
            can_focus: false,
        });
        this.menu.addMenuItem(this._statusItem);

        this._toggleItem = new PopupMenu.PopupSwitchMenuItem('On / Off', false);
        this._toggleSignalId = this._toggleItem.connect('toggled', (_item, state) => {
            if (this._updatingToggle)
                return;

            if (!this._isWarpInstalled()) {
                this._withToggleUpdate(() => this._toggleItem.setToggleState(false));
                this._notifyMissingWarp();
                return;
            }

            this._runWarpCommand(state ? 'connect --accept-tos' : 'disconnect');
            this._refreshStatus();
        });
        this.menu.addMenuItem(this._toggleItem);

        this._settingsItem = new PopupMenu.PopupMenuItem('Settings');
        this._settingsSignalId = this._settingsItem.connect('activate', () => {
            this._expanded = !this._expanded;
            this._buildAdvancedSection();
        });
        this.menu.addMenuItem(this._settingsItem);

        this._advancedItems = [];

        this._refreshStatus();
        this._refreshTimeoutId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 5, () => {
            this._refreshStatus();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _buildAdvancedSection() {
        this._advancedItems.forEach(item => item.destroy());
        this._advancedItems = [];

        if (!this._expanded)
            return;

        let separator = new PopupMenu.PopupSeparatorMenuItem();
        this.menu.addMenuItem(separator);
        this._advancedItems.push(separator);

        if (!this._isWarpInstalled()) {
            let installItem = new PopupMenu.PopupMenuItem('Install Cloudflare WARP (one-click)');
            installItem.connect('activate', () => this._runInstallCommand());
            this.menu.addMenuItem(installItem);
            this._advancedItems.push(installItem);

            let copyItem = new PopupMenu.PopupMenuItem('Copy install command');
            copyItem.connect('activate', () => {
                St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, INSTALL_COMMAND);
                Main.notify('Cloudflare WARP', 'Install command copied to clipboard.');
            });
            this.menu.addMenuItem(copyItem);
            this._advancedItems.push(copyItem);
            return;
        }

        ADVANCED_COMMANDS.forEach(command => {
            let menuItem = new PopupMenu.PopupMenuItem(`warp-cli ${command}`);
            menuItem.connect('activate', () => this._runWarpCommand(command));
            this.menu.addMenuItem(menuItem);
            this._advancedItems.push(menuItem);
        });

        let connectItem = new PopupMenu.PopupMenuItem('warp-cli connect');
        connectItem.connect('activate', () => this._runWarpCommand('connect --accept-tos'));
        this.menu.addMenuItem(connectItem);
        this._advancedItems.push(connectItem);

        let disconnectItem = new PopupMenu.PopupMenuItem('warp-cli disconnect');
        disconnectItem.connect('activate', () => this._runWarpCommand('disconnect'));
        this.menu.addMenuItem(disconnectItem);
        this._advancedItems.push(disconnectItem);
    }

    _notifyMissingWarp() {
        Main.notify('Cloudflare WARP', `warp-cli was not found. Open Settings for one-click install.\n\n${INSTALL_COMMAND}`);
    }

    _runInstallCommand() {
        Util.spawn(['gnome-terminal', '--', 'bash', '-lc', `${INSTALL_COMMAND}; echo; read -n 1 -s -r -p "Press any key to close..."`]);
        Main.notify('Cloudflare WARP', 'Install command launched in terminal.');
    }

    _isWarpInstalled() {
        return runShell('command -v warp-cli').ok;
    }

    _withToggleUpdate(action) {
        this._updatingToggle = true;
        try {
            action();
        } finally {
            this._updatingToggle = false;
        }
    }

    _refreshStatus() {
        if (!this._isWarpInstalled()) {
            this._statusItem.label.text = 'Status: warp-cli not installed';
            this._withToggleUpdate(() => this._toggleItem.setToggleState(false));
            this._settingsItem.label.text = 'Settings (install available)';
            return;
        }

        this._settingsItem.label.text = this._expanded ? 'Settings (hide)' : 'Settings';

        let result = runShell('warp-cli status');
        if (!result.ok) {
            this._statusItem.label.text = 'Status: unavailable';
            return;
        }

        let statusText = result.output.split('\n')[0] || 'unknown';
        this._statusItem.label.text = `Status: ${statusText}`;

        let lowerOutput = result.output.toLowerCase();
        let connected = lowerOutput.includes('connected') && !lowerOutput.includes('disconnected');
        this._withToggleUpdate(() => this._toggleItem.setToggleState(connected));
    }

    _runWarpCommand(command) {
        let result = runShell(`warp-cli ${command}`);
        if (result.ok) {
            Main.notify('Cloudflare WARP', result.output || `warp-cli ${command} executed.`);
        } else {
            Main.notifyError('Cloudflare WARP', result.output || `warp-cli ${command} failed.`);
        }
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

let warpIndicator;

function init() {}

function enable() {
    warpIndicator = new WarpPanelButton();
    Main.panel.addToStatusArea('warp-cosmic-panel', warpIndicator);
}

function disable() {
    if (warpIndicator) {
        warpIndicator.destroy();
        warpIndicator = null;
    }
}

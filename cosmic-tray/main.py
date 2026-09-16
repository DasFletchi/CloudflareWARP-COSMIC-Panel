#!/usr/bin/env python3
"""
Cloudflare WARP Tray Applet for Pop!_OS COSMIC Desktop & Linux Panels.
Provides a native StatusNotifierItem (SNI) tray icon with real-time status,
mode switching, IP copying, and non-blocking execution.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from PyQt5.QtCore import QObject, QRunnable, QSize, Qt, QThread, QThreadPool, QTimer, pyqtSignal
from PyQt5.QtGui import QClipboard, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QApplication,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

# Relative import support
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
from warp_client import WarpClient

ASSETS_DIR = BASE_DIR / "assets"
AUTOSTART_FILE = Path.home() / ".config" / "autostart" / "com.dasfletchi.warp-cosmic.desktop"


class WorkerSignals(QObject):
    """Signals for background status polling and commands."""
    status_ready = pyqtSignal(dict)
    command_finished = pyqtSignal(bool, str)


class StatusWorker(QRunnable):
    """Runs status check in background thread to guarantee buttery-smooth UI."""

    def __init__(self, client: WarpClient):
        super().__init__()
        self.client = client
        self.signals = WorkerSignals()

    def run(self):
        info = self.client.get_status_info()
        self.signals.status_ready.emit(info)


class CommandWorker(QRunnable):
    """Runs a warp-cli command asynchronously in the background."""

    def __init__(self, task_func):
        super().__init__()
        self.task_func = task_func
        self.signals = WorkerSignals()

    def run(self):
        try:
            ok, msg = self.task_func()
            self.signals.command_finished.emit(ok, msg)
        except Exception as exc:
            self.signals.command_finished.emit(False, str(exc))


class WarpCosmicTray(QSystemTrayIcon):
    """Main System Tray Icon controller for Pop!_OS COSMIC."""

    def __init__(self, app: QApplication):
        super().__init__(app)
        self.app = app
        self.client = WarpClient()
        self.threadpool = QThreadPool.globalInstance()

        self._last_state: Optional[bool] = None
        self._current_info: Dict[str, Any] = {}
        self._is_transitioning = False

        # Load icons
        self.icons = {
            "connected": self._load_icon("warp-connected"),
            "disconnected": self._load_icon("warp-disconnected"),
            "connecting": self._load_icon("warp-connecting"),
            "error": self._load_icon("warp-error"),
        }

        # Initialize default icon
        self.setIcon(self.icons["disconnected"])

        # Setup context menu
        self._build_menu()

        # Connect tray click events
        self.activated.connect(self._on_tray_activated)

        # Setup status polling timer
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(4000)  # 4 seconds interval
        self.poll_timer.timeout.connect(self.refresh_status)
        self.poll_timer.timeout.connect(self._verify_tray_registered)
        self.poll_timer.start()

        # Initial refresh
        self.refresh_status()

    def _load_icon(self, name: str) -> QIcon:
        """Load SVG icon with fallback to PNG."""
        svg_path = ASSETS_DIR / f"{name}.svg"
        png_path = ASSETS_DIR / f"{name}.png"
        if svg_path.exists():
            return QIcon(str(svg_path))
        if png_path.exists():
            return QIcon(str(png_path))
        return QIcon()

    def _build_menu(self):
        """Construct the rich context menu for COSMIC Panel."""
        self.menu = QMenu()

        # Title / Brand Header
        self.title_action = self.menu.addAction("Cloudflare WARP")
        self.title_action.setEnabled(False)

        # Connection status badge
        self.status_action = self.menu.addAction("Status: checking...")
        self.status_action.setEnabled(False)

        self.menu.addSeparator()

        # Primary Toggle Action
        self.toggle_action = self.menu.addAction("Connect")
        self.toggle_action.triggered.connect(self._toggle_connection)

        self.menu.addSeparator()

        # Operation Mode Submenu
        self.mode_menu = self.menu.addMenu("🌐 Mode")
        self.mode_group = QActionGroup(self.mode_menu)
        self.mode_group.setExclusive(True)

        self.modes = [
            ("warp", "WARP (Full Tunnel)"),
            ("warp+doh", "WARP with DoH"),
            ("doh", "1.1.1.1 (DoH Only)"),
            ("proxy", "Proxy Mode (SOCKS5)"),
        ]
        self.mode_actions: Dict[str, QAction] = {}
        for mode_key, mode_label in self.modes:
            action = QAction(mode_label, self.mode_menu)
            action.setCheckable(True)
            action.setData(mode_key)
            action.triggered.connect(lambda checked, m=mode_key: self._set_mode(m))
            self.mode_group.addAction(action)
            self.mode_menu.addAction(action)
            self.mode_actions[mode_key] = action

        # Tools & Diagnostics Submenu
        self.tools_menu = self.menu.addMenu("🛠️ Tools & Info")

        self.reconnect_action = self.tools_menu.addAction("🔄 Reconnect")
        self.reconnect_action.triggered.connect(self._reconnect)

        self.tools_menu.addSeparator()

        self.copy_ipv4_action = self.tools_menu.addAction("📋 Copy Virtual IPv4")
        self.copy_ipv4_action.triggered.connect(lambda: self._copy_ip("ipv4"))

        self.copy_ipv6_action = self.tools_menu.addAction("📋 Copy Virtual IPv6")
        self.copy_ipv6_action.triggered.connect(lambda: self._copy_ip("ipv6"))

        self.show_diag_action = self.tools_menu.addAction("🔍 Connection Details")
        self.show_diag_action.triggered.connect(self._show_details)

        # System & Settings Submenu
        self.system_menu = self.menu.addMenu("⚙️ Settings & System")

        self.open_settings_action = self.system_menu.addAction("💻 Open warp-cli Settings")
        self.open_settings_action.triggered.connect(self._open_settings_terminal)

        self.open_logs_action = self.system_menu.addAction("📄 View Daemon Logs")
        self.open_logs_action.triggered.connect(self._open_logs_terminal)

        self.restart_svc_action = self.system_menu.addAction("⚡ Restart warp-svc")
        self.restart_svc_action.triggered.connect(self._restart_daemon)

        self.autostart_action = self.system_menu.addAction("🚀 Start on Login")
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(AUTOSTART_FILE.exists())
        self.autostart_action.toggled.connect(self._toggle_autostart)

        self.menu.addSeparator()

        # Quit Action
        self.quit_action = self.menu.addAction("Quit Panel Applet")
        self.quit_action.triggered.connect(self._quit_applet)

        self.setContextMenu(self.menu)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        """Toggle connection on left click, open menu on right click / trigger."""
        if reason == QSystemTrayIcon.Trigger:
            # Single Left-Click toggles connection
            self._toggle_connection()

    def refresh_status(self):
        """Dispatches non-blocking status fetch to background thread."""
        worker = StatusWorker(self.client)
        worker.signals.status_ready.connect(self._on_status_updated)
        self.threadpool.start(worker)

    def _on_status_updated(self, info: Dict[str, Any]):
        """Update UI based on status results."""
        self._current_info = info

        if not info["installed"]:
            self.setIcon(self.icons["error"])
            self.setToolTip("Cloudflare WARP: Not Installed")
            self.status_action.setText("⚠️ warp-cli not installed")
            self.toggle_action.setText("Install Cloudflare WARP")
            self.toggle_action.setEnabled(True)
            self.mode_menu.setEnabled(False)
            self.tools_menu.setEnabled(False)
            return

        connected = info["connected"]
        status_text = info["status"]
        mode = info.get("mode", "warp")
        ipv4 = info.get("ipv4")

        # Update mode radio buttons
        for mode_key, action in self.mode_actions.items():
            action.setChecked(mode_key == mode)

        # Notify state transition if changed
        if self._last_state is not None and self._last_state != connected:
            if connected:
                self._send_notification(
                    "Cloudflare WARP Connected",
                    f"Status: {status_text}\nVirtual IP: {ipv4 or 'Assigned'}\nMode: {mode.upper()}"
                )
            else:
                self._send_notification(
                    "Cloudflare WARP Disconnected",
                    "Your internet traffic is no longer routing through WARP."
                )

        self._last_state = connected

        if self._is_transitioning:
            self.setIcon(self.icons["connecting"])
            self.status_action.setText(f"⏳ Status: {status_text}...")
            self.toggle_action.setEnabled(False)
        elif connected:
            self.setIcon(self.icons["connected"])
            status_desc = f"● Connected ({info.get('reason') or 'healthy'})"
            self.status_action.setText(status_desc)
            self.toggle_action.setText("🛑 Disconnect")
            self.toggle_action.setEnabled(True)
            tooltip = f"Cloudflare WARP: Connected\nMode: {mode.upper()}"
            if ipv4:
                tooltip += f"\nIP: {ipv4}"
            self.setToolTip(tooltip)
        else:
            self.setIcon(self.icons["disconnected"])
            self.status_action.setText(f"○ Status: {status_text}")
            self.toggle_action.setText("⚡ Connect")
            self.toggle_action.setEnabled(True)
            self.setToolTip("Cloudflare WARP: Disconnected")

        # Update Copy IP actions
        self.copy_ipv4_action.setEnabled(bool(ipv4))
        self.copy_ipv6_action.setEnabled(bool(info.get("ipv6")))
        if ipv4:
            self.copy_ipv4_action.setText(f"📋 Copy IPv4 ({ipv4})")
        else:
            self.copy_ipv4_action.setText("📋 Copy Virtual IPv4")

    def _toggle_connection(self):
        """Connect or disconnect asynchronously."""
        if not self.client.is_installed():
            self._install_warp()
            return

        self._is_transitioning = True
        self.setIcon(self.icons["connecting"])
        self.status_action.setText("⏳ Switching connection...")
        self.toggle_action.setEnabled(False)

        is_connected = self._current_info.get("connected", False)
        task = self.client.disconnect if is_connected else self.client.connect

        worker = CommandWorker(task)
        worker.signals.command_finished.connect(self._on_command_finished)
        self.threadpool.start(worker)

    def _on_command_finished(self, ok: bool, message: str):
        """Callback when connect/disconnect/mode command completes."""
        self._is_transitioning = False
        if not ok:
            self._send_notification("WARP Error", message)
        # Immediate refresh to synchronize
        QTimer.singleShot(600, self.refresh_status)

    def _set_mode(self, mode: str):
        """Switch WARP operation mode."""
        self._send_notification("Cloudflare WARP", f"Switching mode to {mode.upper()}...")
        worker = CommandWorker(lambda: self.client.set_mode(mode))
        worker.signals.command_finished.connect(self._on_command_finished)
        self.threadpool.start(worker)

    def _reconnect(self):
        """Reconnect WARP tunnel."""
        def task():
            self.client.disconnect()
            import time
            time.sleep(1)
            return self.client.connect()

        self._is_transitioning = True
        self.setIcon(self.icons["connecting"])
        worker = CommandWorker(task)
        worker.signals.command_finished.connect(self._on_command_finished)
        self.threadpool.start(worker)

    def _copy_ip(self, ip_type: str):
        """Copy IP to clipboard."""
        ip = self._current_info.get(ip_type)
        if ip:
            clipboard = QApplication.clipboard()
            clipboard.setText(ip, QClipboard.Clipboard)
            clipboard.setText(ip, QClipboard.Selection)
            self._send_notification("Copied to Clipboard", f"{ip_type.upper()}: {ip}")

    def _show_details(self):
        """Show full status information in a clean message dialog."""
        info = self._current_info
        details = (
            f"Status: {info.get('status', 'Unknown')}\n"
            f"Health: {info.get('reason', 'N/A')}\n"
            f"Operation Mode: {info.get('mode', 'warp').upper()}\n"
            f"Account: {self.client.get_account_type()}\n"
            f"Virtual IPv4: {info.get('ipv4') or 'Not connected'}\n"
            f"Virtual IPv6: {info.get('ipv6') or 'Not connected'}\n"
            f"Daemon Active: {self.client.is_daemon_running()}"
        )
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Cloudflare WARP Status")
        msg_box.setText(details)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowIcon(self.icons["connected"])
        msg_box.exec_()

    def _get_terminal_cmd(self, command: str) -> list[str]:
        """Detect available terminal emulator, preferring cosmic-term."""
        terms = ["cosmic-term", "gnome-terminal", "ptyxis", "x-terminal-emulator", "alacritty", "kitty"]
        term = next((t for t in terms if shutil.which(t)), "x-terminal-emulator")
        if term == "gnome-terminal":
            return ["gnome-terminal", "--", "bash", "-lc", f"{command}; echo; read -n 1 -s -r -p 'Press any key to close...'"]
        return [term, "-e", "bash", "-lc", f"{command}; echo; read -n 1 -s -r -p 'Press any key to close...'"]

    def _open_settings_terminal(self):
        """Open warp-cli settings in terminal."""
        cmd = self._get_terminal_cmd("warp-cli settings")
        subprocess.Popen(cmd)

    def _open_logs_terminal(self):
        """View live daemon logs."""
        cmd = self._get_terminal_cmd("journalctl -u warp-svc -f")
        subprocess.Popen(cmd)

    def _restart_daemon(self):
        """Restart warp-svc daemon with pkexec."""
        def task():
            res = subprocess.run(["pkexec", "systemctl", "restart", "warp-svc"], check=False)
            return res.returncode == 0, "Restarted warp-svc"

        worker = CommandWorker(task)
        worker.signals.command_finished.connect(self._on_command_finished)
        self.threadpool.start(worker)

    def _toggle_autostart(self, enabled: bool):
        """Toggle desktop autostart entry."""
        if enabled:
            AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
            desktop_content = f"""[Desktop Entry]
Type=Application
Name=Cloudflare WARP COSMIC Panel
Comment=System tray applet for Cloudflare WARP on Pop!_OS COSMIC
Exec={sys.executable} {BASE_DIR}/main.py
Icon={ASSETS_DIR}/warp-connected.png
Terminal=false
Categories=Network;Utility;
X-GNOME-Autostart-enabled=true
"""
            AUTOSTART_FILE.write_text(desktop_content, encoding="utf-8")
            self._send_notification("Autostart Enabled", "WARP panel will start automatically on login.")
        else:
            if AUTOSTART_FILE.exists():
                AUTOSTART_FILE.unlink()
            self._send_notification("Autostart Disabled", "WARP panel autostart removed.")

    def _install_warp(self):
        """Launch installation of cloudflare-warp in terminal."""
        install_script = (
            'curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg && '
            'echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list >/dev/null && '
            'sudo apt-get update && sudo apt-get install -y cloudflare-warp'
        )
        cmd = self._get_terminal_cmd(install_script)
        subprocess.Popen(cmd)

    def _verify_tray_registered(self):
        """Watchdog to re-register icon if StatusNotifierWatcher restarts."""
        if not self.isVisible() or not QSystemTrayIcon.isSystemTrayAvailable():
            self.show()

    def _send_notification(self, title: str, message: str):
        """Send native desktop notification via notify-send or tray message."""
        if shutil.which("notify-send"):
            try:
                icon_path = str(ASSETS_DIR / ("warp-connected.png" if "Connected" in title else "warp-disconnected.png"))
                subprocess.Popen(["notify-send", "-a", "Cloudflare WARP", "-i", icon_path, title, message])
                return
            except Exception:
                pass
        self.showMessage(title, message, QSystemTrayIcon.Information, 3500)

    def _quit_applet(self):
        """Quit the tray applet without disconnecting the background WARP tunnel."""
        self.hide()
        self.app.quit()


def _wait_for_tray_service(timeout_seconds: float = 20.0) -> bool:
    """Wait for StatusNotifierWatcher to be active on D-Bus during login boot."""
    import time
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            res = subprocess.run(
                ["busctl", "--user", "status", "org.kde.StatusNotifierWatcher"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=1.0,
            )
            if res.returncode == 0:
                return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


def main():
    # Wait for COSMIC status notifier watcher on boot
    _wait_for_tray_service(timeout_seconds=25.0)

    # Set app metadata
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv)
    app.setApplicationName("CloudflareWARP-COSMIC-Panel")
    app.setOrganizationName("DasFletchi")
    app.setQuitOnLastWindowClosed(False)

    tray = WarpCosmicTray(app)
    tray.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()


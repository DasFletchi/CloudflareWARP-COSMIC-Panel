"""
Cloudflare WARP client interface for Pop!_OS COSMIC Panel.
Interacts with warp-cli and warp-svc via JSON output and non-blocking calls.
"""

import json
import shutil
import subprocess
from typing import Any, Dict, Optional, Tuple


class WarpClient:
    """Manages communication with Cloudflare warp-cli."""

    def __init__(self, cli_path: Optional[str] = None):
        self.cli_path = cli_path or shutil.which("warp-cli") or "warp-cli"

    def is_installed(self) -> bool:
        """Check if warp-cli is installed and available in PATH."""
        return shutil.which("warp-cli") is not None

    def _run_cli(self, args: list[str], timeout: float = 4.0) -> Tuple[bool, str, int]:
        """Run warp-cli with specified arguments."""
        if not self.is_installed():
            return False, "warp-cli is not installed", 127

        cmd = [self.cli_path] + args
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                check=False,
            )
            out = res.stdout.strip() or res.stderr.strip()
            return res.returncode == 0, out, res.returncode
        except subprocess.TimeoutExpired:
            return False, f"Command timed out after {timeout}s", -1
        except Exception as exc:
            return False, str(exc), 1

    def get_status_info(self) -> Dict[str, Any]:
        """
        Fetch comprehensive status information.
        Uses `warp-cli --json status` and falls back gracefully.
        """
        if not self.is_installed():
            return {
                "installed": False,
                "connected": False,
                "status": "Not Installed",
                "reason": "warp-cli missing",
                "mode": "unknown",
                "ipv4": None,
                "ipv6": None,
            }

        ok, out, _ = self._run_cli(["--json", "status"])
        connected = False
        status_text = "Unknown"
        reason = ""

        if ok:
            try:
                data = json.loads(out)
                status_text = data.get("status", "Unknown")
                reason = data.get("reason", "")
                connected = status_text.strip().lower() == "connected"
            except Exception:
                status_text = out.splitlines()[0] if out else "Unknown"
                connected = "connected" in out.lower() and "disconnected" not in out.lower()
        else:
            # Fallback to plain text check
            ok_plain, out_plain, _ = self._run_cli(["status"])
            if ok_plain:
                status_text = out_plain.splitlines()[0] if out_plain else "Unknown"
                connected = "connected" in out_plain.lower() and "disconnected" not in out_plain.lower()
            else:
                status_text = "Daemon Unavailable"
                reason = out_plain

        ipv4, ipv6 = self.get_virtual_ips()
        mode = self.get_current_mode()

        return {
            "installed": True,
            "connected": connected,
            "status": status_text,
            "reason": reason,
            "mode": mode,
            "ipv4": ipv4,
            "ipv6": ipv6,
        }

    def get_current_mode(self) -> str:
        """Fetch active operation mode (warp, doh, warp+doh, proxy, etc.)."""
        ok, out, _ = self._run_cli(["--json", "settings"])
        if ok:
            try:
                data = json.loads(out)
                return data.get("settings", {}).get("operation_mode", "warp")
            except Exception:
                pass
        return "warp"

    def get_virtual_ips(self) -> Tuple[Optional[str], Optional[str]]:
        """Retrieve assigned IPv4 and IPv6 addresses on the CloudflareWARP interface."""
        ipv4 = None
        ipv6 = None
        try:
            res = subprocess.run(
                ["ip", "-br", "addr", "show", "dev", "CloudflareWARP"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=1.5,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = res.stdout.strip().split()
                # format: CloudflareWARP UNKNOWN 172.16.0.2/32 2606:.../128 fe80:...
                for addr in parts[2:]:
                    ip_clean = addr.split("/")[0]
                    if ":" in ip_clean and not ip_clean.startswith("fe80"):
                        ipv6 = ip_clean
                    elif "." in ip_clean:
                        ipv4 = ip_clean
        except Exception:
            pass
        return ipv4, ipv6

    def connect(self) -> Tuple[bool, str]:
        """Connect to Cloudflare WARP."""
        ok, out, code = self._run_cli(["connect", "--accept-tos"])
        if not ok and "--accept-tos" in out:
            # Older versions do not have --accept-tos
            ok, out, code = self._run_cli(["connect"])
        return ok, out or ("Connected" if ok else "Failed to connect")

    def disconnect(self) -> Tuple[bool, str]:
        """Disconnect from Cloudflare WARP."""
        ok, out, code = self._run_cli(["disconnect"])
        return ok, out or ("Disconnected" if ok else "Failed to disconnect")

    def toggle(self) -> Tuple[bool, str]:
        """Toggle connection state."""
        info = self.get_status_info()
        if info["connected"]:
            return self.disconnect()
        return self.connect()

    def set_mode(self, mode: str) -> Tuple[bool, str]:
        """Set operation mode: warp, doh, warp+doh, proxy."""
        valid_modes = ["warp", "doh", "warp+doh", "dot", "warp+dot", "proxy", "tunnel_only"]
        if mode not in valid_modes:
            return False, f"Invalid mode: {mode}"
        ok, out, _ = self._run_cli(["mode", mode])
        return ok, out

    def get_account_type(self) -> str:
        """Fetch account type (free, teams, zero-trust)."""
        ok, out, _ = self._run_cli(["--json", "registration", "show"])
        if ok:
            try:
                data = json.loads(out)
                return data.get("account", {}).get("type", "Free")
            except Exception:
                pass
        return "Free"

    def is_daemon_running(self) -> bool:
        """Check if warp-svc systemd service is active."""
        try:
            res = subprocess.run(
                ["systemctl", "is-active", "warp-svc"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=1.5,
                check=False,
            )
            return res.stdout.strip() == "active"
        except Exception:
            return False


if __name__ == "__main__":
    client = WarpClient()
    print("Installed:", client.is_installed())
    print("Daemon active:", client.is_daemon_running())
    print("Status:", client.get_status_info())
    print("Account:", client.get_account_type())

# Cloudflare WARP COSMIC Panel 🚀

[![Pop!_OS COSMIC](https://img.shields.io/badge/Desktop-Pop!_OS%20COSMIC-blue?logo=popos)](https://system76.com/cosmic)
[![GNOME Shell](https://img.shields.io/badge/GNOME-45%20%7C%2046%20%7C%2047-orange?logo=gnome)](https://www.gnome.org)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow?logo=python)](https://python.org)
[![Cloudflare WARP](https://img.shields.io/badge/Cloudflare-WARP-orange?logo=cloudflare)](https://1.1.1.1)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A sleek, lightweight, and modern top-bar control applet for **Cloudflare WARP (`warp-cli`)**, natively optimized for **Pop!_OS 24.04 (COSMIC Desktop)** and fully compatible with modern **GNOME Shell (45+)**.

Control your VPN, switch DNS modes, copy your assigned virtual IP, view live diagnostics, and inspect logs without ever having to remember terminal commands!

---

## ✨ Features

- **Native Pop!_OS COSMIC Status Area Integration**: Seamlessly embeds into the COSMIC Panel (`StatusNotifierItem` / SNI) right alongside your network and sound controls.
- **Dynamic Real-Time State Icons**:
  - 🟠 **Connected**: Cloudflare orange with active encryption rays.
  - ⚪ **Disconnected**: Clean slate monochrome cloud.
  - 🔵 **Connecting**: Transition state indicator.
  - 🔴 **Error / Inactive**: Warning badge if `warp-svc` or `warp-cli` requires attention.
- **Instant Quick-Toggle**: Click the tray icon to connect or disconnect in under a second.
- **Mode Switching Menu**:
  - `WARP` (Full Tunnel)
  - `WARP with DoH` (Tunnel + DNS over HTTPS)
  - `1.1.1.1` (DNS-only over HTTPS)
  - `Proxy Mode` (SOCKS5 local proxy)
- **1-Click IP Copy**: Instantly copy your assigned virtual IPv4 (`172.16.0.2`) or IPv6 to the clipboard.
- **Built-in System Tools**:
  - Live daemon log viewer (`cosmic-term -e journalctl -u warp-svc -f`).
  - Settings viewer (`warp-cli settings`).
  - One-click restart of `warp-svc`.
  - Automatic login startup toggle.
- **Modern GNOME 45+ Extension**: Includes a non-blocking ESM extension for GNOME Shell users.

---

## ⚡ 1-Click "EZ" Installation

Open a terminal and run the installer:

```bash
git clone https://github.com/DasFletchi/CloudflareWARP-COSMIC-Panel.git
cd CloudflareWARP-COSMIC-Panel
./install.sh
```

### What `install.sh` does automatically:
1. Verifies dependencies (`python3`, `python3-pyqt5`).
2. Checks if `warp-cli` is installed (and offers a 1-click install if missing).
3. Installs high-resolution SVG and PNG icons into your system icon theme (`~/.local/share/icons/hicolor`).
4. Creates a `warp-cosmic` executable link in `~/.local/bin/`.
5. Sets up the autostart desktop entry and systemd user service (`cloudflare-warp-cosmic.service`).
6. Starts the panel applet immediately!

---

## 🕹️ CLI Usage (`warp-cosmic`)

You can also control WARP from your terminal or bind keyboard shortcuts to `warp-cosmic`:

```bash
warp-cosmic status          # Print live status, mode, and assigned IPs
warp-cosmic toggle          # Toggle connection on or off
warp-cosmic connect         # Connect to WARP
warp-cosmic disconnect      # Disconnect from WARP
warp-cosmic mode warp       # Switch to full WARP tunnel
warp-cosmic mode doh        # Switch to DNS-only (1.1.1.1)
warp-cosmic mode proxy      # Switch to SOCKS5 proxy
warp-cosmic tray            # Launch the tray applet
```

---

## 🔧 Systemd Service Management

The panel runs as a background user service that starts automatically on login:

```bash
# Check status
systemctl --user status cloudflare-warp-cosmic.service

# Restart applet
systemctl --user restart cloudflare-warp-cosmic.service

# Stop applet
systemctl --user stop cloudflare-warp-cosmic.service
```

---

## 💻 Manual Installation (Cloudflare WARP)

If you need to install Cloudflare WARP manually on Ubuntu / Pop!_OS 24.04:

```bash
curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list >/dev/null
sudo apt-get update && sudo apt-get install -y cloudflare-warp
sudo systemctl enable --now warp-svc
warp-cli --accept-tos registration new
warp-cli connect
```

---

## 🗑️ Uninstallation

To remove the applet, icons, and autostart configuration cleanly:

```bash
cd CloudflareWARP-COSMIC-Panel
./uninstall.sh
```

## ❓ Frequently Asked Questions (FAQ)

### Why doesn't the GNOME extension work on Pop!_OS 24.04?
Pop!_OS 24.04 LTS uses the brand-new **COSMIC Desktop Environment** (`cosmic-epoch`) written in Rust, which does not run GNOME Shell extensions. This project provides a dedicated **COSMIC Panel Tray Applet** that natively integrates into COSMIC's `cosmic-applet-status-area` via the StatusNotifierItem (SNI) standard.

### How do I switch DNS modes (e.g. 1.1.1.1 or DoH)?
Right-click the panel icon, open the **Mode** submenu, and select `1.1.1.1 (DoH Only)`, `WARP with DoH`, or `WARP (Full Tunnel)`. You can also run `warp-cosmic mode doh` in your terminal.

### How do I check if the WARP service is running?
Run `warp-cosmic status` in your terminal or check `systemctl status warp-svc`. The panel icon will show a warning indicator if the daemon is inactive.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

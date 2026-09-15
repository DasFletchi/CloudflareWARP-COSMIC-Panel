#!/usr/bin/env bash
#
# install.sh - 1-Click "EZ" Installer for Cloudflare WARP COSMIC Panel
#

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"
SYSTEMD_DIR="$HOME/.config/systemd/user"
ICON_SCALABLE_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
ICON_64_DIR="$HOME/.local/share/icons/hicolor/64x64/apps"
GNOME_EXT_DIR="$HOME/.local/share/gnome-shell/extensions/warp-cosmic-panel@dasfletchi"

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}   Cloudflare WARP COSMIC Panel - Installer${NC}"
echo -e "${BLUE}======================================================${NC}"

# 1. Dependency checks
echo -e "\n${YELLOW}[1/5] Checking dependencies...${NC}"

if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}Python3 is required but not installed. Please run: sudo apt install python3${NC}"
    exit 1
fi

if ! python3 -c "import PyQt5" >/dev/null 2>&1; then
    echo -e "${YELLOW}PyQt5 is not installed. Installing python3-pyqt5 via apt...${NC}"
    sudo apt-get update && sudo apt-get install -y python3-pyqt5
fi

if ! command -v warp-cli >/dev/null 2>&1; then
    echo -e "${YELLOW}Notice: warp-cli is not installed yet.${NC}"
    read -rp "Would you like to install official Cloudflare WARP now? [Y/n] " answer
    answer=${answer:-Y}
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Installing Cloudflare WARP...${NC}"
        curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
        echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list >/dev/null
        sudo apt-get update && sudo apt-get install -y cloudflare-warp
        sudo systemctl enable --now warp-svc
        echo -e "${GREEN}Cloudflare WARP installed and service started!${NC}"
        echo "Registering client..."
        warp-cli --accept-tos registration new || true
    fi
else
    echo -e "${GREEN}✓ Dependencies verified (Python3, PyQt5, warp-cli).${NC}"
fi

# 2. Directory structure
echo -e "\n${YELLOW}[2/5] Creating directories...${NC}"
mkdir -p "$BIN_DIR" "$APP_DIR" "$AUTOSTART_DIR" "$SYSTEMD_DIR" "$ICON_SCALABLE_DIR" "$ICON_64_DIR"

# 3. Installing icons
echo -e "\n${YELLOW}[3/5] Installing icons...${NC}"
cp "$SCRIPT_DIR/cosmic-tray/assets/warp-connected.svg" "$ICON_SCALABLE_DIR/warp-connected.svg"
cp "$SCRIPT_DIR/cosmic-tray/assets/warp-disconnected.svg" "$ICON_SCALABLE_DIR/warp-disconnected.svg"
cp "$SCRIPT_DIR/cosmic-tray/assets/warp-connecting.svg" "$ICON_SCALABLE_DIR/warp-connecting.svg"
cp "$SCRIPT_DIR/cosmic-tray/assets/warp-error.svg" "$ICON_SCALABLE_DIR/warp-error.svg"

cp "$SCRIPT_DIR/cosmic-tray/assets/warp-connected.png" "$ICON_64_DIR/warp-connected.png"
cp "$SCRIPT_DIR/cosmic-tray/assets/warp-disconnected.png" "$ICON_64_DIR/warp-disconnected.png"
cp "$SCRIPT_DIR/cosmic-tray/assets/warp-connecting.png" "$ICON_64_DIR/warp-connecting.png"
cp "$SCRIPT_DIR/cosmic-tray/assets/warp-error.png" "$ICON_64_DIR/warp-error.png"

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi
echo -e "${GREEN}✓ Icons installed.${NC}"

# 4. Installing CLI binary and desktop integration
echo -e "\n${YELLOW}[4/5] Installing launcher & autostart integration...${NC}"
ln -sf "$SCRIPT_DIR/bin/warp-cosmic" "$BIN_DIR/warp-cosmic"
chmod +x "$SCRIPT_DIR/bin/warp-cosmic" "$SCRIPT_DIR/cosmic-tray/main.py"

# Desktop launcher & autostart
cp "$SCRIPT_DIR/autostart/com.dasfletchi.warp-cosmic.desktop" "$APP_DIR/"
cp "$SCRIPT_DIR/autostart/com.dasfletchi.warp-cosmic.desktop" "$AUTOSTART_DIR/"

# Systemd user service
cp "$SCRIPT_DIR/systemd/cloudflare-warp-cosmic.service" "$SYSTEMD_DIR/"
systemctl --user daemon-reload 2>/dev/null || true

echo -e "${GREEN}✓ CLI link created at $BIN_DIR/warp-cosmic.${NC}"
echo -e "${GREEN}✓ Desktop and Autostart entries installed.${NC}"

# Check GNOME compatibility
if [ "$XDG_CURRENT_DESKTOP" != "COSMIC" ] && command -v gnome-shell >/dev/null 2>&1; then
    echo -e "\n${BLUE}Detected GNOME Shell environment.${NC}"
    mkdir -p "$GNOME_EXT_DIR"
    cp -r "$SCRIPT_DIR/gnome-extension/"* "$GNOME_EXT_DIR/"
    echo -e "${GREEN}✓ Modernized GNOME Shell extension installed to $GNOME_EXT_DIR.${NC}"
fi

# 5. Launch
echo -e "\n${YELLOW}[5/5] Launching Cloudflare WARP COSMIC Panel...${NC}"
systemctl --user enable --now cloudflare-warp-cosmic.service 2>/dev/null || {
    nohup "$BIN_DIR/warp-cosmic" tray >/dev/null 2>&1 &
}

echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN}  ✓ Installation Complete! EZ & Ready to go!${NC}"
echo -e "${GREEN}======================================================${NC}"
echo -e "You can now control Cloudflare WARP directly from the top panel."
echo -e "CLI commands available:"
echo -e "  ${BLUE}warp-cosmic status${NC}     - View connection state and IP"
echo -e "  ${BLUE}warp-cosmic toggle${NC}     - Connect / Disconnect quickly"
echo -e "  ${BLUE}warp-cosmic mode <mode>${NC} - Switch modes (warp, doh, proxy)"
echo -e "  ${BLUE}warp-cosmic tray${NC}       - Start tray applet"

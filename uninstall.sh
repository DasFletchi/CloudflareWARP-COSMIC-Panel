#!/usr/bin/env bash
#
# uninstall.sh - Clean uninstaller for Cloudflare WARP COSMIC Panel
#

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}Uninstalling Cloudflare WARP COSMIC Panel...${NC}"

# Stop and disable systemd service
systemctl --user stop cloudflare-warp-cosmic.service 2>/dev/null || true
systemctl --user disable cloudflare-warp-cosmic.service 2>/dev/null || true

# Kill any running tray instance
pkill -f "cosmic-tray/main.py" 2>/dev/null || true

# Remove files
rm -f "$HOME/.local/bin/warp-cosmic"
rm -f "$HOME/.local/share/applications/com.dasfletchi.warp-cosmic.desktop"
rm -f "$HOME/.config/autostart/com.dasfletchi.warp-cosmic.desktop"
rm -f "$HOME/.config/systemd/user/cloudflare-warp-cosmic.service"

# Remove icons
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/warp-"*.svg
rm -f "$HOME/.local/share/icons/hicolor/64x64/apps/warp-"*.png

# Reload systemd
systemctl --user daemon-reload 2>/dev/null || true

echo -e "${GREEN}✓ Cloudflare WARP COSMIC Panel uninstalled cleanly.${NC}"

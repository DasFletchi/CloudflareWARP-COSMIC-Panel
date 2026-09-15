# CloudflareWARP-COSMIC-Panel

GNOME/Pop!_OS top-bar extension for `warp-cli` so Cloudflare WARP can be controlled without opening a terminal.

## Features

- `WARP` indicator in the top bar
- Main menu shows only:
  - current status
  - On/Off toggle
  - `Settings` button
- Clicking `Settings` reveals advanced `warp-cli` actions
- If `warp-cli` is missing, the extension shows a one-click install action and the install command

## Install extension (local)

1. Copy files:
   ```bash
   mkdir -p ~/.local/share/gnome-shell/extensions/warp-cosmic-panel@dasfletchi
   cp -r gnome-extension/* ~/.local/share/gnome-shell/extensions/warp-cosmic-panel@dasfletchi/
   ```
2. Restart GNOME Shell (X11: `Alt+F2`, type `r`) or log out and back in.
3. Enable extension:
   ```bash
   gnome-extensions enable warp-cosmic-panel@dasfletchi
   ```

## One-click install command used when WARP is missing

```bash
curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg && echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list >/dev/null && sudo apt-get update && sudo apt-get install -y cloudflare-warp
```

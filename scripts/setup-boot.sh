#!/usr/bin/env bash
# Install Jarvis systemd user units and autostart desktop entry
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SYSTEMD_DIR="$HOME/.config/systemd/user"
AUTOSTART_DIR="$HOME/.config/autostart"

echo "🔧 Setting up Jarvis boot services..."

# 1. Create systemd user directory
mkdir -p "$SYSTEMD_DIR"

# 2. Copy service files
for svc in jarvis-stt jarvis-tts jarvis-core jarvis-memory jarvis-connectors jarvis-pc-actions jarvis-agent-sessions jarvis-messaging; do
 if [ -f "$PROJECT_ROOT/systemd/${svc}.service" ]; then
 cp "$PROJECT_ROOT/systemd/${svc}.service" "$SYSTEMD_DIR/"
 echo " ✅ Installed ${svc}.service"
 fi
done

# 3. Reload systemd user daemon
systemctl --user daemon-reload
echo "✅ Systemd user daemon reloaded"

# 4. Enable services (start at login)
for svc in jarvis-stt jarvis-tts jarvis-memory jarvis-core jarvis-connectors jarvis-agent-sessions jarvis-pc-actions; do
 if [ -f "$SYSTEMD_DIR/${svc}.service" ]; then
 systemctl --user enable "${svc}.service"
 echo " ✅ Enabled ${svc}"
 fi
done

# 5. Enable lingering (services start at boot, not just login)
loginctl enable-linger "$USER" 2>/dev/null || echo "⚠️ Could not enable lingering (may need sudo)"

# 6. Create autostart desktop entry for UI
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/jarvis-ui.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Jarvis AI Assistant
Comment=AI Personal Assistant HUD Interface
Exec=$PROJECT_ROOT/apps/ui/src-tauri/target/release/jarvis-ui
Icon=utilities-terminal
Terminal=false
Categories=Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF
echo "✅ Created autostart entry: jarvis-ui.desktop"

echo ""
echo "🎉 Jarvis boot setup complete!"
echo ""
echo "To start all services now:"
echo " systemctl --user start jarvis-stt jarvis-tts jarvis-memory jarvis-core jarvis-connectors"
echo ""
echo "To check status:"
echo " systemctl --user status jarvis-*"
echo ""
echo "To view logs:"
echo " journalctl --user -u jarvis-stt -f"
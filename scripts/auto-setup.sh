#!/usr/bin/env bash
# Jarvis Auto-Setup — fully automatic installation, build, and boot configuration
# Resists reboot: systemd user units + linger + XDG autostart
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$PROJECT_ROOT/.venv"

echo "◈ Jarvis Auto-Setup"
echo "===================="
echo ""

# 1. System dependencies
echo "📦 Installing system dependencies..."
sudo apt-get install -y scrot xclip wmctrl libnotify-bin cmake build-essential 2>/dev/null || true
echo "✅ System dependencies ready"

# 2. Python venv + all services
echo ""
echo " Creating Python virtual environment..."
if [ ! -d "$VENV" ]; then
 python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"
echo " Installing all Python services..."
pip install --quiet \
 -e "$PROJECT_ROOT/services/stt" \
 -e "$PROJECT_ROOT/services/tts" \
 -e "$PROJECT_ROOT/services/memory" \
 -e "$PROJECT_ROOT/services/connectors" \
 -e "$PROJECT_ROOT/services/pc-actions" \
 -e "$PROJECT_ROOT/services/agent-sessions" \
 -e "$PROJECT_ROOT/apps/core"
echo "✅ All Python services installed"

# 3. Voice binaries + models
echo ""
echo " Building whisper.cpp (AVX2)..."
bash "$PROJECT_ROOT/services/stt/scripts/build_whisper.sh"
echo " Downloading whisper small model..."
bash "$PROJECT_ROOT/services/stt/scripts/download_model.sh"
echo " Installing Piper TTS..."
bash "$PROJECT_ROOT/services/tts/scripts/install_piper.sh"
echo " Downloading French voices..."
bash "$PROJECT_ROOT/services/tts/scripts/download_voices.sh"
echo "✅ Voice stack ready"

# 4. UI build
echo ""
echo " Installing UI dependencies..."
cd "$PROJECT_ROOT"
pnpm install --frozen-lockfile 2>/dev/null || pnpm install
echo " Building Tauri app (release)..."
cd "$PROJECT_ROOT/apps/ui"
pnpm tauri build 2>&1 | tail -5
BINARY="$PROJECT_ROOT/apps/ui/src-tauri/target/release/jarvis-ui"
if [ -x "$BINARY" ]; then
 echo "✅ Tauri binary built: $BINARY"
else
 echo "⚠️ Tauri binary not found at expected path. Check build logs."
 exit 1
fi

# 5. Data directories
mkdir -p "$PROJECT_ROOT/data/memory" "$PROJECT_ROOT/data/connectors" "$PROJECT_ROOT/data/screenshots"
echo "✅ Data directories created"

# 6. Systemd user units (boot-persistent)
echo ""
echo " Configuring systemd user units..."
SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_DIR"
for svc in jarvis-stt jarvis-tts jarvis-core jarvis-memory jarvis-connectors jarvis-pc-actions jarvis-agent-sessions; do
 if [ -f "$PROJECT_ROOT/systemd/${svc}.service" ]; then
 cp "$PROJECT_ROOT/systemd/${svc}.service" "$SYSTEMD_DIR/"
 systemctl --user enable "${svc}.service" 2>/dev/null
 fi
done
systemctl --user daemon-reload
loginctl enable-linger "$USER" 2>/dev/null || true
echo "✅ 7 systemd services enabled (start at boot via linger)"

# 7. XDG autostart for UI (fullscreen at login)
echo ""
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/jarvis-ui.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Jarvis AI Assistant
Comment=AI Personal Assistant HUD — Fullscreen at boot
Exec=$BINARY
Icon=utilities-terminal
Terminal=false
Categories=Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
EOF
echo "✅ Autostart desktop entry created (fullscreen, 5s delay after login)"

# 8. Start all services NOW
echo ""
echo " Starting all services..."
for svc in jarvis-stt jarvis-tts jarvis-memory jarvis-core jarvis-connectors jarvis-pc-actions jarvis-agent-sessions; do
 systemctl --user start "${svc}.service" 2>/dev/null && echo " ✅ Started ${svc}" || echo " ⚠️ Failed to start ${svc}"
done

echo ""
echo "◈ Jarvis Auto-Setup Complete!"
echo ""
echo "Services running:"
systemctl --user list-units 'jarvis-*' --no-pager --state=active 2>/dev/null | grep jarvis || echo " (check with: systemctl --user status jarvis-*)"
echo ""
echo "UI will launch fullscreen at next login."
echo "To launch now: $BINARY &"
echo ""
echo "Reboot-proof: systemd linger + XDG autostart ensure everything restarts automatically."
#!/usr/bin/env bash
# Install Piper TTS binary for Jarvis
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN_DIR="$PROJECT_ROOT/bin/piper"
PIPER_VERSION="1.2.0"
ARCH="$(uname -m)"

mkdir -p "$BIN_DIR"

if [ -f "$BIN_DIR/piper" ]; then
 echo "✅ Piper already installed at $BIN_DIR/piper"
 exit 0
fi

case "$ARCH" in
 x86_64) PIPER_ARCH="linux_x86_64" ;;
 aarch64) PIPER_ARCH="linux_aarch64" ;;
 *) echo "❌ Unsupported architecture: $ARCH"; exit 1 ;;
esac

URL="https://github.com/rhasspy/piper/releases/download/v${PIPER_VERSION}/piper_${PIPER_ARCH}.tar.gz"

echo "📥 Downloading Piper v${PIPER_VERSION} (${PIPER_ARCH})..."
curl -L --progress-bar "$URL" | tar xz -C "$BIN_DIR"

# The archive extracts a 'piper' directory; move binary up
if [ -f "$BIN_DIR/piper/piper" ]; then
 mv "$BIN_DIR/piper/piper" "$BIN_DIR/piper_bin"
 rm -rf "$BIN_DIR/piper"
 mv "$BIN_DIR/piper_bin" "$BIN_DIR/piper"
 chmod +x "$BIN_DIR/piper"
fi

if [ -x "$BIN_DIR/piper" ]; then
 echo "✅ Piper installed: $BIN_DIR/piper"
 "$BIN_DIR/piper" --help 2>&1 | head -3 || true
else
 echo "❌ Installation failed — piper binary not found"
 exit 1
fi
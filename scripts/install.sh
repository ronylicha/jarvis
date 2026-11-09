#!/usr/bin/env bash
# Jarvis one-shot installation script
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$PROJECT_ROOT/.venv"

echo " Jarvis Installation"
echo "======================"
echo ""

# 1. Python virtual environment
if [ ! -d "$VENV" ]; then
  echo " Creating Python virtual environment..."
  python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"
echo "✅ Python venv ready: $VENV"

# 2. Install Python services
echo ""
echo " Installing Python services..."
pip install --quiet -e "$PROJECT_ROOT/services/stt" \
            -e "$PROJECT_ROOT/services/tts" \
            -e "$PROJECT_ROOT/services/memory" \
            -e "$PROJECT_ROOT/services/connectors" \
            -e "$PROJECT_ROOT/apps/core"
echo "✅ All Python services installed"

# 3. Build whisper.cpp
echo ""
echo " Building whisper.cpp (AVX2)..."
bash "$PROJECT_ROOT/services/stt/scripts/build_whisper.sh"

# 4. Download STT model
echo ""
echo " Downloading whisper small model..."
bash "$PROJECT_ROOT/services/stt/scripts/download_model.sh"

# 5. Install Piper TTS
echo ""
echo " Installing Piper TTS..."
bash "$PROJECT_ROOT/services/tts/scripts/install_piper.sh"

# 6. Download TTS voices
echo ""
echo " Downloading French TTS voices..."
bash "$PROJECT_ROOT/services/tts/scripts/download_voices.sh"

# 7. Install Node.js dependencies (UI)
echo ""
echo " Installing UI dependencies..."
cd "$PROJECT_ROOT"
pnpm install --frozen-lockfile 2>/dev/null || pnpm install
echo "✅ UI dependencies installed"

# 8. Create data directories
mkdir -p "$PROJECT_ROOT/data/memory" "$PROJECT_ROOT/data/connectors"
echo "✅ Data directories created"

echo ""
echo " Jarvis installation complete!"
echo ""
echo "Next steps:"
echo "  1. Set API keys in ~/.jarvis.env:"
echo "     export JARVIS_CORE_ANTHROPIC_API_KEY='sk-ant-...'"
echo "     export JARVIS_MEMORY_API_TOKEN='your-secret-token'"
echo ""
echo "  2. Start all services:"
echo "     source $VENV/bin/activate"
echo "     python -m jarvis_stt.main &"
echo "     python -m jarvis_tts.main &"
echo "     python -m jarvis_memory.main &"
echo "     python -m jarvis_core.main &"
echo "     python -m jarvis_connectors.main &"
echo ""
echo "  3. Build and launch UI:"
echo "     cd apps/ui && pnpm tauri build"
echo ""
echo "  4. Setup boot autostart:"
echo "     bash scripts/setup-boot.sh"
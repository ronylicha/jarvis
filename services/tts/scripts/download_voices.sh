#!/usr/bin/env bash
# Download French voices for Piper TTS
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MODELS_DIR="$PROJECT_ROOT/models"
BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/fr/fr_FR/siwis/medium"

mkdir -p "$MODELS_DIR"

VOICES=(
 "fr_FR-siwis-medium.onnx"
 "fr_FR-siwis-medium.onnx.json"
)

for voice_file in "${VOICES[@]}"; do
 target="$MODELS_DIR/$voice_file"
 if [ -f "$target" ]; then
 echo "✅ Already exists: $voice_file"
 continue
 fi
 echo " Downloading $voice_file..."
 curl -L --progress-bar -o "$target" "$BASE_URL/$voice_file"
done

echo ""
echo "✅ Voices ready in $MODELS_DIR/"
ls -lh "$MODELS_DIR"/fr_FR-*.onnx* 2>/dev/null || echo "⚠️ No FR voices found"
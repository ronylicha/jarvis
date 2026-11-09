#!/usr/bin/env bash
# Download whisper.cpp ggml-small model for French transcription
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MODELS_DIR="$PROJECT_ROOT/models"
MODEL_NAME="ggml-small.bin"
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$MODEL_NAME"

mkdir -p "$MODELS_DIR"

if [ -f "$MODELS_DIR/$MODEL_NAME" ]; then
 echo "✅ Model already exists: $MODELS_DIR/$MODEL_NAME ($(du -h "$MODELS_DIR/$MODEL_NAME" | cut -f1))"
 exit 0
fi

echo " Downloading whisper small model (~460 MB)..."
curl -L --progress-bar -o "$MODELS_DIR/$MODEL_NAME" "$MODEL_URL"

echo "✅ Model downloaded: $MODELS_DIR/$MODEL_NAME ($(du -h "$MODELS_DIR/$MODEL_NAME" | cut -f1))"
#!/usr/bin/env bash
# Build whisper.cpp with AVX2 support for Jarvis STT
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN_DIR="$PROJECT_ROOT/bin/whisper.cpp"

echo "🔨 Building whisper.cpp with AVX2..."

if [ ! -d "$BIN_DIR" ]; then
 echo "📥 Cloning whisper.cpp..."
 git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git "$BIN_DIR"
fi

cd "$BIN_DIR"

# Build with AVX2 (i7-1360P supports AVX2 + VNNI)
cmake -B build -DCMAKE_BUILD_TYPE=Release \
 -DGGML_AVX2=ON \
 -DGGML_FMA=ON \
 -DGGML_NATIVE=OFF

cmake --build build --config Release -j"$(nproc)"

if [ -f "build/bin/whisper-cli" ]; then
 echo "✅ whisper.cpp built successfully at $BIN_DIR/build/bin/whisper-cli"
else
 echo "❌ Build failed — whisper-cli not found"
 exit 1
fi
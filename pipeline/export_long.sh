#!/bin/bash
# Export video in Long format (16:9, max 300 seconds)
set -e

INPUT_VIDEO="${1:-./pipeline/output/output.mp4}"
OUTPUT_FILE="${2:-./pipeline/output/long_final.mp4}"

echo "=== Exporting Long Format (16:9) ==="

ffmpeg -y \
    -i "$INPUT_VIDEO" \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black" \
    -c:v libx264 \
    -profile:v high \
    -level 4.0 \
    -preset medium \
    -crf 18 \
    -c:a aac \
    -b:a 192k \
    -ar 48000 \
    -t 300 \
    -movflags +faststart \
    "$OUTPUT_FILE"

echo "=== Long export complete: $OUTPUT_FILE ==="

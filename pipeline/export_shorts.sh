#!/bin/bash
# Export video in Shorts format (9:16, max 120 seconds)
set -e

INPUT_VIDEO="${1:-./pipeline/output/output.mp4}"
OUTPUT_FILE="${2:-./pipeline/output/shorts_final.mp4}"

echo "=== Exporting Shorts Format (9:16) ==="

ffmpeg -y \
    -i "$INPUT_VIDEO" \
    -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black" \
    -c:v libx264 \
    -profile:v high \
    -level 4.0 \
    -preset medium \
    -crf 20 \
    -c:a aac \
    -b:a 192k \
    -ar 44100 \
    -t 120 \
    -movflags +faststart \
    "$OUTPUT_FILE"

echo "=== Shorts export complete: $OUTPUT_FILE ==="

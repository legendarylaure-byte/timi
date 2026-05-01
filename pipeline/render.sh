#!/bin/bash
# FFmpeg Video Composition Pipeline
# Combines animation frames, voice-over, and background music

set -e

INPUT_FRAMES_DIR="${1:-./pipeline/output/frames}"
VOICE_AUDIO="${2:-./pipeline/output/voice.mp3}"
MUSIC_AUDIO="${3:-./pipeline/output/music.mp3}"
OUTPUT_DIR="${4:-./pipeline/output}"
OUTPUT_FILE="${5:-output.mp4}"
FORMAT="${6:-long}"

if [ "$FORMAT" = "shorts" ]; then
    RESOLUTION="1080x1920"
    FPS=30
    MAX_DURATION=120
else
    RESOLUTION="1920x1080"
    FPS=30
    MAX_DURATION=300
fi

echo "=== Vyom Ai Cloud - Video Composition ==="
echo "Format: $FORMAT"
echo "Resolution: $RESOLUTION"
echo "Max Duration: ${MAX_DURATION}s"

# Step 1: Create video from frames
echo "Step 1: Creating video from animation frames..."
ffmpeg -y \
    -framerate $FPS \
    -i "$INPUT_FRAMES_DIR/frame_%04d.png" \
    -c:v libx264 \
    -profile:v high \
    -pix_fmt yuv420p \
    -vf "scale=$RESOLUTION:force_original_aspect_ratio=decrease,pad=$RESOLUTION:(ow-iw)/2:(oh-ih)/2" \
    -preset medium \
    -crf 23 \
    "$OUTPUT_DIR/video_raw.mp4"

# Step 2: Trim voice audio to video duration
echo "Step 2: Trimming audio..."
VIDEO_DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUTPUT_DIR/video_raw.mp4")
ffmpeg -y \
    -i "$VOICE_AUDIO" \
    -t "$VIDEO_DURATION" \
    -c copy \
    "$OUTPUT_DIR/voice_trimmed.mp3"

# Step 3: Mix voice and music
echo "Step 3: Mixing audio..."
ffmpeg -y \
    -i "$OUTPUT_DIR/voice_trimmed.mp3" \
    -i "$MUSIC_AUDIO" \
    -filter_complex "[0:a]volume=0.8[voice];[1:a]volume=0.2[music];[voice][music]amix=inputs=2:duration=shortest[a]" \
    -map "[a]" \
    -c:a aac \
    -b:a 192k \
    "$OUTPUT_DIR/mixed_audio.m4a"

# Step 4: Combine video and audio
echo "Step 4: Combining video and audio..."
ffmpeg -y \
    -i "$OUTPUT_DIR/video_raw.mp4" \
    -i "$OUTPUT_DIR/mixed_audio.m4a" \
    -c:v copy \
    -c:a aac \
    -shortest \
    "$OUTPUT_DIR/$OUTPUT_FILE"

# Step 5: Final duration check
FINAL_DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUTPUT_DIR/$OUTPUT_FILE")
echo "Final video duration: ${FINAL_DURATION}s"

if (( $(echo "$FINAL_DURATION > $MAX_DURATION" | bc -l) )); then
    echo "WARNING: Video exceeds maximum duration. Trimming..."
    ffmpeg -y \
        -i "$OUTPUT_DIR/$OUTPUT_FILE" \
        -t "$MAX_DURATION" \
        -c copy \
        "$OUTPUT_DIR/${OUTPUT_FILE%.mp4}_final.mp4"
    mv "$OUTPUT_DIR/${OUTPUT_FILE%.mp4}_final.mp4" "$OUTPUT_DIR/$OUTPUT_FILE"
fi

echo "=== Video composition complete: $OUTPUT_DIR/$OUTPUT_FILE ==="

"""
End-to-end test: render "How Transformers Work"
Generates voiceover (Edge TTS), dispatches scenes via Asset Router,
composites with xfade transitions, produces final MP4.
"""

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import edge_tts
from utils.asset_router import dispatch_scenes
from utils.video_compositor import composite_video
from utils.music_gen import generate_background_music

VOICE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp", "test_voice")
os.makedirs(VOICE_DIR, exist_ok=True)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

VIDEO_ID = "how_transformers_work_v1"
FORMAT_TYPE = "long"

NARRATION = """
The transformer architecture revolutionized deep learning. Introduced in 2017, it replaced recurrent networks with a simple but powerful idea: attention.

At its core, the transformer uses self-attention to weigh the importance of every word relative to every other word. This lets it capture long-range dependencies without the sequential bottleneck of RNNs.

The architecture has two main blocks: an encoder and a decoder. The encoder processes the input sequence, while the decoder generates the output.

Inside each encoder layer, we have multi-head attention followed by a feed-forward network. Layer normalization and residual connections help training stability.

The key innovation is the attention mechanism. It computes three matrices: queries, keys, and values. The attention score is the dot product of queries and keys, scaled and passed through softmax.

Multi-head attention runs this process in parallel, allowing the model to focus on different parts of the input simultaneously. Each head learns a different relationship pattern.

After attention, the feed-forward network applies two linear transformations with a ReLU activation. This adds non-linearity and helps the model learn complex patterns.

Positional encoding is crucial since transformers have no built-in notion of word order. Sine and cosine functions of different frequencies encode each position.

The decoder is similar but adds masked self-attention to prevent looking ahead at future tokens, plus cross-attention that attends to the encoder output.

Training transformers requires significant data and compute. They're trained with a language modeling objective: predict the next token. Modern variants like BERT, GPT, and T5 have pushed the boundaries of what's possible.

From machine translation to code generation, transformers are now the foundation of modern AI. Understanding this architecture is essential for anyone working in deep learning today.
"""

SCENES = [
    {
        "asset_type": "STOCK_FOOTAGE",
        "keyword": "neural network abstract",
        "target_duration": 10.0,
        "description": "Transformer architecture overview - abstract AI visualization",
        "transition": "dissolve",
    },
    {
        "asset_type": "DIAGRAM_ANIMATION",
        "keyword": "attention mechanism",
        "target_duration": 12.0,
        "description": "Self-attention visualization - QKV computation",
        "transition": "dissolve",
    },
    {
        "asset_type": "DIAGRAM_ANIMATION",
        "keyword": "transformer architecture",
        "target_duration": 14.0,
        "description": "Encoder-decoder transformer block diagram",
        "transition": "dissolve",
    },
    {
        "asset_type": "STOCK_FOOTAGE",
        "keyword": "data center servers",
        "target_duration": 8.0,
        "description": "Training infrastructure - GPU clusters",
        "transition": "slide_left",
    },
    {
        "asset_type": "DIAGRAM_ANIMATION",
        "keyword": "multi-head attention",
        "target_duration": 10.0,
        "description": "Attention mechanism breakdown: QKV matrices, scaled dot-product",
        "transition": "dissolve",
    },
    {
        "asset_type": "CODE_SNIPPET",
        "keyword": "python code",
        "target_duration": 8.0,
        "description": "Multi-head attention PyTorch implementation",
        "code_lines": [
            "import torch.nn as nn",
            "",
            "class MultiHeadAttention(nn.Module):",
            "    def __init__(self, d_model, num_heads):",
            "        super().__init__()",
            "        self.num_heads = num_heads",
            "        self.d_k = d_model // num_heads",
            "        self.W_q = nn.Linear(d_model, d_model)",
            "        self.W_k = nn.Linear(d_model, d_model)",
            "        self.W_v = nn.Linear(d_model, d_model)",
        ],
        "transition": "dissolve",
    },
    {
        "asset_type": "STOCK_FOOTAGE",
        "keyword": "artificial intelligence chip",
        "target_duration": 8.0,
        "description": "AI chip / GPU hardware for transformer training",
        "transition": "fade",
    },
    {
        "asset_type": "DIAGRAM_ANIMATION",
        "keyword": "neural network layers",
        "target_duration": 12.0,
        "description": "Feed-forward network inside transformer - MLP layers",
        "transition": "dissolve",
    },
    {
        "asset_type": "SCREEN_CAPTURE",
        "capture_type": "terminal",
        "keyword": "training log",
        "target_duration": 6.0,
        "description": "Transformer training in progress",
        "code_lines": [
            "$ python3 train.py --model transformer --epochs 50",
            "Epoch 1/50: loss=4.23, acc=0.312",
            "Epoch 5/50: loss=2.87, acc=0.564",
            "Epoch 10/50: loss=1.94, acc=0.723",
            "Epoch 25/50: loss=1.12, acc=0.891",
            "Epoch 50/50: loss=0.67, acc=0.943",
            "# Training complete. Best checkpoint saved.",
        ],
        "transition": "dissolve",
    },
    {
        "asset_type": "STOCK_FOOTAGE",
        "keyword": "machine learning data",
        "target_duration": 8.0,
        "description": "Data pipeline / training data flow",
        "transition": "slide_right",
    },
    {
        "asset_type": "DIAGRAM_ANIMATION",
        "keyword": "bar chart comparison",
        "target_duration": 10.0,
        "description": "Transformer model comparison - BERT, GPT, T5 performance",
        "transition": "dissolve",
    },
    {
        "asset_type": "STOCK_FOOTAGE",
        "keyword": "future technology",
        "target_duration": 8.0,
        "description": "Future of AI - closing shot",
        "transition": "dissolve",
    },
]


async def generate_voiceover(text: str, video_id: str) -> str:
    path = os.path.join(VOICE_DIR, f"{video_id}.mp3")
    tts = edge_tts.Communicate(text, voice="en-US-JennyNeural", rate="-5%", pitch="-2Hz")
    await tts.save(path)
    print(f"[voice] Saved: {path} ({os.path.getsize(path)} bytes)")
    return path


def get_timings(voice_path: str) -> tuple[float, list[float]]:
    from pydub import AudioSegment
    audio = AudioSegment.from_file(voice_path)
    total_dur = len(audio) / 1000.0
    seg_dur = total_dur / len(SCENES)
    scene_timings = [seg_dur] * len(SCENES)
    return total_dur, scene_timings


async def main():
    print("=" * 60)
    print("Test: How Transformers Work")
    print("=" * 60)

    print("\n[1/5] Generating voiceover via Edge TTS...")
    start = time.time()
    voice_path = await generate_voiceover(NARRATION, VIDEO_ID)
    total_dur, scene_timings = get_timings(voice_path)
    print(f"       Duration: {total_dur:.1f}s, took {time.time()-start:.1f}s")

    print("\n[2/5] Updating scene durations to match voice...")
    for i, s in enumerate(SCENES):
        s["target_duration"] = max(scene_timings[i], 6.0)
    print(f"       {len(SCENES)} scenes, total {sum(s['target_duration'] for s in SCENES):.1f}s")

    print("\n[3/5] Dispatching via Asset Router...")
    start = time.time()
    clips = dispatch_scenes(SCENES, VIDEO_ID, FORMAT_TYPE)
    print(f"       Got {len(clips)} clips, took {time.time()-start:.1f}s")
    for c in clips:
        print(f"       [{c.get('asset_type','?')}] {c.get('source','?')} -> {os.path.basename(c['path'])} ({c['duration']:.1f}s)")

    if not clips:
        print("ERROR: No clips generated!")
        return

    print(f"\n[3.5/5] Generating background music ({total_dur:.0f}s, AI Explained)...")
    music_result = generate_background_music("AI Explained", duration=total_dur)
    music_path = music_result.get("path")
    if music_path:
        print(f"       Music: {music_result.get('mood', '?')} mood -> {music_path}")
    else:
        print("       Music generation failed — continuing without music")

    print("\n[4/5] Compositing final video with xfade transitions...")
    start = time.time()
    result = composite_video(
        clips=clips,
        voice_path=voice_path,
        music_path=music_path,
        format_type=FORMAT_TYPE,
        video_id=VIDEO_ID,
    )
    print(f"       Compositing took {time.time()-start:.1f}s")

    if result:
        size_mb = os.path.getsize(result) / (1024 * 1024)
        print(f"\n[5/5] SUCCESS! Final video: {result}")
        print(f"       Size: {size_mb:.1f} MB")
        print(f"       Duration: {sum(c['duration'] for c in clips):.1f}s")
    else:
        print("\n[5/5] FAILED: No video produced")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

"""Batch LTX worker — loads model once, generates all scenes, then decodes and saves."""

import json
import os
import random
import sys
import time

import mlx.core as mx
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def main():
    config_path = sys.argv[1]
    with open(config_path) as f:
        config = json.load(f)

    from ltx_pipelines_mlx.distilled import DistilledPipeline
    from ltx_core_mlx.utils.memory import aggressive_cleanup

    pipe = DistilledPipeline(
        model_dir=config["model_dir"],
        gemma_model_id=config["gemma_id"],
        low_memory=True,
        low_ram_streaming=True,
    )
    pipe.verbose = False

    scenes = config["scenes"]
    cpu_latents = []

    for i, scene in enumerate(scenes):
        try:
            seed = (hash(scene.get("prompt", "")) + i) & 0x7FFFFFFF
            video_latent, audio_latent = pipe.generate_two_stage(
                prompt=scene["prompt"],
                height=480,
                width=704,
                num_frames=scene["frames"],
                frame_rate=24,
                seed=seed,
            )
            # Materialize + move to CPU immediately to free GPU memory for next scene
            video_cpu = np.array(mx.eval(video_latent))
            audio_cpu = np.array(mx.eval(audio_latent))
            del video_latent, audio_latent
            cpu_latents.append((video_cpu, audio_cpu))
        except Exception as e:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "message": f"Scene {i} generation failed: {e}",
                        "path": scene["output"],
                    }
                ),
                flush=True,
            )
            cpu_latents.append(None)

    pipe.dit = None
    pipe._loaded = False
    aggressive_cleanup()

    pipe._load_decoders()

    for cpu_lat, scene in zip(cpu_latents, scenes):
        if cpu_lat is None:
            continue
        video_np, audio_np = cpu_lat
        video_latent = mx.array(video_np)
        audio_latent = mx.array(audio_np)
        try:
            pipe._decode_and_save_video(
                video_latent, audio_latent, scene["output"], frame_rate=24
            )
            del video_latent, audio_latent
            print(
                json.dumps({"status": "ok", "path": scene["output"]}),
                flush=True,
            )
        except Exception as e:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "message": f"Decode failed: {e}",
                        "path": scene["output"],
                    }
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()

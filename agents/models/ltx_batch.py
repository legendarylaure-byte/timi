"""Batch LTX worker — loads model once, generates all scenes, then decodes and saves."""

import json
import os
import random
import sys
import time

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
    )
    pipe.verbose = False

    scenes = config["scenes"]
    latents = []

    for i, scene in enumerate(scenes):
        try:
            seed = random.randint(0, 2**31 - 1)
            video_latent, audio_latent = pipe.generate_two_stage(
                prompt=scene["prompt"],
                height=448,
                width=704,
                num_frames=scene["frames"],
                frame_rate=24,
                seed=seed,
            )
            latents.append((video_latent, audio_latent))
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
            latents.append(None)

    pipe.dit = None
    pipe._loaded = False
    aggressive_cleanup()

    pipe._load_decoders()

    for lat, scene in zip(latents, scenes):
        if lat is None:
            continue
        video_latent, audio_latent = lat
        try:
            pipe._decode_and_save_video(
                video_latent, audio_latent, scene["output"], frame_rate=24
            )
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

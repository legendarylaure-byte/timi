import os
import modal

app = modal.App("vyom-ai-svd-render")

svd_image = (
    modal.Image.debian_slim()
    .pip_install(
        "diffusers==0.30.0",
        "transformers==4.46.0",
        "accelerate==1.1.0",
        "torch==2.5.0",
        "safetensors==0.4.5",
        "pillow==11.0.0",
    )
)

@app.function(gpu="A10G", image=svd_image, timeout=600)
def render_frames(storyboard: str, num_frames: int = 48):
    import torch
    from diffusers import StableVideoDiffusionPipeline
    from diffusers.utils import load_image, export_to_video
    from PIL import Image

    pipe = StableVideoDiffusionPipeline.from_pretrained(
        "stabilityai/stable-video-diffusion-img2vid-xt",
        torch_dtype=torch.float16,
        variant="fp16",
    )
    pipe.enable_model_cpu_offload()

    frames = []
    scenes = storyboard.split("---SCENE---")

    for i, scene in enumerate(scenes[:num_frames // 4]):
        image_input = Image.new("RGB", (1024, 576), color=(255, 255, 255))
        frames_for_scene = pipe(
            image_input,
            decode_chunk_size=8,
            motion_bucket_id=127,
            noise_aug_strength=0.1,
            num_frames=4,
        ).frames[0]
        frames.extend(frames_for_scene)

    output_path = "/tmp/rendered_frames"
    os.makedirs(output_path, exist_ok=True)

    for i, frame in enumerate(frames):
        frame.save(f"{output_path}/frame_{i:04d}.png")

    return output_path, len(frames)

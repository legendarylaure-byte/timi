"""
Modal GPU function for FLUX character sprite generation.

Generates high-quality cartoon character sprites for the animation pipeline.
Fallback when local MPS/CUDA is unavailable.
"""
import os
import modal

app = modal.App("vyom-ai-flux-gen")

flux_image = (
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

CHARACTER_PROMPTS = {
    "pixel": (
        "cute cartoon robot character, round pink body, screen face, "
        "antenna on top, friendly expression, thick outlines, "
        "solid bright colors, children's cartoon, white background, front view"
    ),
    "nova": (
        "cute cartoon star character, golden yellow, warm glow, "
        "big friendly eyes, thick outlines, solid colors, "
        "children's cartoon, white background, front view"
    ),
    "ziggy": (
        "cute cartoon rainbow character, multicolor round body, "
        "big expressive eyes, thick outlines, solid bright colors, "
        "children's cartoon, white background, front view"
    ),
    "boop": (
        "cute cartoon blue penguin character, round chubby body, "
        "light blue belly, rosy cheeks, big eyes, "
        "thick outlines, solid colors, children's cartoon, white background, front view"
    ),
    "sprout": (
        "cute cartoon plant seedling character, light green round body, "
        "pink flower on head, leaf arms, friendly expression, "
        "thick outlines, solid colors, children's cartoon, white background, front view"
    ),
}


@app.function(gpu="A10G", image=flux_image, timeout=300)
def generate_character(char_name: str) -> str:
    import torch
    from diffusers import StableDiffusionXLPipeline
    from PIL import Image

    prompt = CHARACTER_PROMPTS.get(char_name, CHARACTER_PROMPTS["pixel"])
    neg = ("photorealistic, 3d render, shading, complex background, "
           "watermark, text, logo, distorted, ugly, bad anatomy, extra limbs")

    pipe = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=torch.float16,
        use_safetensors=True,
    )
    pipe.enable_model_cpu_offload()

    image = pipe(
        prompt=prompt,
        negative_prompt=neg,
        num_inference_steps=30,
        guidance_scale=7.5,
        width=512,
        height=512,
    ).images[0]

    image = image.convert("RGBA")
    pixels = image.load()
    w, h = image.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if r > 240 and g > 240 and b > 240:
                pixels[x, y] = (r, g, b, 0)

    output_path = f"/tmp/{char_name}_base.png"
    image.save(output_path, "PNG")
    return output_path

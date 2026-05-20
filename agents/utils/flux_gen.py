"""
FLUX/SD character sprite generator for the animation pipeline.

Produces higher-quality character body sprites with the same
file naming convention as the procedural generator.

Pipeline: local GPU (MPS/CUDA) -> Modal -> procedural fallback
Controlled by USE_FLUX_GEN env var.
"""
import os
import json
import warnings
from pathlib import Path
from PIL import Image

ASSETS_DIR = Path(__file__).parent / "assets"
CHARACTERS_DIR = ASSETS_DIR / "characters"
SPRITE_SIZE = 512

USE_FLUX_GEN = os.getenv("USE_FLUX_GEN", "false").lower() == "true"

CHARACTER_PROMPTS = {
    "pixel": (
        "A cute cartoon robot character with a round pink body, "
        "a screen-like face, antenna on top, friendly expression, "
        "thick black outlines, solid bright colors, children's cartoon style, "
        "white background, front-facing, full body"
    ),
    "nova": (
        "A cute cartoon star-shaped character, golden yellow with warm glow, "
        "big friendly eyes, thick black outlines, solid bright colors, "
        "children's cartoon style, white background, front-facing, full body"
    ),
    "ziggy": (
        "A cute cartoon rainbow character, multicolor round body, "
        "big expressive eyes, thick black outlines, solid bright colors, "
        "children's cartoon style, white background, front-facing, full body"
    ),
    "boop": (
        "A cute cartoon blue penguin-like character, round and chubby, "
        "light blue belly, rosy cheeks, big expressive eyes, "
        "thick black outlines, solid bright colors, children's cartoon style, "
        "white background, front-facing, full body"
    ),
    "sprout": (
        "A cute cartoon plant/seedling character, light green round body, "
        "a pink flower on head, leaf arms, friendly expression, "
        "thick black outlines, solid bright colors, children's cartoon style, "
        "white background, front-facing, full body"
    ),
}

CHARACTER_NEGATIVE_PROMPTS = (
    "photorealistic, 3d render, shading, complex background, "
    "watermark, text, logo, distorted, ugly, bad anatomy, "
    "extra limbs, blurry, low quality, grainy"
)


def _ensure_output_dir(char_name: str) -> Path:
    d = CHARACTERS_DIR / char_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _model_is_fully_cached(model_id: str) -> bool:
    """Check if a HuggingFace model is fully cached locally."""
    from huggingface_hub import scan_cache_dir
    try:
        cache_info = scan_cache_dir()
        for repo in cache_info.repos:
            if repo.repo_id == model_id and repo.repo_type == "model":
                return repo.size_on_disk > 0 and not repo.nb_incomplete
    except Exception:
        pass
    return False


def _generate_sd_local(char_name: str, output_path: Path) -> bool:
    """Generate a single character sprite using SDXL on local GPU."""
    try:
        import torch
        from diffusers import StableDiffusionXLPipeline
    except ImportError:
        print("[flux_gen] diffusers/torch not installed")
        return False

    device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print("[flux_gen] No GPU available for local SD generation")
        return False

    model_id = "stabilityai/stable-diffusion-xl-base-1.0"
    if not _model_is_fully_cached(model_id):
        print(f"[flux_gen] {model_id} not fully cached ({device}), trying API instead")
        return False

    try:
        print(f"[flux_gen] Loading SDXL on {device}...")
        pipe = StableDiffusionXLPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16 if device != "cpu" else torch.float32,
            use_safetensors=True,
        )
        pipe = pipe.to(device)
        if device == "mps":
            pipe.enable_attention_slicing()

        prompt = CHARACTER_PROMPTS.get(char_name, CHARACTER_PROMPTS["pixel"])
        print(f"[flux_gen] Generating {char_name}...")
        image = pipe(
            prompt=prompt,
            negative_prompt=CHARACTER_NEGATIVE_PROMPTS,
            num_inference_steps=30,
            guidance_scale=7.5,
            width=SPRITE_SIZE,
            height=SPRITE_SIZE,
        ).images[0]

        image = image.convert("RGBA")
        pixels = image.load()
        w, h = image.size
        for y in range(h):
            for x in range(w):
                r, g, b, a = pixels[x, y]
                if r > 240 and g > 240 and b > 240:
                    pixels[x, y] = (r, g, b, 0)

        image.save(output_path, "PNG")
        print(f"[flux_gen] Saved -> {output_path}")
        return True

    except Exception as e:
        print(f"[flux_gen] Local SD generation failed: {e}")
        return False


def _generate_modal(char_name: str, output_path: Path) -> bool:
    """Generate via Modal GPU function."""
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "pipeline"))
        from gpu.flux_gen import generate_character
        result_path = generate_character.remote(char_name)
        if result_path and os.path.exists(result_path):
            import shutil
            shutil.copy(result_path, str(output_path))
            print(f"[flux_gen] Modal generated -> {output_path}")
            return True
    except Exception as e:
        print(f"[flux_gen] Modal generation failed: {e}")
    return False


def _generate_sd_api(char_name: str, output_path: Path) -> bool:
    """Generate character sprite via Hugging Face free Inference API."""
    try:
        import requests
    except ImportError:
        return False

    prompt = CHARACTER_PROMPTS.get(char_name, CHARACTER_PROMPTS["pixel"])
    neg = CHARACTER_NEGATIVE_PROMPTS

    hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN") or ""
    headers = {"Authorization": f"Bearer {hf_token}"} if hf_token else {}

    try:
        print(f"[flux_gen] Calling HF Inference API for {char_name}...")
        response = requests.post(
            "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0",
            headers=headers,
            json={
                "inputs": prompt,
                "parameters": {
                    "negative_prompt": neg,
                    "num_inference_steps": 25,
                    "guidance_scale": 7.5,
                },
            },
            timeout=120,
        )
        if response.status_code == 200:
            import io
            img = Image.open(io.BytesIO(response.content))
            img = img.convert("RGBA")
            pixels = img.load()
            w, h = img.size
            for y in range(h):
                for x in range(w):
                    r, g, b, a = pixels[x, y]
                    if r > 240 and g > 240 and b > 240:
                        pixels[x, y] = (r, g, b, 0)
            img = img.resize((SPRITE_SIZE, SPRITE_SIZE), Image.LANCZOS)
            img.save(output_path, "PNG")
            print(f"[flux_gen] HF API generated -> {output_path}")
            return True
        else:
            print(f"[flux_gen] HF API returned {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"[flux_gen] HF API failed: {e}")
        return False


def generate_character_base(char_name: str, force: bool = False) -> Path | None:
    """Generate or retrieve the base character sprite.

    Checks for existing sprite first, generates only if missing or forced.
    """
    char_dir = CHARACTERS_DIR / char_name
    char_dir.mkdir(parents=True, exist_ok=True)
    base_path = char_dir / f"{char_name}_base.png"

    if base_path.exists() and not force:
        return base_path

    if not USE_FLUX_GEN:
        return None

    # Try API first (fast, no model download needed)
    if _generate_sd_api(char_name, base_path):
        return base_path
    # Then try local GPU (requires fully cached model)
    if _generate_sd_local(char_name, base_path):
        return base_path
    # Finally try Modal
    if _generate_modal(char_name, base_path):
        return base_path

    print(f"[flux_gen] All generation methods failed for {char_name}")
    return None


def generate_all_bases(force: bool = False) -> dict[str, Path | None]:
    """Generate base sprites for all 5 characters."""
    results = {}
    for char_name in ["pixel", "nova", "ziggy", "boop", "sprout"]:
        path = generate_character_base(char_name, force=force)
        results[char_name] = path
        if path:
            print(f"  {char_name}: {path}")
        else:
            print(f"  {char_name}: skipped (no GPU or USE_FLUX_GEN=false)")
    return results


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    if not USE_FLUX_GEN:
        print("Set USE_FLUX_GEN=true to enable SD/FLUX generation")
        print("Usage: USE_FLUX_GEN=true python utils/flux_gen.py [--force]")
        sys.exit(0)
    generate_all_bases(force=force)

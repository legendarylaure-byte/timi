"""Image generation for thumbnails + static scene backgrounds.

Pollinations.ai is the default because it needs no key and no billing. Gemini image
models are supported as a switch but are quota-blocked on the current project
(all `gemini-*-image` models return 429), so the provider is env-switchable rather
than hardcoded.

Env:
    IMAGE_GEN_PROVIDER  pollinations (default) | gemini | none
    IMAGE_GEN_MODEL     provider-specific model id
    IMAGE_GEN_ENABLED   true/false master switch

Every function returns "" on failure — callers must have a real fallback. Image gen
is best-effort, never a hard pipeline dependency.
"""
import os
import logging

logger = logging.getLogger(__name__)

# Photographic quality terms. Procedural gradients and blurred circles cannot
# compete in a thumbnail; the subject has to look like a real photo.
_PHOTO_SUFFIX = (
    "cinematic photography, dramatic lighting, sharp focus, high detail, "
    "professional photography, 8k, dramatic composition, vivid colors"
)
_NO_TEXT = "no text, no watermark, no letters, no words, no typography"

_provider_cache: dict = {}


def _provider() -> str:
    p = os.getenv("IMAGE_GEN_PROVIDER", "pollinations").strip().lower()
    if p not in ("pollinations", "gemini", "none"):
        logger.warning(f"[IMAGE_GEN] unknown provider '{p}', falling back to pollinations")
        p = "pollinations"
    return p


def _enabled() -> bool:
    return os.getenv("IMAGE_GEN_ENABLED", "true").strip().lower() not in ("false", "0", "no")


def enhance_prompt(prompt: str, style: str = "") -> str:
    """Turn a scene/topic description into a photographic prompt."""
    base = " ".join(str(prompt or "").split())[:600]
    if not base:
        base = "abstract technology background"
    parts = [base]
    if style:
        parts.append(str(style))
    parts.append(_PHOTO_SUFFIX)
    parts.append(_NO_TEXT)
    return ", ".join(parts)


def _validate_image(path: str) -> bool:
    """Confirm the download is a real, non-trivial image (not an HTML error page)."""
    if not path or not os.path.exists(path):
        return False
    if os.path.getsize(path) < 2000:
        return False
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            return im.width >= 64 and im.height >= 64
    except Exception:
        return False


def _pollinations(prompt: str, width: int, height: int, seed: int, out_path: str) -> str:
    import requests

    model = os.getenv("IMAGE_GEN_MODEL", "flux")
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt, safe='')}"
    params = {
        "width": width, "height": height, "nologo": "true",
        "seed": seed, "model": model, "enhance": "false",
    }
    key = os.getenv("POLLINATIONS_API_KEY", "").strip()
    if key:
        params["token"] = key

    resp = requests.get(url, params=params, timeout=90)
    if resp.status_code != 200 or len(resp.content) < 2000:
        logger.warning(f"[IMAGE_GEN] pollinations HTTP {resp.status_code} ({len(resp.content)}B)")
        return ""

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(resp.content)
    return out_path if _validate_image(out_path) else ""


def _gemini(prompt: str, width: int, height: int, seed: int, out_path: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return ""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return ""

    model = os.getenv("IMAGE_GEN_MODEL", "gemini-3.1-flash-image")
    try:
        client = genai.Client(api_key=api_key)
        r = client.models.generate_content(
            model=model, contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        for part in (r.candidates[0].content.parts if r.candidates else []):
            inline = getattr(part, "inline_data", None)
            if not inline or not getattr(inline, "data", None):
                continue
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(inline.data)
            return out_path if _validate_image(out_path) else ""
    except Exception as e:
        logger.warning(f"[IMAGE_GEN] gemini image failed: {str(e)[:120]}")
    return ""


def generate_image(
    prompt: str,
    out_path: str,
    width: int = 1280,
    height: int = 720,
    seed: int = 0,
    style: str = "",
    retries: int = 2,
) -> str:
    """Generate one image. Returns out_path on success, "" on any failure."""
    if not _enabled() or _provider() == "none":
        return ""

    full = enhance_prompt(prompt, style)
    provider = _provider()

    for attempt in range(retries + 1):
        # Vary the seed per retry so a transient failure doesn't return the same bad image.
        use_seed = (seed + attempt * 7919) % 2_147_483_647 if seed else (attempt * 7919 + 13)
        if provider == "gemini":
            result = _gemini(full, width, height, use_seed, out_path)
        else:
            result = _pollinations(full, width, height, use_seed, out_path)
        if result:
            logger.info(f"[IMAGE_GEN] {provider} ok -> {out_path} ({width}x{height}, seed={use_seed})")
            return result
    logger.warning(f"[IMAGE_GEN] {provider} failed after {retries + 1} attempts: {str(prompt)[:60]}")
    return ""


def generate_variants(
    prompt: str,
    out_dir: str,
    count: int = 3,
    width: int = 1280,
    height: int = 720,
    seed: int = 0,
    style: str = "",
) -> list:
    """Generate `count` distinct images. Returns only the paths that validated."""
    import hashlib
    os.makedirs(out_dir, exist_ok=True)
    base = int(hashlib.sha256(str(prompt).encode()).hexdigest()[:8], 16)
    paths = []
    for i in range(count):
        p = os.path.join(out_dir, f"img_{base}_{i}.jpg")
        got = generate_image(prompt, p, width, height, seed=base + i * 104729, style=style)
        if got:
            paths.append(got)
    return paths


if __name__ == "__main__":
    import tempfile
    ok = generate_image(
        "a futuristic AI data center with glowing server racks",
        os.path.join(tempfile.gettempdir(), "image_gen_demo.jpg"),
        1280, 720, seed=7,
    )
    assert ok, "image generation failed"
    from PIL import Image
    with Image.open(ok) as im:
        print(f"OK {ok} {im.width}x{im.height} {os.path.getsize(ok)}B")

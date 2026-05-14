import os

ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))
CHARACTERS_DIR = os.path.join(ASSETS_DIR, "characters")
BACKGROUNDS_DIR = os.path.join(ASSETS_DIR, "backgrounds")
EFFECTS_DIR = os.path.join(ASSETS_DIR, "effects")


def get_asset_path(asset_type: str, name: str) -> str:
    mapping = {
        "character": CHARACTERS_DIR,
        "background": BACKGROUNDS_DIR,
        "effect": EFFECTS_DIR,
    }
    base = mapping.get(asset_type, ASSETS_DIR)
    path = os.path.join(base, name)
    if os.path.exists(path):
        return path
    return None


def ensure_dirs():
    for d in [CHARACTERS_DIR, BACKGROUNDS_DIR, EFFECTS_DIR]:
        os.makedirs(d, exist_ok=True)

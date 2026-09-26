"""Self-check for the render chain's fallback floor.

Run: python -m utils.render_chain_selfcheck

Why this exists: the pipeline is zero-cost, so there is no AI video model (LTX needs
MLX, which is Apple-only; the cloud model is deliberately disabled). That means every
scene depends on the fallback chain terminating in an asset. Before this, a paid
provider claimed to be available and failed every call, so a regression here would
silently leave scenes with no visual at all.

The floor is: branded card -> AI video model -> stock -> branded title card. A scene
is only DROPPED if even the title card fails. These checks exercise that floor
deterministically by stubbing the network (stock) and asserting no scene is dropped.
"""
import logging
import os

logging.disable(logging.CRITICAL)

import utils.asset_router as ar


def _scene(i: int, rt: str = "stock") -> dict:
    return {
        "render_type": rt,
        "keyword": f"quantum computing scene {i}",
        "description": f"a detailed shot of topic number {i}",
        "asset_keywords": [f"topic {i}"],
        "target_duration": 6.0,
    }


def test_no_ai_video_model_is_available():
    """Documents the zero-cost state: nothing paid/generative is live."""
    from models.registry import get_video_model
    model = get_video_model()
    assert model is None or not model.is_available(), \
        f"an AI video model is active: {getattr(model, 'name', lambda: model)()}"


def test_cloud_model_stays_disabled():
    """The paid fallback must not quietly switch itself back on."""
    from models.replicate_model import ReplicateVideoModel, version_is_valid, MODEL_VERSION
    m = ReplicateVideoModel()
    assert m.is_available() is False, "paid cloud model reported available"
    assert version_is_valid(MODEL_VERSION) is False, \
        "MODEL_VERSION is valid but is_available() still False — inconsistent"


def test_scene_falls_back_to_branded_card_when_stock_exhausted():
    """With no video model and no stock hit, the scene must still get an image."""
    orig_stock = ar._get_stock_clip
    ar._get_stock_clip = lambda *a, **k: None
    try:
        res = ar.dispatch_scene(_scene(1), "selftest-1", 0, "long", "Science & Technology")
    finally:
        ar._get_stock_clip = orig_stock
    assert res is not None, "scene was DROPPED — no asset from the fallback floor"
    assert res.get("path") and os.path.exists(res["path"]), \
        f"fallback returned a non-existent path: {res}"
    assert res.get("asset_type") in ("STATIC_IMAGE", "STOCK_FOOTAGE"), res


def test_no_scene_dropped_across_many_scenes():
    """Whole-batch safety net: with every remote source stubbed out, every scene
    in a realistic batch must still resolve to an asset."""
    orig_stock = ar._get_stock_clip
    ar._get_stock_clip = lambda *a, **k: None
    dropped, assets = [], []
    try:
        for i in range(12):
            res = ar.dispatch_scene(_scene(i), "selftest-batch", i, "long", "AI News")
            if res is None:
                dropped.append(i)
            else:
                assets.append(res.get("path"))
    finally:
        ar._get_stock_clip = orig_stock
    assert not dropped, f"{len(dropped)} scene(s) DROPPED: {dropped}"
    missing = [p for p in assets if not (p and os.path.exists(p))]
    assert not missing, f"{len(missing)} scene(s) got a non-existent path"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  PASS {name}")
    print("render chain selfcheck OK")

"""Guard every TTS provider against the BaseTTSProvider contract.

Why this exists: `voice_gen` calls `provider.generate(..., is_documentary=...)` on
whatever `get_tts_provider()` returns. `KokoroProvider.generate` was missing that
keyword, so ANY environment with VOICE_PROVIDER unset or misspelled died with
`TypeError: generate() got an unexpected keyword argument 'is_documentary'` on the
first TTS call -- killing the whole pipeline, not just dubbing. Production was safe
only because agents/.env pinned `VOICE_PROVIDER=edge`. Nothing checked that, so the
next provider edit could silently reintroduce it.

This asserts, for every provider class:
  1. it is instantiable (a missing ABC method would raise at class creation),
  2. `generate` / `generate_timing` accept every parameter the ABC declares,
     or at minimum every keyword voice_gen actually passes,
  3. the provider name resolves, and an unknown name raises.

Run:  python3 -m utils.voice_provider_selfcheck
"""
import inspect
import os
import sys

from utils.voice_provider import (
    DEFAULT_VOICE_PROVIDER,
    VALID_VOICE_PROVIDERS,
    BaseTTSProvider,
    EdgeTTSProvider,
    GoogleCloudTTSProvider,
    KokoroProvider,
    get_tts_provider,
)

# The ABC is the contract, but assert the real call site too: voice_gen passes
# is_documentary= to BOTH generate() and generate_timing() (utils/voice_gen.py:446),
# so a provider missing it dies on the first call. generate_timing has no
# output_path -- it returns timings instead of writing audio -- hence per-method.
REQUIRED_KEYWORDS = {
    "generate": ("text", "output_path", "voice", "rate", "pitch",
                 "is_deep_lesson", "is_documentary"),
    "generate_timing": ("text", "voice", "rate", "pitch",
                        "is_deep_lesson", "is_documentary"),
}

PROVIDERS = (EdgeTTSProvider, GoogleCloudTTSProvider, KokoroProvider)


def _accepts(fn, keyword: str) -> bool:
    """True if fn accepts `keyword` by name, or takes **kwargs."""
    params = inspect.signature(fn).parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return True
    return keyword in params


def check_contract(cls) -> list:
    fails = []
    inst = cls()  # ABC with unimplemented methods raises TypeError here
    for meth in ("generate", "generate_timing"):
        fn = getattr(inst, meth, None)
        if fn is None:
            fails.append(f"{cls.__name__}: missing {meth}()")
            continue
        missing = [k for k in REQUIRED_KEYWORDS[meth] if not _accepts(fn, k)]
        if missing:
            fails.append(f"{cls.__name__}.{meth}() missing params: {', '.join(missing)}")
    for meth in ("name", "is_available"):
        if not callable(getattr(inst, meth, None)):
            fails.append(f"{cls.__name__}: missing {meth}()")
    return fails


def check_resolution() -> list:
    fails = []
    import utils.voice_provider as vp
    for name in VALID_VOICE_PROVIDERS:
        vp._PROVIDER_INSTANCE = None
        try:
            vp.get_tts_provider(name)
        except ValueError as e:
            fails.append(f"valid provider {name!r} rejected: {e}")
        except Exception as e:  # noqa: BLE001
            fails.append(f"valid provider {name!r} raised {type(e).__name__}: {e}")
    for bad in ("edge-tts", "kokoro_x", "", "EDGE_TTS"):
        vp._PROVIDER_INSTANCE = None
        try:
            got = vp.get_tts_provider(bad)
        except ValueError:
            continue  # correct: refuses the typo
        except Exception as e:  # noqa: BLE001
            fails.append(f"bad provider {bad!r} raised {type(e).__name__} not ValueError: {e}")
            continue
        fails.append(f"bad provider {bad!r} silently resolved to {got.name()!r}")

    # unset must land on the documented default, not on an accident
    saved = os.environ.pop("VOICE_PROVIDER", None)
    try:
        vp._PROVIDER_INSTANCE = None
        got = vp.get_tts_provider()
        if got.name() != DEFAULT_VOICE_PROVIDER:
            fails.append(f"unset VOICE_PROVIDER -> {got.name()!r}, expected {DEFAULT_VOICE_PROVIDER!r}")
    finally:
        vp._PROVIDER_INSTANCE = None
        if saved is not None:
            os.environ["VOICE_PROVIDER"] = saved
    return fails


def main() -> int:
    assert VALID_VOICE_PROVIDERS and DEFAULT_VOICE_PROVIDER in VALID_VOICE_PROVIDERS
    fails = []
    for cls in PROVIDERS:
        print(f"[1] {cls.__name__:24s} contract ...", end=" ", flush=True)
        f = check_contract(cls)
        fails += f
        print("FAIL" if f else "ok")
    print("[2] provider resolution      ...", end=" ", flush=True)
    f = check_resolution()
    fails += f
    print("FAIL" if f else "ok")
    print(f"[3] default={DEFAULT_VOICE_PROVIDER!r} valid={list(VALID_VOICE_PROVIDERS)}")

    if fails:
        print("\nFAILED:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("\nvoice_provider_selfcheck: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

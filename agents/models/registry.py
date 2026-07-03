import os
import logging

logger = logging.getLogger(__name__)

_REGISTRY = {}
_INSTANCES = {}


def register(name: str, model_class):
    _REGISTRY[name] = model_class


def get_video_model(name: str | None = None):
    if name is None:
        name = os.getenv("VIDEO_MODEL", "ltx")

    if name in _INSTANCES:
        return _INSTANCES[name]

    if name not in _REGISTRY:
        logger.warning("[ModelRegistry] Unknown model '%s', falling back to ltx", name)
        name = "ltx"

    try:
        instance = _REGISTRY[name]()
        _INSTANCES[name] = instance
        if not instance.is_available():
            logger.warning("[ModelRegistry] '%s' not available, trying fallbacks", name)
            for fallback_name, fallback_cls in _REGISTRY.items():
                if fallback_name == name:
                    continue
                fallback = fallback_cls()
                if fallback.is_available():
                    logger.info("[ModelRegistry] Falling back to '%s'", fallback_name)
                    _INSTANCES[fallback_name] = fallback
                    return fallback
        return instance
    except Exception as e:
        logger.error("[ModelRegistry] Failed to init '%s': %s", name, e)
        return None

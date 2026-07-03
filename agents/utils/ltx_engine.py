import warnings
warnings.warn(
    "Import from 'utils.ltx_engine' is deprecated. Use 'models' instead.",
    DeprecationWarning, stacklevel=2
)

from models import get_video_model
from models.ltx_model import LtxVideoModel

_model_instance = None


def _get_model():
    global _model_instance
    if _model_instance is None:
        _model_instance = get_video_model("ltx")
    return _model_instance


def is_available() -> bool:
    m = _get_model()
    return m is not None and m.is_available()


def generate_clip(prompt: str, duration: int = 10,
                  output_path: str | None = None) -> str | None:
    m = _get_model()
    if m is None:
        return None
    return m.generate_clip(prompt, duration, output_path)

from models.ltx_model import LtxVideoModel
from models.registry import register, get_video_model
from models.base_video_model import BaseVideoModel

register("ltx", LtxVideoModel)

try:
    from models.wan_model import WanVideoModel
    register("wan2.1", WanVideoModel)
except ImportError:
    pass

try:
    from models.replicate_model import ReplicateVideoModel
    register("replicate", ReplicateVideoModel)
except ImportError:
    pass

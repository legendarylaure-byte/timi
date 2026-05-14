#!/usr/bin/env python3
import json
import sys
import os
import base64
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    try:
        scene_json = sys.stdin.read()
        if not scene_json.strip():
            print(json.dumps({"error": "No input received"}), file=sys.stderr)
            return 1

        scene = json.loads(scene_json)
        format_type = scene.pop("format_type", "shorts")

        from utils.animation_engine import render_single_frame

        img = render_single_frame(scene, format_type)

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        print(encoded)
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

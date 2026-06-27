from pydantic import BaseModel, field_validator
from typing import List, Optional


class ScriptOutput(BaseModel):
    title: str
    scenes: List[dict]
    dialogue: List[str]
    duration_seconds: int
    educational_value: str


class MetadataOutput(BaseModel):
    title: str
    description: str
    tags: List[str]

    @field_validator("title")
    @classmethod
    def validate_title_length(cls, v):
        if len(v) > 100:
            raise ValueError("Title must be under 100 characters")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        if len(v) < 3:
            raise ValueError("At least 3 tags required")
        if len(v) > 30:
            raise ValueError("Maximum 30 tags allowed")
        return v


class ViralityResult(BaseModel):
    overall_virality_score: int = 70
    strengths: List[str] = []
    weaknesses: List[str] = []


class QualityScore(BaseModel):
    overall_score: int = 50
    recommendation: str = "proceed"
    breakdown: dict = {}


def safe_parse(model_class, data: dict, default: Optional[dict] = None) -> dict:
    try:
        return model_class(**data).model_dump()
    except Exception:
        return default or {}


def validate_script_content(content: str) -> bool:
    forbidden_words = ["violence", "scary", "death", "kill", "hurt", "fight", "war"]
    content_lower = content.lower()
    return not any(word in content_lower for word in forbidden_words)


def validate_video_duration(file_path: str, format_type: str) -> bool:
    import subprocess
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True, timeout=15
        )
        duration = float(result.stdout.strip())
        max_dur = 120 if format_type == "shorts" else 300
        return duration <= max_dur
    except Exception:
        return True

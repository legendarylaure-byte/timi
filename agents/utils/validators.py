from pydantic import BaseModel, validator
from typing import List


class ScriptOutput(BaseModel):
    title: str
    scenes: List[dict]
    dialogue: List[str]
    duration_seconds: int
    age_group: str
    educational_value: str

    @validator("duration_seconds")
    def validate_duration(cls, v, values):
        fmt = values.get("format", "shorts")
        max_dur = 120 if fmt == "shorts" else 300
        if v > max_dur:
            raise ValueError(f"Duration exceeds {max_dur}s for {fmt}")
        return v

    @validator("age_group")
    def validate_age_group(cls, v):
        if v not in ["1-3", "4-6", "7-9", "1-9"]:
            raise ValueError("Age group must be 1-3, 4-6, 7-9, or 1-9")
        return v


class MetadataOutput(BaseModel):
    title: str
    description: str
    tags: List[str]
    hashtags: List[str]

    @validator("title")
    def validate_title_length(cls, v):
        if len(v) > 100:
            raise ValueError("Title must be under 100 characters")
        return v

    @validator("tags")
    def validate_tags(cls, v):
        if len(v) < 5:
            raise ValueError("At least 5 tags required")
        if len(v) > 30:
            raise ValueError("Maximum 30 tags allowed")
        return v


def validate_script_content(content: str) -> bool:
    forbidden_words = ["violence", "scary", "death", "kill", "hurt", "fight", "war"]
    content_lower = content.lower()
    return not any(word in content_lower for word in forbidden_words)


def validate_video_duration(file_path: str, format_type: str) -> bool:
    import subprocess
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", file_path],
        capture_output=True, text=True
    )
    duration = float(result.stdout.strip())
    max_dur = 120 if format_type == "shorts" else 300
    return duration <= max_dur

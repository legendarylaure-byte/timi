# Pipeline Improvement Implementation

## File 1: agents/utils/voice_gen.py

### Fix: XML escaping in `_wrap_ssml()` (line 51-72)

Add 4 lines after the docstring and before `emphasis_words` assignment:

```python
# XML-escape text first so &, <, > don't break SSML parsing
text = (
    text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
)
```

## File 2: agents/main.py

### Change 1: LONG_MAX_DURATION default 180→600 (line 295)
Change `"180"` to `"600"`:
```python
LONG_MAX_DURATION = int(os.getenv("LONG_MAX_DURATION", 600))
```

### Change 2: Wire LONG_MAX_DURATION into script_kwargs for long videos
Find the `generate_long_video()` call and add `"max_duration": max_duration` to the `script_kwargs` dict. Current code at ~line 1160 passes `SHORTS_MAX_DURATION` for shorts; the long path already has `video_dur` / `max_duration` available.

## File 3: agents/crew/scriptwriter.py

### Scale for 10-min content (lines 27-34)

```python
if fmt == "long":
    format_instructions = f"""
CRITICAL: This is a LONG-FORM video ({category}). Write enough content for {max_duration} seconds.
- Write 1500-2500 words for the narration.
- Include 25-35 distinct scenes, each 10-15 seconds.
- Structure: Hook (0-15s) → Context (15-60s) → Main explanation (20-30 scenes) → Summary → Outro with CTA.
...
"""
```

Also increase `max_tokens` from `8000` to `12000` for long format (line 8):
```python
max_tokens = 12000 if is_long else 4000
```

## File 4: agents/.env

Add or change:
```
LONG_MAX_DURATION=600
```

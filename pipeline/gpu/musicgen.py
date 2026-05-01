import os
import modal

app = modal.App("vyom-ai-music-gen")

musicgen_image = (
    modal.Image.debian_slim()
    .pip_install(
        "transformers==4.46.0",
        "torch==2.5.0",
        "scipy==1.14.0",
        "soundfile==0.12.1",
    )
)

@app.function(gpu="T4", image=musicgen_image, timeout=300)
def generate_music(prompt: str, duration_seconds: int = 120):
    from transformers import AutoProcessor, MusicgenForConditionalGeneration
    import scipy.io.wavfile as wavfile
    import numpy as np

    processor = AutoProcessor.from_pretrained("facebook/musicgen-small")
    model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small")

    inputs = processor(
        text=[prompt],
        padding=True,
        return_tensors="pt",
    )

    max_new_tokens = int(duration_seconds * 50)
    audio_values = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        guidance_scale=3.0,
    )

    sampling_rate = model.config.audio_encoder.sampling_rate
    audio = audio_values[0, 0].numpy()

    output_path = "/tmp/background_music.wav"
    wavfile.write(output_path, sampling_rate, audio)

    return output_path

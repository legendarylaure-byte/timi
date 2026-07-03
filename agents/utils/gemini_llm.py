import os
from google import genai
from google.genai import types
from crewai.llm import LLM


class GeminiLLM(LLM):
    def __init__(self, model=None, api_key=None, temperature=0.7, max_tokens=2000, **kwargs):
        model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self._model_name = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client = genai.Client(api_key=api_key)
        super().__init__(model=model, api_key=api_key, temperature=temperature, max_tokens=max_tokens, **kwargs)

    def call(self, messages, callbacks=None):
        system_instruction = None
        user_contents = []
        for msg in messages:
            if msg.get("role") == "system":
                system_instruction = msg.get("content", "")
            else:
                user_contents.append(msg.get("content", ""))

        prompt = "\n".join(user_contents)
        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction or None,
                    temperature=self._temperature,
                    max_output_tokens=self._max_tokens,
                ),
            )
            return response.text if response.text else ""
        except Exception as e:
            print(f"[GEMINI] API call failed: {e}")
            raise

import os
import google.generativeai as genai
from crewai.llm import LLM


class GeminiLLM(LLM):
    def __init__(self, model=None, api_key=None, temperature=0.7, max_tokens=2000, **kwargs):
        model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        genai.configure(api_key=api_key)
        self._model_name = model
        self._generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        super().__init__(model=model, api_key=api_key, temperature=temperature, max_tokens=max_tokens, **kwargs)

    def call(self, messages, callbacks=None):
        system_instruction = None
        user_contents = []
        for msg in messages:
            if msg.get("role") == "system":
                system_instruction = msg.get("content", "")
            else:
                user_contents.append(msg.get("content", ""))

        model = genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system_instruction or None,
        )

        prompt = "\n".join(user_contents)
        try:
            response = model.generate_content(
                prompt,
                generation_config=self._generation_config,
            )
            return response.text if response.text else ""
        except Exception as e:
            print(f"[GEMINI] API call failed: {e}")
            raise

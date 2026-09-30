import logging

import httpx
from google import genai
from google.genai import errors, types

logger = logging.getLogger(__name__)


class GeminiProvider:
    name = "Gemini"

    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000))
        )
        self._model = model

    def generate(self, prompt: str, system_instruction: str | None = None) -> str | None:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=system_instruction),
            )
        except errors.APIError, httpx.HTTPError:
            logger.exception("Falló la llamada a Gemini")
            return None
        return (response.text or "").strip() or None

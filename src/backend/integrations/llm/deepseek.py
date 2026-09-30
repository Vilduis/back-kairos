import logging

import httpx

logger = logging.getLogger(__name__)


class DeepSeekProvider:
    name = "DeepSeek"

    def __init__(self, api_key: str, model: str, base_url: str, timeout_seconds: float) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )
        self._model = model

    def generate(self, prompt: str, system_instruction: str | None = None) -> str | None:
        messages = [{"role": "system", "content": system_instruction}] if system_instruction else []
        messages.append({"role": "user", "content": prompt})
        try:
            response = self._client.post(
                "/chat/completions", json={"model": self._model, "messages": messages}
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPError, KeyError, IndexError, ValueError:
            logger.exception("Falló la llamada a DeepSeek")
            return None
        return (content or "").strip() or None

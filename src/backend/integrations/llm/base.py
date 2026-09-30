from typing import Protocol


class LLMProvider(Protocol):
    name: str

    def generate(self, prompt: str, system_instruction: str | None = None) -> str | None:
        """Devuelve el texto generado, o None si el proveedor falla o responde vacío."""
        ...

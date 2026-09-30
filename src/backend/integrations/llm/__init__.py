import logging
from functools import cache

from backend.core.config import LLMProviderName, get_settings
from backend.integrations.llm.base import LLMProvider
from backend.integrations.llm.deepseek import DeepSeekProvider
from backend.integrations.llm.gemini import GeminiProvider

logger = logging.getLogger(__name__)


def _build_provider(name: LLMProviderName) -> LLMProvider | None:
    settings = get_settings()
    match name:
        case "deepseek" if settings.deepseek_api_key:
            return DeepSeekProvider(
                settings.deepseek_api_key,
                settings.deepseek_model,
                settings.deepseek_base_url,
                settings.llm_timeout_seconds,
            )
        case "gemini" if settings.gemini_api_key:
            return GeminiProvider(
                settings.gemini_api_key, settings.gemini_model, settings.llm_timeout_seconds
            )
    logger.warning("Proveedor LLM '%s' sin API key; se omite", name)
    return None


@cache
def get_providers() -> tuple[LLMProvider, ...]:
    providers = tuple(filter(None, map(_build_provider, get_settings().llm_providers)))
    if not providers:
        logger.warning("Ningún proveedor LLM disponible; se usarán mensajes predefinidos")
    return providers


def generate_text(prompt: str, system_instruction: str | None = None) -> str | None:
    for provider in get_providers():
        if text := provider.generate(prompt, system_instruction):
            return text
        logger.warning("%s no generó respuesta; se intenta el siguiente proveedor", provider.name)
    return None

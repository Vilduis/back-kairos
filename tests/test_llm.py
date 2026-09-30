import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from google.genai import errors

from backend.core.config import get_settings
from backend.integrations import llm
from backend.integrations.llm.deepseek import DeepSeekProvider
from backend.integrations.llm.gemini import GeminiProvider

# Referencia sin caché tomada antes de que el fixture global reemplace get_providers.
build_providers = llm.get_providers.__wrapped__


@dataclass
class StubProvider:
    name: str
    result: str | None

    def generate(self, prompt: str, system_instruction: str | None = None) -> str | None:
        return self.result


class TestProviderChain:
    def test_uses_first_provider_that_answers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        chain = (StubProvider("A", None), StubProvider("B", "respuesta B"), StubProvider("C", "C"))
        monkeypatch.setattr(llm, "get_providers", lambda: chain)

        assert llm.generate_text("hola") == "respuesta B"

    def test_returns_none_when_all_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(llm, "get_providers", lambda: (StubProvider("A", None),))

        assert llm.generate_text("hola") is None

    @pytest.mark.parametrize(
        ("order", "keys", "expected"),
        [
            (
                ["deepseek", "gemini"],
                {"deepseek_api_key": "d", "gemini_api_key": "g"},
                ["DeepSeek", "Gemini"],
            ),
            (
                ["gemini", "deepseek"],
                {"deepseek_api_key": "d", "gemini_api_key": "g"},
                ["Gemini", "DeepSeek"],
            ),
            (["deepseek", "gemini"], {"deepseek_api_key": None, "gemini_api_key": "g"}, ["Gemini"]),
            (["gemini"], {"deepseek_api_key": "d", "gemini_api_key": "g"}, ["Gemini"]),
            (["deepseek", "gemini"], {"deepseek_api_key": None, "gemini_api_key": None}, []),
        ],
    )
    def test_builds_configured_providers_with_keys(
        self,
        monkeypatch: pytest.MonkeyPatch,
        order: list[str],
        keys: dict[str, str | None],
        expected: list[str],
    ) -> None:
        settings = get_settings().model_copy(update={"llm_providers": order, **keys})
        monkeypatch.setattr(llm, "get_settings", lambda: settings)

        providers = build_providers()

        assert [provider.name for provider in providers] == expected


def _deepseek(handler: Any) -> DeepSeekProvider:
    provider = DeepSeekProvider("clave", "deepseek-chat", "https://api.deepseek.com", 5)
    provider._client = httpx.Client(
        base_url="https://api.deepseek.com",
        headers={"Authorization": "Bearer clave"},
        transport=httpx.MockTransport(handler),
    )
    return provider


class TestDeepSeekProvider:
    def test_sends_chat_completion_and_returns_content(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"choices": [{"message": {"content": "  Hola  "}}]})

        text = _deepseek(handler).generate("pregunta", "sistema")

        assert text == "Hola"
        request = requests[0]
        assert request.url.path == "/chat/completions"
        assert request.headers["Authorization"] == "Bearer clave"
        assert json.loads(request.content) == {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "sistema"},
                {"role": "user", "content": "pregunta"},
            ],
        }

    def test_omits_system_message_when_missing(self) -> None:
        bodies: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            bodies.append(json.loads(request.content))
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        _deepseek(handler).generate("pregunta")

        assert bodies[0]["messages"] == [{"role": "user", "content": "pregunta"}]

    @pytest.mark.parametrize(
        "response",
        [
            httpx.Response(500, json={"error": "caído"}),
            httpx.Response(200, json={"choices": []}),
            httpx.Response(200, text="no es json"),
            httpx.Response(200, json={"choices": [{"message": {"content": "   "}}]}),
        ],
        ids=["error-http", "sin-choices", "json-invalido", "vacio"],
    )
    def test_returns_none_on_failure(self, response: httpx.Response) -> None:
        assert _deepseek(lambda _: response).generate("pregunta") is None

    def test_returns_none_on_network_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("sin red", request=request)

        assert _deepseek(handler).generate("pregunta") is None


def _gemini(result: str | Exception) -> tuple[GeminiProvider, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    def generate_content(**kwargs: Any) -> SimpleNamespace:
        calls.append(kwargs)
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(text=result)

    provider = GeminiProvider("clave", "gemini-2.5-flash", 5)
    provider._client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    return provider, calls


class TestGeminiProvider:
    def test_passes_system_instruction_and_strips_text(self) -> None:
        provider, calls = _gemini("  ¿Qué te gusta?  ")

        assert provider.generate("pregunta", "sistema") == "¿Qué te gusta?"
        assert calls[0]["model"] == "gemini-2.5-flash"
        assert calls[0]["contents"] == "pregunta"
        assert calls[0]["config"].system_instruction == "sistema"

    @pytest.mark.parametrize(
        "result",
        [
            errors.ServerError(503, {"error": {"message": "caído", "status": "UNAVAILABLE"}}),
            httpx.ConnectError("sin red"),
            "   ",
        ],
        ids=["error-api", "error-red", "vacio"],
    )
    def test_returns_none_on_failure(self, result: str | Exception) -> None:
        provider, _ = _gemini(result)

        assert provider.generate("pregunta") is None

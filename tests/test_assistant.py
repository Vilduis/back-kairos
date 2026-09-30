from dataclasses import dataclass, field

import pytest

from backend.conversation.assistant import (
    FALLBACK_QUESTIONS,
    TASK_FALLBACK_QUESTIONS,
    ChatTurn,
    FollowupPhase,
    generate_closing_message,
    generate_open_followup,
)
from backend.core.enums import MessageType

SIGNAL_TEXTS = [
    "me gusta programar videojuegos",
    "me encanta la matemática",
    "disfruto dibujar paisajes",
    "soy bueno organizando eventos",
    "me interesa la ciencia",
]


@dataclass
class FakeProvider:
    result: str | None
    name: str = "Fake"
    calls: list[tuple[str, str | None]] = field(default_factory=list)

    def generate(self, prompt: str, system_instruction: str | None = None) -> str | None:
        self.calls.append((prompt, system_instruction))
        return self.result


def _use_provider(monkeypatch: pytest.MonkeyPatch, result: str | None) -> FakeProvider:
    provider = FakeProvider(result)
    monkeypatch.setattr("backend.integrations.llm.get_providers", lambda: (provider,))
    return provider


@pytest.mark.parametrize(
    ("user_texts", "phase", "task"),
    [
        ([], FollowupPhase.OPENING, False),
        (["hola"], FollowupPhase.OPENING, False),
        (SIGNAL_TEXTS[:1], FollowupPhase.DEEPENING, False),
        (["me gusta analizar problemas difíciles"], FollowupPhase.DEEPENING, True),
        (SIGNAL_TEXTS[:3], FollowupPhase.CONTEXT, False),
        ([*SIGNAL_TEXTS[:2], "puedes ayudarme a analizar datos"], FollowupPhase.CONTEXT, True),
        (SIGNAL_TEXTS, FollowupPhase.VALUES, False),
    ],
)
def test_followup_fallback_uses_stage_templates(
    user_texts: list[str], phase: FollowupPhase, task: bool
) -> None:
    options = TASK_FALLBACK_QUESTIONS[phase] if task else FALLBACK_QUESTIONS[phase]
    assert generate_open_followup(user_texts) in options


def test_followup_fallback_skips_questions_already_asked() -> None:
    options = FALLBACK_QUESTIONS[FollowupPhase.OPENING]
    history = [ChatTurn(MessageType.BOT, f"  {question} ") for question in options[:2]]
    history.append(ChatTurn(MessageType.USER, "hola"))

    assert generate_open_followup(["hola"], history) == options[2]


def test_followup_fallback_is_deterministic() -> None:
    assert generate_open_followup(SIGNAL_TEXTS) == generate_open_followup(SIGNAL_TEXTS)


def test_followup_uses_provider_with_history_and_name(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _use_provider(monkeypatch, "¿Qué te gusta crear?")
    history = [ChatTurn(MessageType.BOT, "¡Hola!"), ChatTurn(MessageType.USER, "hola")]

    text = generate_open_followup(["hola"], history, "Ana María Pérez")

    assert text == "¿Qué te gusta crear?"
    prompt, system_instruction = provider.calls[0]
    assert "Kairos: ¡Hola!\nEstudiante: hola" in prompt
    assert system_instruction is not None
    assert "El nombre del estudiante es Ana." in system_instruction


def test_followup_falls_back_when_providers_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_provider(monkeypatch, None)

    assert generate_open_followup(["hola"]) in FALLBACK_QUESTIONS[FollowupPhase.OPENING]


def test_closing_fallback_mentions_topics_and_name() -> None:
    texts = ["Me gusta programar", "también las matemáticas y la música", "y el arte"]

    message = generate_closing_message(texts, "Luis Vilder")

    assert message.startswith("¡Luis, con lo que me contaste sobre programación, ")
    assert "programación, matemáticas y arte ya tengo suficiente" in message


def test_closing_fallback_without_topics() -> None:
    message = generate_closing_message(["hola", "nada en especial"])

    assert message.startswith("¡ya tengo suficiente información para estimar tu perfil")


def test_closing_without_texts_does_not_call_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _use_provider(monkeypatch, "no debería usarse")

    message = generate_closing_message(["  "], "Ana")

    assert message.startswith("¡Ana, ya tengo suficiente información")
    assert provider.calls == []


def test_closing_uses_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _use_provider(monkeypatch, "¡Ana, ya tengo tu perfil!")

    assert generate_closing_message(["me gusta el arte"], "Ana") == "¡Ana, ya tengo tu perfil!"
    assert "- me gusta el arte" in provider.calls[0][0]


def test_closing_falls_back_when_providers_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_provider(monkeypatch, None)

    assert "sobre arte" in generate_closing_message(["me gusta el arte"])

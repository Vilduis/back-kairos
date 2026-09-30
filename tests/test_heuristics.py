import pytest

from backend.conversation.heuristics import (
    count_signals,
    is_acceptance,
    is_greeting,
    is_negative,
    is_substantive_signal,
    is_task_request,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hola", True),
        ("buenos días, ¿cómo estás?", True),
        ("ok", True),
        ("hola, me gusta mucho programar y diseñar videojuegos en mi tiempo libre", False),
        ("Me gusta programar videojuegos", False),
        ("", False),
        ("   ", False),
    ],
)
def test_is_greeting(text: str, expected: bool) -> None:
    assert is_greeting(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("sí", True),
        ("Dale", True),
        ("quiero ver mis resultados", True),
        ("muéstrame los resultados", True),
        ("verlos", True),
        ("no", False),
        ("me gusta la química", False),
        ("", False),
    ],
)
def test_is_acceptance(text: str, expected: bool) -> None:
    assert is_acceptance(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("no", True),
        ("No gracias", True),
        ("todavía no", True),
        ("prefiero seguir conversando", True),
        ("no me gusta la química", False),
        ("sí", False),
        ("", False),
    ],
)
def test_is_negative(text: str, expected: bool) -> None:
    assert is_negative(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("¿Puedes ayudarme?", True),
        ("explícame esto", True),
        ("me gusta el arte", False),
        ("", False),
    ],
)
def test_is_task_request(text: str, expected: bool) -> None:
    assert is_task_request(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("me gusta el arte", True),
        ("pintar", True),
        ("no me gusta la química", True),
        ("arte", False),
        ("hola", False),
        ("sí", False),
        ("xyzabc", False),
        ("", False),
    ],
)
def test_is_substantive_signal(text: str, expected: bool) -> None:
    assert is_substantive_signal(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("me gusta programar", 2),
        ("no me gusta la química", 2),
        ("pintar", 1),
        ("Me encanta programar, diseñar y analizar datos con matemáticas", 4),
        ("xyzabc", 0),
        ("hola", 0),
        ("quiero ver mis resultados", 0),
        ("", 0),
    ],
)
def test_count_signals(text: str, expected: int) -> None:
    assert count_signals(text) == expected

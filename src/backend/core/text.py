from collections.abc import Sequence

ACCENT_TRANSLATION = str.maketrans("áéíóú", "aeiou")


def normalize_text(text: str) -> str:
    # Debe coincidir con la normalización usada al entrenar el pipeline v8: solo se
    # quitan tildes de vocales (la ñ y la ü se conservan).
    return text.strip().lower().translate(ACCENT_TRANSLATION)


def join_words(items: Sequence[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} y {items[-1]}"

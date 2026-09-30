ACCENT_TRANSLATION = str.maketrans("áéíóú", "aeiou")


def normalize_text(text: str) -> str:
    # Debe coincidir con la normalización usada al entrenar el pipeline v8: solo se
    # quitan tildes de vocales (la ñ y la ü se conservan).
    return text.strip().lower().translate(ACCENT_TRANSLATION)

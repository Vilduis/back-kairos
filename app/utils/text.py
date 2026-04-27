def normalize_text(s: str) -> str:
    """Normaliza texto: minúsculas, sin tildes, espacios colapsados."""
    t = (s or "").strip().lower()
    return (
        t.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )

def chunk_text(text: str, size: int = 40):
    """Itera o texto em pedaços de até `size` chars."""
    if not text:
        return
    for i in range(0, len(text), size):
        yield text[i:i + size]

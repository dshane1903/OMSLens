def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    if not text.strip():
        return []

    chunks: list[str] = []
    start = 0
    step = max(chunk_size - overlap, 1)

    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += step

    return [chunk for chunk in chunks if chunk]


def normalize_text(text: str) -> str:
    return " ".join(text.replace("\x00", " ").split())

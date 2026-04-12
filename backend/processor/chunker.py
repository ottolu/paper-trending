from __future__ import annotations


def chunk_text(
    text: str,
    max_chars: int = 4000,
    overlap_chars: int = 200,
    return_with_metadata: bool = False,
) -> list[str] | list[dict]:
    if not text.strip():
        return []

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current)
            if overlap_chars > 0 and len(current) > overlap_chars:
                tail = current[-overlap_chars:]
                candidate = tail + "\n\n" + para
                if len(candidate) > max_chars:
                    current = para
                else:
                    current = candidate
            else:
                current = para
        else:
            current = current + "\n\n" + para if current else para

    if current:
        chunks.append(current)

    if return_with_metadata:
        return [{"text": c, "index": i, "char_count": len(c)} for i, c in enumerate(chunks)]
    return chunks

"""
Document chunker for Knowledge Base retrieval.
Splits text into overlapping chunks along natural paragraph/sentence boundaries.
"""
from typing import Dict, List

KB_CATEGORIES: List[str] = [
    "Programming",
    "Python",
    "Java",
    "SQL",
    "Data Structures and Algorithms",
    "Cybersecurity",
    "Application Security",
    "OWASP",
    "API Security",
    "SAP Security",
    "Oracle Fusion HCM",
    "OTBI",
    "BI Publisher",
    "Projects",
    "System Design",
    "HR Interview Preparation",
    "Custom Topics",
]


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 80,
) -> List[Dict[str, object]]:
    """Split text into overlapping character-bounded chunks preserving offsets."""
    cleaned = text.strip()
    if not cleaned:
        return []

    if len(cleaned) <= chunk_size:
        return [{"chunk_index": 0, "text": cleaned, "start_char": 0, "end_char": len(cleaned)}]

    chunks: List[Dict[str, object]] = []
    start = 0
    idx = 0
    text_len = len(cleaned)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            # Prefer breaking on newline or sentence end within the last 30% of the chunk
            search_from = start + int(chunk_size * 0.7)
            best_break = -1
            for sep in ("\n\n", "\n", ". ", "? ", "! ", " "):
                pos = cleaned.rfind(sep, search_from, end)
                if pos != -1:
                    best_break = pos + len(sep)
                    break
            if best_break > start:
                end = best_break

        chunk_str = cleaned[start:end].strip()
        if chunk_str:
            chunks.append(
                {
                    "chunk_index": idx,
                    "text": chunk_str,
                    "start_char": start,
                    "end_char": end,
                }
            )
            idx += 1

        if end >= text_len:
            break
        start = max(end - overlap, start + 1)

    return chunks

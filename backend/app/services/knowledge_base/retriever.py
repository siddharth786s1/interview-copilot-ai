"""
BM25 keyword retriever for the Personal Knowledge Base using rank-bm25.
"""
import json
import re
from typing import Dict, List, Optional

from rank_bm25 import BM25Okapi
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.knowledge_base import KBDocument

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "to", "of",
    "and", "or", "in", "on", "at", "for", "with", "by", "as", "it", "this",
    "that", "what", "how", "why", "when", "where", "which", "can", "could",
    "would", "should", "do", "does", "did", "you", "your", "me", "my", "explain",
    "tell", "about", "between", "difference",
}


def tokenize_for_bm25(text: str) -> List[str]:
    raw_tokens = re.findall(r"[a-z0-9_+#.-]+", text.lower())
    filtered = [t.strip(".-") for t in raw_tokens if len(t.strip(".-")) > 1 and t.strip(".-") not in _STOPWORDS]
    return filtered if filtered else [t.strip(".-") for t in raw_tokens if t.strip(".-")]


def retrieve_from_chunks(
    query: str,
    corpus_items: List[Dict[str, str]],
    top_k: int = 3,
) -> List[Dict[str, object]]:
    """
    Rank chunk dictionaries via BM25Okapi and return the top_k non-zero matches.

    Each item in corpus_items should have:
      {"document_id": str, "filename": str, "category": str, "text": str}
    """
    if not query.strip() or not corpus_items:
        return []

    query_tokens = tokenize_for_bm25(query)
    if not query_tokens:
        return []

    # Include category + filename keywords alongside chunk text so category-matched docs rank well
    tokenized_docs = [
        tokenize_for_bm25(f"{item.get('category', '')} {item.get('filename', '')} {item.get('text', '')}")
        for item in corpus_items
    ]
    bm25 = BM25Okapi(tokenized_docs)
    scores = bm25.get_scores(query_tokens)

    # Also compute direct keyword overlap fallback for very small corpora (1-2 docs where IDF can be 0 in standard BM25)
    q_set = set(query_tokens)
    scored: List[tuple[float, Dict[str, str]]] = []
    for idx, item in enumerate(corpus_items):
        bm25_score = float(scores[idx])
        doc_tokens = set(tokenized_docs[idx])
        overlap_count = len(q_set & doc_tokens)
        if overlap_count == 0:
            continue
        # Combine BM25 score with small overlap tie-breaker so single-doc corpora still retrieve matches
        combined_score = max(bm25_score, 0.0) + (overlap_count / max(len(q_set), 1)) * 0.5
        scored.append((combined_score, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)

    results: List[Dict[str, object]] = []
    for score, item in scored[:top_k]:
        results.append(
            {
                "document_id": item.get("document_id", ""),
                "filename": item.get("filename", ""),
                "category": item.get("category", "Custom Topics"),
                "excerpt": item.get("text", ""),
                "score": round(score, 4),
            }
        )
    return results


async def retrieve_from_db(
    db: AsyncSession,
    query: str,
    top_k: int = 3,
    category: Optional[str] = None,
) -> List[Dict[str, object]]:
    """Load active KB chunks from SQLite and return top-K BM25-ranked excerpts."""
    stmt = select(KBDocument).where(KBDocument.is_active == True)  # noqa: E712
    if category and category.lower() != "all":
        stmt = stmt.where(KBDocument.category == category)

    res = await db.execute(stmt)
    docs = res.scalars().all()
    if not docs:
        return []

    corpus_items: List[Dict[str, str]] = []
    for doc in docs:
        chunks = []
        if doc.chunks:
            try:
                chunks = json.loads(doc.chunks)
            except Exception:
                chunks = []
        if not chunks and doc.extracted_text:
            chunks = [{"text": doc.extracted_text[:500]}]
        for ch in chunks:
            txt = str(ch.get("text", "")).strip()
            if txt:
                corpus_items.append(
                    {
                        "document_id": doc.id,
                        "filename": doc.filename,
                        "category": doc.category,
                        "text": txt,
                    }
                )

    return retrieve_from_chunks(query=query, corpus_items=corpus_items, top_k=top_k)

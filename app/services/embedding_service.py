import io
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import httpx
from pypdf import PdfReader
from openai import AsyncOpenAI

from app.database.database import get_db, settings


KB_COLLECTION = "knowledge_bases"
CHUNK_COLLECTION = "rag_chunks"


def _utcnow():
    return datetime.now(timezone.utc)


def _make_kb_id() -> str:
    return f"KB-{uuid.uuid4().hex[:12].upper()}"


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    if chunk_size <= 0:
        return []
    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == length:
            break
        start = max(0, end - chunk_overlap)
    return chunks


async def _download_pdf(url: str) -> bytes:
    timeout = httpx.Timeout(60.0, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages_text = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:
            pages_text.append("")
    return _normalize_text(" ".join(pages_text))


async def _embed_texts(texts: List[str]) -> List[List[float]]:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured in .env")
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    model = settings.EMBEDDING_MODEL or "text-embedding-3-small"

    # OpenAI embeddings API supports batching
    embeddings: List[List[float]] = []
    batch_size = 64
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = await client.embeddings.create(
            model=model,
            input=batch,
        )
        embeddings.extend([item.embedding for item in response.data])
    return embeddings


async def create_knowledge_base(
    name: Optional[str],
    source_url: str,
    chunk_size: int,
    chunk_overlap: int,
    metadata: Optional[dict],
) -> Tuple[dict, int]:
    db = get_db()
    kb_id = _make_kb_id()
    now = _utcnow()

    kb_doc = {
        "kb_id": kb_id,
        "name": name,
        "source_url": source_url,
        "status": "processing",
        "chunk_count": 0,
        "embedding_model": settings.EMBEDDING_MODEL or "text-embedding-3-small",
        "created_at": now,
        "updated_at": now,
        "metadata": metadata,
        "last_error": None,
    }

    await db[KB_COLLECTION].insert_one(kb_doc)

    try:
        pdf_bytes = await _download_pdf(source_url)
        text = _extract_pdf_text(pdf_bytes)
        chunks = _chunk_text(text, chunk_size, chunk_overlap)
        if not chunks:
            raise RuntimeError("No text extracted from PDF.")

        embeddings = await _embed_texts(chunks)

        chunk_docs = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings), start=1):
            chunk_docs.append(
                {
                    "kb_id": kb_id,
                    "source_url": source_url,
                    "chunk_index": idx,
                    "text": chunk,
                    "embedding": embedding,
                    "created_at": now,
                }
            )

        if chunk_docs:
            await db[CHUNK_COLLECTION].insert_many(chunk_docs)

        await db[KB_COLLECTION].update_one(
            {"kb_id": kb_id},
            {"$set": {"status": "ready", "chunk_count": len(chunk_docs), "updated_at": _utcnow()}},
        )

        kb_doc["status"] = "ready"
        kb_doc["chunk_count"] = len(chunk_docs)
        kb_doc["updated_at"] = _utcnow()

        return kb_doc, len(chunk_docs)

    except Exception as e:
        await db[KB_COLLECTION].update_one(
            {"kb_id": kb_id},
            {"$set": {"status": "failed", "last_error": str(e), "updated_at": _utcnow()}},
        )
        raise


async def rebuild_knowledge_base(
    kb_id: str,
    name: Optional[str] = None,
    source_url: Optional[str] = None,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    metadata: Optional[dict] = None,
    regenerate: bool = True,
) -> dict:
    db = get_db()
    kb = await db[KB_COLLECTION].find_one({"kb_id": kb_id}, {"_id": 0})
    if not kb:
        return {}

    new_name = name if name is not None else kb.get("name")
    new_source_url = source_url if source_url is not None else kb.get("source_url")
    new_metadata = metadata if metadata is not None else kb.get("metadata")

    update_doc = {
        "name": new_name,
        "source_url": new_source_url,
        "metadata": new_metadata,
        "updated_at": _utcnow(),
    }

    if regenerate:
        # Remove old chunks and rebuild
        await db[CHUNK_COLLECTION].delete_many({"kb_id": kb_id})
        await db[KB_COLLECTION].update_one(
            {"kb_id": kb_id},
            {"$set": {"status": "processing", "chunk_count": 0, "last_error": None}},
        )

        pdf_bytes = await _download_pdf(new_source_url)
        text = _extract_pdf_text(pdf_bytes)
        c_size = chunk_size or 1000
        c_overlap = chunk_overlap or 200
        chunks = _chunk_text(text, c_size, c_overlap)
        if not chunks:
            raise RuntimeError("No text extracted from PDF.")

        embeddings = await _embed_texts(chunks)
        now = _utcnow()
        chunk_docs = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings), start=1):
            chunk_docs.append(
                {
                    "kb_id": kb_id,
                    "source_url": new_source_url,
                    "chunk_index": idx,
                    "text": chunk,
                    "embedding": embedding,
                    "created_at": now,
                }
            )

        if chunk_docs:
            await db[CHUNK_COLLECTION].insert_many(chunk_docs)

        update_doc.update(
            {
                "status": "ready",
                "chunk_count": len(chunk_docs),
                "embedding_model": settings.EMBEDDING_MODEL or "text-embedding-3-small",
                "last_error": None,
            }
        )

    await db[KB_COLLECTION].update_one({"kb_id": kb_id}, {"$set": update_doc})

    kb = await db[KB_COLLECTION].find_one({"kb_id": kb_id}, {"_id": 0})
    return kb or {}


async def delete_knowledge_base(kb_id: str) -> bool:
    db = get_db()
    await db[CHUNK_COLLECTION].delete_many({"kb_id": kb_id})
    result = await db[KB_COLLECTION].delete_one({"kb_id": kb_id})
    return result.deleted_count > 0


async def get_knowledge_base(kb_id: str) -> Optional[dict]:
    db = get_db()
    return await db[KB_COLLECTION].find_one({"kb_id": kb_id}, {"_id": 0})


async def list_knowledge_bases(limit: int = 100) -> List[dict]:
    db = get_db()
    cursor = db[KB_COLLECTION].find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def resolve_kb_ids(knowledge_bases: Optional[List[str]]) -> List[str]:
    """
    Accepts a mix of KB IDs or PDF URLs. Returns matching kb_id list.
    """
    if not knowledge_bases:
        return []
    db = get_db()
    kb_ids = []
    for item in knowledge_bases:
        if item.upper().startswith("KB-"):
            kb_ids.append(item)
        else:
            kb = await db[KB_COLLECTION].find_one({"source_url": item}, {"kb_id": 1, "_id": 0})
            if kb and kb.get("kb_id"):
                kb_ids.append(kb["kb_id"])
    # de-duplicate while preserving order
    seen = set()
    result = []
    for k in kb_ids:
        if k not in seen:
            seen.add(k)
            result.append(k)
    return result


async def retrieve_context(
    query: str,
    knowledge_bases: Optional[List[str]],
    top_k: int = 6,
    max_chars: int = 4000,
) -> str:
    """
    Vector search over rag_chunks filtered by kb_id. Returns a concatenated context string.
    Requires Atlas Vector Search index on rag_chunks.embedding.
    """
    kb_ids = await resolve_kb_ids(knowledge_bases)
    if not kb_ids:
        return ""

    if not settings.OPENAI_API_KEY:
        return ""

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    model = settings.EMBEDDING_MODEL or "text-embedding-3-small"
    index_name = settings.VECTOR_INDEX_NAME or "rag_chunks_embedding_idx"

    embedding_resp = await client.embeddings.create(
        model=model,
        input=[query],
    )
    query_vector = embedding_resp.data[0].embedding

    db = get_db()
    pipeline = [
        {
            "$vectorSearch": {
                "index": index_name,
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": max(50, top_k * 5),
                "limit": top_k,
                "filter": {"kb_id": {"$in": kb_ids}},
            }
        },
        {
            "$project": {
                "_id": 0,
                "text": 1,
                "source_url": 1,
                "chunk_index": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    results = await db[CHUNK_COLLECTION].aggregate(pipeline).to_list(length=top_k)
    if not results:
        return ""

    parts = []
    total = 0
    for r in results:
        snippet = f"Source: {r.get('source_url')} | Chunk: {r.get('chunk_index')}\n{r.get('text')}\n"
        if total + len(snippet) > max_chars:
            break
        parts.append(snippet)
        total += len(snippet)

    return "\n".join(parts).strip()

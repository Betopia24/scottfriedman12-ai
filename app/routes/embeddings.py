from fastapi import APIRouter, HTTPException, status

from app.schemas.embedding_schemas import (
    KnowledgeBaseCreateInput,
    KnowledgeBaseUpdateInput,
    KnowledgeBaseResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseData,
)
from app.services.embedding_service import (
    create_knowledge_base,
    rebuild_knowledge_base,
    delete_knowledge_base,
    get_knowledge_base,
    list_knowledge_bases,
)

router = APIRouter(
    prefix="/knowledge-bases",
    tags=["Knowledge Bases"],
)


@router.post(
    "",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create embeddings for a PDF and store in vector collection",
)
async def create_kb(payload: KnowledgeBaseCreateInput):
    try:
        kb_doc, _ = await create_knowledge_base(
            name=payload.name,
            source_url=str(payload.source_url),
            chunk_size=payload.chunk_size,
            chunk_overlap=payload.chunk_overlap,
            metadata=payload.metadata,
        )
        return KnowledgeBaseResponse(
            success=True,
            message="Knowledge base created and embeddings stored successfully.",
            data=KnowledgeBaseData(**kb_doc),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create knowledge base: {str(e)}",
        )


@router.get(
    "",
    response_model=KnowledgeBaseListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all knowledge bases",
)
async def list_kb(limit: int = 100):
    items = await list_knowledge_bases(limit=limit)
    return KnowledgeBaseListResponse(
        success=True,
        total=len(items),
        data=[KnowledgeBaseData(**item) for item in items],
    )


@router.get(
    "/{kb_id}",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a knowledge base by ID",
)
async def get_kb(kb_id: str):
    kb = await get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge base '{kb_id}' not found.",
        )
    return KnowledgeBaseResponse(
        success=True,
        message="Knowledge base retrieved successfully.",
        data=KnowledgeBaseData(**kb),
    )


@router.put(
    "/{kb_id}",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Update or rebuild embeddings for a knowledge base",
)
async def update_kb(kb_id: str, payload: KnowledgeBaseUpdateInput):
    kb = await rebuild_knowledge_base(
        kb_id=kb_id,
        name=payload.name,
        source_url=str(payload.source_url) if payload.source_url else None,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
        metadata=payload.metadata,
        regenerate=payload.regenerate,
    )
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge base '{kb_id}' not found.",
        )
    return KnowledgeBaseResponse(
        success=True,
        message="Knowledge base updated successfully.",
        data=KnowledgeBaseData(**kb),
    )


@router.delete(
    "/{kb_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a knowledge base and its embeddings",
)
async def delete_kb(kb_id: str):
    deleted = await delete_knowledge_base(kb_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge base '{kb_id}' not found.",
        )
    return {"success": True, "message": f"Knowledge base '{kb_id}' deleted successfully."}

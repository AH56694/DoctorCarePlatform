import base64
import os
import tempfile
from typing import Any

from fastapi import APIRouter, HTTPException, status
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field

from core.mysql_client import mysql_client
from core.parser import DocumentParser
from core.vector_store import vector_store

router = APIRouter()


class KnowledgeIngestRequest(BaseModel):
    doc_id: int = Field(gt=0)
    title: str = Field(default="", max_length=255)
    collection: str = Field(default="medical.symptom_inquiry", max_length=128)
    category: str = Field(default="medical", max_length=64)
    subcategory: str = Field(default="symptom_inquiry", max_length=64)
    content: str = ""
    file_name: str = Field(default="", max_length=255)
    file_type: str = Field(default="", max_length=120)
    file_content_base64: str = ""
    source: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeIngestResponse(BaseModel):
    status: str
    doc_id: int
    chunks_count: int


def _metadata(payload: KnowledgeIngestRequest) -> dict[str, Any]:
    return {
        **payload.metadata,
        "doc_id": payload.doc_id,
        "title": payload.title,
        "collection": payload.collection,
        "category": payload.category,
        "subcategory": payload.subcategory,
        "source": payload.source or payload.file_name or payload.title,
        "file_name": payload.file_name,
        "file_type": payload.file_type,
    }


def _split_text(payload: KnowledgeIngestRequest) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=100,
        separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " ", ""],
    )
    document = Document(page_content=payload.content, metadata=_metadata(payload))
    chunks = splitter.split_documents([document])
    for index, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = index
        chunk.metadata["total_chunks"] = len(chunks)
    return chunks


def _parse_uploaded_file(payload: KnowledgeIngestRequest) -> list[Document]:
    suffix = os.path.splitext(payload.file_name or "")[1] or ".txt"
    temp_path = ""
    try:
        try:
            file_bytes = base64.b64decode(payload.file_content_base64, validate=True)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件内容不是有效的 Base64。") from exc

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(file_bytes)
            temp_path = temp_file.name

        chunks = DocumentParser().parse(temp_path)
        metadata = _metadata(payload)
        for index, chunk in enumerate(chunks):
            chunk.metadata.update(metadata)
            chunk.metadata["chunk_index"] = chunk.metadata.get("chunk_index", index)
            chunk.metadata["total_chunks"] = len(chunks)
        return chunks
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


@router.post("/knowledge/ingest", response_model=KnowledgeIngestResponse)
async def ingest_knowledge(payload: KnowledgeIngestRequest) -> KnowledgeIngestResponse:
    if payload.file_content_base64:
        chunks = _parse_uploaded_file(payload)
    elif payload.content.strip():
        chunks = _split_text(payload)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请提供知识文本或上传文件。")

    if not chunks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未解析到可入库的知识内容。")

    vector_store.delete_document(payload.doc_id)
    vector_store.add_documents(chunks)

    try:
        mysql_client.insert_chunks(
            payload.doc_id,
            [
                {"page_content": chunk.page_content, "chunk_index": chunk.metadata.get("chunk_index", index)}
                for index, chunk in enumerate(chunks)
            ],
        )
    except Exception:
        # MySQL is optional for the RAG service; vector storage is the source used by QA.
        pass

    return KnowledgeIngestResponse(status="success", doc_id=payload.doc_id, chunks_count=len(chunks))


@router.delete("/knowledge/{doc_id}")
async def delete_knowledge(doc_id: int) -> dict[str, Any]:
    if doc_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="doc_id 必须为正整数。")
    vector_store.delete_document(doc_id)
    try:
        mysql_client.execute("DELETE FROM knowledge_chunk WHERE doc_id = %s", (doc_id,))
    except Exception:
        pass
    return {"status": "success", "doc_id": doc_id}

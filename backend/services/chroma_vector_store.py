import hashlib
from pathlib import Path
from typing import Any, Dict, List

import chromadb
from chromadb.config import Settings as ChromaSettings

from config import settings


class ChromaVectorStore:
    def __init__(self):
        self.storage_dir = Path(settings.CHROMA_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.storage_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION
        )
        self.dimension = settings.CHROMA_EMBEDDING_DIMENSION
        print(f"ChromaVectorStore: 使用持久化目录 {self.storage_dir}")

    def _embedding_for_text(self, text: str) -> List[float]:
        digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
        values: List[float] = []
        while len(values) < self.dimension:
            for b in digest:
                values.append((b / 127.5) - 1.0)
                if len(values) >= self.dimension:
                    break
        return values

    def _embeddings_for_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._embedding_for_text(t) for t in texts]

    def add_chunks(self, user_id: int, document_id: int, chunks: List[str], filename: str) -> None:
        if not chunks:
            return

        ids = [f"u{user_id}_d{document_id}_c{i}" for i in range(len(chunks))]
        embeddings = self._embeddings_for_texts(chunks)
        metadatas = [
            {
                "user_id": user_id,
                "document_id": str(document_id),
                "filename": filename,
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]

        self.collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search(self, user_id: int, query: str, n_results: int = 5, document_ids: List[int] = None) -> List[Dict[str, Any]]:
        if not query.strip():
            return []

        where: Dict[str, Any] = {"user_id": user_id}
        if document_ids:
            where = {
                "$and": [
                    {"user_id": user_id},
                    {"document_id": {"$in": [str(i) for i in document_ids]}},
                ]
            }

        query_embedding = self._embedding_for_text(query)
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas"],
        )

        docs = result.get("documents", [[]])
        metas = result.get("metadatas", [[]])
        if not docs or not metas:
            return []

        rows = []
        for content, meta in zip(docs[0], metas[0]):
            rows.append(
                {
                    "content": content,
                    "filename": meta.get("filename", ""),
                    "document_id": str(meta.get("document_id", "")),
                }
            )
        return rows

    def delete_document(self, user_id: int, document_id: int) -> None:
        self.collection.delete(
            where={
                "$and": [
                    {"user_id": user_id},
                    {"document_id": str(document_id)},
                ]
            }
        )


chroma_vector_store = ChromaVectorStore()

import faiss
import numpy as np
import pickle
import os
from typing import List, Dict, Any
from config import settings
from pathlib import Path
from services.aliyun_embedding import AliyunEmbeddingFunction


class FAISSVectorStore:
    def __init__(self):
        # 使用阿里云百炼嵌入模型
        try:
            if settings.DASHSCOPE_API_KEY and settings.EMBEDDING_BASE_URL:
                self.embedding_func = AliyunEmbeddingFunction()
                self.dimension = 1024  # text-embedding-v4 的维度
                print("FAISS: 使用阿里云百炼嵌入模型")
            else:
                # 如果没有配置阿里云，使用简单的模拟嵌入
                self.embedding_func = None
                self.dimension = 384
                print("FAISS: 使用模拟嵌入模型")
        except Exception as e:
            print(f"FAISS: 阿里云模型初始化失败，使用模拟模型: {e}")
            self.embedding_func = None
            self.dimension = 384
        self.index_map = {}  # user_id -> faiss_index
        self.data_map = {}   # user_id -> list of documents
        self.storage_dir = Path("faiss_storage")
        self.storage_dir.mkdir(exist_ok=True)
        self._load_all_indices()

    def _get_user_storage_path(self, user_id: int) -> tuple:
        """获取用户存储路径"""
        index_path = self.storage_dir / f"user_{user_id}_index.faiss"
        data_path = self.storage_dir / f"user_{user_id}_data.pkl"
        return index_path, data_path

    def _load_all_indices(self):
        """加载所有用户的索引"""
        for file_path in self.storage_dir.glob("*_index.faiss"):
            try:
                user_id = int(file_path.stem.split('_')[1])
                self._load_user_index(user_id)
            except Exception as e:
                print(f"加载用户索引失败 {file_path}: {e}")

    def _load_user_index(self, user_id: int):
        """加载单个用户的索引"""
        index_path, data_path = self._get_user_storage_path(user_id)

        if index_path.exists() and data_path.exists():
            try:
                # 加载FAISS索引
                index = faiss.read_index(str(index_path))
                self.index_map[user_id] = index

                # 加载文档数据
                with open(data_path, 'rb') as f:
                    self.data_map[user_id] = pickle.load(f)

                print(f"已加载用户 {user_id} 的FAISS索引，包含 {index.ntotal} 个向量")
            except Exception as e:
                print(f"加载用户 {user_id} 索引失败: {e}")

    def _save_user_index(self, user_id: int):
        """保存用户索引"""
        if user_id not in self.index_map or user_id not in self.data_map:
            return

        index_path, data_path = self._get_user_storage_path(user_id)

        try:
            # 保存FAISS索引
            faiss.write_index(self.index_map[user_id], str(index_path))

            # 保存文档数据
            with open(data_path, 'wb') as f:
                pickle.dump(self.data_map[user_id], f)
        except Exception as e:
            print(f"保存用户 {user_id} 索引失败: {e}")

    def _get_or_create_index(self, user_id: int):
        """获取或创建用户的FAISS索引"""
        if user_id not in self.index_map:
            # 创建新的FAISS索引
            index = faiss.IndexFlatL2(self.dimension)  # L2距离索引
            self.index_map[user_id] = index
            self.data_map[user_id] = []
        return self.index_map[user_id]

    def add_chunks(self, user_id: int, document_id: int, chunks: List[str], filename: str) -> None:
        """添加文档块到向量存储"""
        if not chunks:
            return

        index = self._get_or_create_index(user_id)
        documents = self.data_map[user_id]

        # 生成嵌入向量
        if self.embedding_func:
            # 使用阿里云嵌入模型
            embeddings_list = self.embedding_func(chunks)
            embeddings = np.array(embeddings_list, dtype=np.float32)
        else:
            # 使用简单的模拟嵌入（用于测试）
            np.random.seed(42)  # 固定种子以便重现
            embeddings = np.random.rand(len(chunks), self.dimension).astype(np.float32)

        # 添加到FAISS索引
        index.add(embeddings)

        # 保存文档元数据
        for i, chunk in enumerate(chunks):
            doc_data = {
                "id": f"doc_{document_id}_chunk_{i}",
                "content": chunk,
                "filename": filename,
                "document_id": str(document_id),
                "chunk_index": i,
                "embedding_index": len(documents)
            }
            documents.append(doc_data)

        # 保存到磁盘
        self._save_user_index(user_id)
        print(f"用户 {user_id} 添加 {len(chunks)} 个文档块，总计 {index.ntotal} 个向量")

    def search(self, user_id: int, query: str, n_results: int = 5, document_ids: List[int] = None) -> List[Dict[str, Any]]:
        """搜索相似文档"""
        if user_id not in self.index_map or user_id not in self.data_map:
            return []

        index = self.index_map[user_id]
        documents = self.data_map[user_id]

        if document_ids:
            selected = {str(i) for i in document_ids}
            documents = [d for d in documents if d["document_id"] in selected]

        if index.ntotal == 0 or not documents:
            return []

        # 生成查询嵌入
        if self.embedding_func:
            query_embeddings = self.embedding_func([query])
            query_embedding = np.array(query_embeddings[0], dtype=np.float32)
            query_vector = query_embedding
            doc_vectors = []
            for doc in documents:
                emb = self.embedding_func([doc["content"]])[0]
                doc_vectors.append(np.array(emb, dtype=np.float32))
        else:
            np.random.seed(hash(query) % 1000)
            query_vector = np.random.rand(self.dimension).astype(np.float32)
            doc_vectors = []
            for doc in documents:
                np.random.seed(hash(doc["content"]) % 1000)
                doc_vectors.append(np.random.rand(self.dimension).astype(np.float32))

        # 计算距离并排序
        scored = []
        for i, (doc, vec) in enumerate(zip(documents, doc_vectors)):
            dist = float(np.linalg.norm(query_vector - vec))
            scored.append((dist, i, doc))
        scored.sort(key=lambda x: x[0])

        results = []
        for dist, _, doc in scored[:n_results]:
            row = doc.copy()
            row["distance"] = dist
            results.append({
                "content": row["content"],
                "filename": row["filename"],
                "document_id": row["document_id"]
            })

        return results

    def delete_document(self, user_id: int, document_id: int) -> None:
        """删除文档"""
        if user_id not in self.data_map:
            return

        documents = self.data_map[user_id]

        # 过滤出要删除的文档
        docs_to_keep = [doc for doc in documents if doc["document_id"] != str(document_id)]
        docs_to_delete_count = len(documents) - len(docs_to_keep)

        if docs_to_delete_count == 0:
            return

        # 重新构建索引
        self.data_map[user_id] = docs_to_keep

        # 创建新索引
        new_index = faiss.IndexFlatL2(self.dimension)

        # 如果有剩余的文档，重新添加
        if docs_to_keep:
            # 重新生成所有嵌入
            chunks = [doc["content"] for doc in docs_to_keep]
            if self.embedding_func:
                # 使用阿里云嵌入模型
                embeddings_list = self.embedding_func(chunks)
                embeddings = np.array(embeddings_list, dtype=np.float32)
            else:
                # 使用简单的模拟嵌入
                np.random.seed(42)
                embeddings = np.random.rand(len(chunks), self.dimension).astype(np.float32)
            new_index.add(embeddings)

            # 更新嵌入索引
            for i, doc in enumerate(docs_to_keep):
                doc["embedding_index"] = i

        self.index_map[user_id] = new_index
        self._save_user_index(user_id)

        print(f"用户 {user_id} 删除文档 {document_id}，移除了 {docs_to_delete_count} 个向量")


# 全局实例
faiss_vector_store = FAISSVectorStore()
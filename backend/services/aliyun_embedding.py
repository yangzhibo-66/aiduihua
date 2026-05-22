import requests
import json
from typing import List, Optional
from config import settings


class AliyunEmbeddingFunction:
    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY
        self.base_url = settings.EMBEDDING_BASE_URL
        self.model = settings.EMBEDDING_MODEL

        if not self.api_key or not self.base_url:
            raise ValueError("阿里云百炼 API 配置不完整")

    def __call__(self, input: List[str]) -> List[List[float]]:
        """为文本列表生成嵌入向量"""
        if isinstance(input, str):
            input = [input]

        embeddings = []
        for text in input:
            embedding = self._get_single_embedding(text)
            embeddings.append(embedding)

        return embeddings

    def _get_single_embedding(self, text: str) -> List[float]:
        """获取单个文本的嵌入向量"""
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "input": text
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()

            result = response.json()
            if "data" in result and len(result["data"]) > 0:
                return result["data"][0]["embedding"]
            else:
                raise ValueError(f"API 响应格式错误: {result}")

        except Exception as e:
            print(f"获取嵌入向量失败: {e}")
            raise

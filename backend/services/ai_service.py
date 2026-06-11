from typing import AsyncIterator, Optional
import requests
import json
from config import settings
import logging

logger = logging.getLogger(__name__)

RAG_SYSTEM_PROMPT = """你是一个专业的 AI 知识库助手，基于用户上传的文档回答问题。

规则：
1. 仅根据「参考文档」中的内容回答，不要杜撰文档中没有的信息。
2. 如果文档中没有相关内容，请诚实告知用户，并说明原因。
3. 使用 Markdown 格式让回答更易读（标题、加粗、列表、代码块等）。
4. 默认使用中文回答，除非用户明确用英文提问。
5. 引用文档原文时可使用 > 引用格式。"""

FREE_SYSTEM_PROMPT = """你是一个专业、可靠的 AI 助手。

规则：
1. 基于你的通用知识与用户提供的信息回答。
2. 不要伪造事实；不确定时请明确说明不确定。
3. 使用 Markdown 格式让回答更易读（标题、加粗、列表、代码块等）。
4. 默认使用中文回答，除非用户明确用英文提问。"""


def _build_context(chunks: list[dict]) -> str:
    if not chunks:
        return "（当前知识库为空，请先上传相关文档或图片）"

    image_exts = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
    parts = []
    for c in chunks:
        name = c.get("filename", "")
        prefix = "图片来源" if name.lower().endswith(image_exts) else "来源"
        parts.append(f"【{prefix}：{name}】\n{c['content']}")
    return "\n\n---\n\n".join(parts)


async def stream_response(
    message: str,
    retrieved_chunks: list[dict],
    history: list[dict],
    chat_mode: str = "free",
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> AsyncIterator[str]:
    """使用阿里云百炼 OpenAI 兼容 API 流式响应"""
    
    # 使用配置或传入的参数
    effective_key = api_key or settings.OPENAI_API_KEY
    effective_model = model or settings.DEFAULT_MODEL
    effective_base_url = base_url or settings.OPENAI_BASE_URL
    
    # 检查配置
    if not effective_key:
        yield "（未配置 API Key，请在设置页面填写或在服务器 .env 文件中设置后重启服务）"
        return
    
    if not effective_base_url:
        yield "（未配置 API Base URL，请在设置页面填写或在服务器 .env 文件中设置）"
        return
    
    if chat_mode == "rag_selected":
        context = _build_context(retrieved_chunks)
        system = f"{RAG_SYSTEM_PROMPT}\n\n参考文档内容：\n{context}"
    else:
        system = FREE_SYSTEM_PROMPT
    
    # 构建消息历史
    openai_messages = [{"role": "system", "content": system}]
    for h in history[-10:]:
        openai_messages.append({"role": h["role"], "content": h["content"]})
    openai_messages.append({"role": "user", "content": message})
    
    try:
        # 直接调用阿里云百炼 API
        url = f"{effective_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {effective_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": effective_model,
            "messages": openai_messages,
            "max_tokens": 2048,
            "temperature": 0.7,
            "stream": True
        }

        logger.info(f"调用阿里云百炼 API: model={effective_model}, base_url={effective_base_url}")

        response = requests.post(url, headers=headers, json=data, stream=True)
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data_str = line[6:]  # 去掉 "data: " 前缀
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(data_str)
                        if chunk_data.get("choices") and len(chunk_data["choices"]) > 0:
                            delta = chunk_data["choices"][0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue
        
        logger.info("流式响应完成")
        
    except Exception as e:
        logger.error(f"阿里云百炼 API 错误: {e}")
        yield f"（AI 服务错误: {str(e)}）"
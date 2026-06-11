import re
from pathlib import Path

from config import settings
from services.image_ocr_service import extract_image_text


def extract_text(file_path: str, file_type: str) -> str:
    """Dispatch to the correct extractor based on file type / extension."""
    fp = Path(file_path)
    ext = fp.suffix.lower()
    mime = (file_type or "").lower()

    if ext in settings.IMAGE_EXTENSIONS or mime.startswith("image/"):
        return extract_image_text(file_path, file_type)
    if "pdf" in mime or ext == ".pdf":
        return _extract_pdf(file_path)
    if "word" in mime or "docx" in mime or ext == ".docx":
        return _extract_docx(file_path)
    return _extract_plain(file_path)


def _extract_pdf(file_path: str) -> str:
    try:
        import pdfplumber
        pages = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n".join(pages)
    except ImportError as e:
        raise ImportError(f"缺少 pdfplumber 库，请运行: pip install pdfplumber. 错误: {e}")
    except Exception as e:
        raise Exception(f"读取 PDF 文档失败: {e}")


def _extract_docx(file_path: str) -> str:
    try:
        from docx import Document
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError as e:
        raise ImportError(f"缺少 python-docx 库，请运行: pip install python-docx. 错误: {e}")
    except Exception as e:
        raise Exception(f"读取 Word 文档失败: {e}")


def _extract_plain(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def split_into_chunks(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping fixed-size chunks."""
    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == length:
            break
        start = end - overlap
    return chunks


def count_words(text: str) -> int:
    """Count words, treating each CJK character as one word."""
    cjk = len(re.findall(r"[一-鿿㐀-䶿]", text))
    latin = len(re.findall(r"\b[a-zA-Z0-9]+\b", text))
    return cjk + latin

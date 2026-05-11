import re
import requests
from typing import Optional

import trafilatura

try:
    from newspaper import Article
    NEWSPAPER_AVAILABLE = True
except ImportError:
    NEWSPAPER_AVAILABLE = False


URL_FETCH_ERROR_PREFIX = "URL_FETCH_ERROR"


def clean_text(text: str) -> str:
    """
    对输入文本做基础清洗：
    - 去掉多余空白
    - 去掉连续换行
    - 去掉常见无意义字符
    """
    if not text:
        return ""

    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[￼﻿]", "", text)
    return text


def truncate_text(text: str, max_length: int) -> str:
    """
    超过最大长度则截断，并保留提示。
    """
    if len(text) <= max_length:
        return text

    return text[:max_length] + "\n\n[文本过长，已截断]"


def _extract_with_trafilatura(url: str) -> Optional[str]:
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None

        extracted = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
            favor_precision=True,
            deduplicate=True,
            output_format="txt",
        )

        if extracted and extracted.strip():
            return extracted.strip()

        return None
    except Exception:
        return None


def _extract_with_trafilatura_from_requests(url: str) -> Optional[str]:
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()

        extracted = trafilatura.extract(
            response.text,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
            favor_precision=True,
            deduplicate=True,
            output_format="txt",
        )

        if extracted and extracted.strip():
            return extracted.strip()

        return None
    except Exception:
        return None


def _extract_with_newspaper(url: str, language: Optional[str] = None) -> Optional[str]:
    if not NEWSPAPER_AVAILABLE:
        return None

    try:
        article = Article(url=url, language=language) if language else Article(url=url)
        article.download()
        article.parse()

        text = article.text.strip() if article.text else ""
        if text:
            return text

        return None
    except Exception:
        return None


def fetch_text_from_url(url: str, language: Optional[str] = None) -> str:
    """
    URL 正文抽取总入口：
    1. trafilatura.fetch_url + extract
    2. requests + trafilatura.extract
    3. newspaper3k 兜底
    """
    text = _extract_with_trafilatura(url)
    if text:
        return clean_text(text)

    text = _extract_with_trafilatura_from_requests(url)
    if text:
        return clean_text(text)

    text = _extract_with_newspaper(url, language=language)
    if text:
        return clean_text(text)

    return f"{URL_FETCH_ERROR_PREFIX}: unable to extract main article text from the given URL"


def merge_text_and_url_content(text: Optional[str], url_text: Optional[str]) -> str:
    parts = []

    if text and text.strip():
        parts.append(text.strip())

    if url_text and url_text.strip() and not url_text.startswith(URL_FETCH_ERROR_PREFIX):
        parts.append(url_text.strip())

    return "\n\n".join(parts)

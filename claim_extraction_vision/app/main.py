import time
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form

from app.config import settings
from app.schemas import ClaimExtractionRequest, ClaimExtractionResponse
from app.services.claim_extractor import ClaimExtractor
from app.services.ocr_service import OCRService
from app.services.vision_llm_service import VisionLLMService
from app.utils import (
    clean_text,
    fetch_text_from_url,
    merge_text_and_url_content,
    truncate_text,
    URL_FETCH_ERROR_PREFIX,
)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
)


def normalize_optional_text(value: str | None, placeholders: set[str]) -> str:
    """
    清洗 Swagger / 表单 / JSON 中的可选字符串字段。
    如果为空，或是默认占位值，则当作空字符串。
    """
    if value is None:
        return ""

    value = str(value).strip()

    if not value:
        return ""

    if value.lower() in placeholders:
        return ""

    return value


def normalize_optional_url(value) -> str:
    """
    清洗可选 URL。
    Swagger 默认的 https://example.com/ 不作为真实输入处理。
    """
    if value is None:
        return ""

    value = str(value).strip()

    if not value:
        return ""

    if value.lower() in {
        "string",
        "url",
        "https://example.com/",
        "http://example.com/",
        "https://example.com",
        "http://example.com",
    }:
        return ""

    return value


def normalize_optional_form_value(value: str | None, placeholders: set[str]) -> str:
    """
    清洗 Swagger 表单里的可选字段。
    如果用户没有填写，或者误提交了 Swagger 默认占位值，则当作空字符串。
    """
    if value is None:
        return ""

    value = str(value).strip()

    if not value:
        return ""

    if value.lower() in placeholders:
        return ""

    return value


claim_extractor = ClaimExtractor()
ocr_service = OCRService()
vision_llm_service = VisionLLMService()


@app.get("/")
def health_check():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "vision_enabled": settings.USE_VISION_LLM,
        "vision_provider": settings.VISION_PROVIDER,
        "vision_model": settings.VISION_MODEL if settings.USE_VISION_LLM else None,
        "local_ocr_enabled": settings.ENABLE_LOCAL_OCR,
    }


@app.post("/extract_claims", response_model=ClaimExtractionResponse)
def extract_claims_api(request: ClaimExtractionRequest):
    """
    文本版 Claim Extraction：
    - text
    - url
    - text + url

    注意：
    会自动过滤 Swagger 默认值 string / text / https://example.com/。
    """
    try:
        total_start = time.time()

        input_text = normalize_optional_text(request.text, {"string", "text"})
        input_url = normalize_optional_url(request.url)
        language = normalize_optional_text(request.language, {"string", "language"}) or "zh"
        source_type = normalize_optional_text(request.source_type, {"string", "source_type"}) or "news"

        url_text = ""

        # 1. URL 正文抽取
        if input_url:
            url_start = time.time()

            url_text = fetch_text_from_url(
                input_url,
                language=language,
            )

            print(f"[URL_FETCH] cost={time.time() - url_start:.2f}s")

            if url_text.startswith(URL_FETCH_ERROR_PREFIX) and not input_text:
                raise HTTPException(
                    status_code=400,
                    detail="URL 正文抽取失败，请直接粘贴新闻正文或社交媒体文本。",
                )

            if url_text.startswith(URL_FETCH_ERROR_PREFIX):
                url_text = ""

        # 2. 合并 text + URL 正文
        raw_input = merge_text_and_url_content(input_text, url_text)

        if not raw_input:
            raise HTTPException(
                status_code=400,
                detail="text 和 url 不能同时为空",
            )

        # 3. 清洗与截断
        cleaned_text = clean_text(raw_input)

        if len(cleaned_text) < settings.MIN_INPUT_LENGTH:
            raise HTTPException(
                status_code=400,
                detail="输入文本太短，无法抽取 claim",
            )

        cleaned_text = truncate_text(cleaned_text, settings.MAX_INPUT_LENGTH)

        # 4. Claim extraction
        extraction_start = time.time()

        claims = claim_extractor.extract_claims(cleaned_text)

        print(f"[CLAIM_EXTRACTION] cost={time.time() - extraction_start:.2f}s")
        print(f"[TOTAL_REQUEST] cost={time.time() - total_start:.2f}s")

        return ClaimExtractionResponse(
            success=True,
            raw_input=raw_input,
            cleaned_text=cleaned_text,
            claims=claims,
            claim_count=len(claims),
            next_module_input={
                "claims": [
                    {
                        "id": c.id,
                        "claim": c.claim,
                        "type": c.type,
                        "confidence": c.confidence,
                    }
                    for c in claims
                ]
            },
            message="Claim extraction completed successfully.",
            mode="text_rumor",
            diagnostics={
                "source_type": source_type,
                "url_text_available": bool(url_text),
                "total_cost_seconds": round(time.time() - total_start, 2),
            },
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"内部错误: {str(e)}",
        )


@app.post("/describe_image")
async def describe_image_api(
    image: UploadFile = File(...),
    language: str = Form(default="zh"),
):
    """
    单独测试视觉大模型图片分析功能。
    只上传图片，不抽取 claim。
    返回 VLM OCR 文本 + 图片描述。
    """
    try:
        language = normalize_optional_form_value(language, {"string", "language"}) or "zh"

        image_bytes = await image.read()

        vision_result = vision_llm_service.analyze_image(
            image_bytes=image_bytes,
            content_type=image.content_type,
            language=language,
        )

        vlm_ocr_text = vision_result.get("ocr_text", "")
        image_description = vision_result.get("image_description", "")

        return {
            "success": True,
            "filename": image.filename,
            "content_type": image.content_type,
            "vision_enabled": settings.USE_VISION_LLM,
            "vision_provider": settings.VISION_PROVIDER,
            "vision_model": settings.VISION_MODEL if settings.USE_VISION_LLM else None,
            "vlm_ocr_text": vlm_ocr_text,
            "image_description": image_description,
            "message": (
                "Image analysis completed."
                if (vlm_ocr_text or image_description)
                else "No image analysis generated. Check USE_VISION_LLM and VISION_API_KEY."
            ),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"图片分析失败: {str(e)}",
        )


@app.post("/extract_claims_multimodal", response_model=ClaimExtractionResponse)
async def extract_claims_multimodal_api(
    text: str = Form(default=""),
    url: str = Form(default=""),
    language: str = Form(default="zh"),
    source_type: str = Form(default="news"),
    image: Optional[UploadFile] = File(default=None),
):
    """
    多模态接口：
    - 只输入 text/url：按文字谣言处理
    - 输入 text/url + image：按图文联合谣言处理
    - 只输入 image：按 image_only 处理

    图片处理策略：
    - 本地 Tesseract OCR 是可选增强；未安装也不会影响系统。
    - 视觉大模型默认同时负责 VLM OCR 和图片描述。

    注意：
    会自动过滤 Swagger 默认值 string / text / url。
    """
    try:
        text = normalize_optional_form_value(text, {"string", "text"})
        url = normalize_optional_url(url)
        language = normalize_optional_form_value(language, {"string", "language"}) or "zh"
        source_type = normalize_optional_form_value(source_type, {"string", "source_type"}) or "news"

        total_start = time.time()

        url_text = ""
        local_ocr_text = ""
        vlm_ocr_text = ""
        ocr_text = ""
        image_description = ""
        image_filename = image.filename if image else None

        # 1. URL 正文抽取
        if url:
            url_start = time.time()

            url_text = fetch_text_from_url(
                url,
                language=language,
            )

            print(f"[URL_FETCH] cost={time.time() - url_start:.2f}s")

            # 多模态接口中，URL 抽取失败时不直接失败；
            # 如果还有 text/image，可以继续。
            if url_text.startswith(URL_FETCH_ERROR_PREFIX):
                if not text and not image:
                    raise HTTPException(
                        status_code=400,
                        detail="URL 正文抽取失败，请直接粘贴新闻正文或上传图片。",
                    )

                url_text = ""

        # 2. 图片 OCR + 视觉大模型分析
        if image:
            image_start = time.time()

            image_bytes = await image.read()

            # 2.1 本地 OCR：可选，不要求组员安装 Tesseract。
            if settings.ENABLE_LOCAL_OCR:
                ocr_lang = "chi_sim+eng" if language == "zh" else "eng"

                local_ocr_text = ocr_service.extract_text_from_image(
                    image_bytes=image_bytes,
                    language=ocr_lang,
                )

            # 2.2 VLM OCR + 图片描述：推荐主路径。
            vision_result = vision_llm_service.analyze_image(
                image_bytes=image_bytes,
                content_type=image.content_type,
                language=language,
            )

            vlm_ocr_text = vision_result.get("ocr_text", "")
            image_description = vision_result.get("image_description", "")

            # 合并 OCR 结果：本地 OCR + VLM OCR 去重拼接。
            ocr_parts = []

            if local_ocr_text and local_ocr_text.strip():
                ocr_parts.append(local_ocr_text.strip())

            if (
                vlm_ocr_text
                and vlm_ocr_text.strip()
                and vlm_ocr_text.strip() not in ocr_parts
            ):
                ocr_parts.append(vlm_ocr_text.strip())

            ocr_text = "\n".join(ocr_parts)

            # 如果没开视觉模型或调用失败，保留弱提示，方便抽取 image_text_relation。
            if not image_description:
                image_description = "用户上传了一张图片，但当前未生成视觉描述。"

            print(f"[IMAGE_PROCESS] cost={time.time() - image_start:.2f}s")

        # 3. 输入校验
        has_text = bool(text and text.strip())
        has_url_text = bool(url_text and url_text.strip())
        has_ocr_text = bool(ocr_text and ocr_text.strip())
        has_image_desc = bool(image_description and image_description.strip())

        if not has_text and not has_url_text and not has_ocr_text and not has_image_desc:
            raise HTTPException(
                status_code=400,
                detail="text、url 和 image 不能同时为空，或图片中未识别到有效内容。",
            )

        # 4. 自动分流
        if image and (has_text or has_url_text):
            processing_mode = "multimodal_rumor"
        elif image:
            processing_mode = "image_only"
        else:
            processing_mode = "text_rumor"

        # 5. 构造 raw_input，便于调试和展示
        raw_input_parts = []

        if has_text:
            raw_input_parts.append(f"[用户输入文字]\n{text.strip()}")

        if has_url_text:
            raw_input_parts.append(f"[URL 正文]\n{url_text}")

        if has_ocr_text:
            raw_input_parts.append(f"[图片 OCR 文本]\n{ocr_text}")

        if has_image_desc:
            raw_input_parts.append(f"[图片视觉描述]\n{image_description}")

        raw_input = "\n\n".join(raw_input_parts)
        cleaned_text = clean_text(raw_input)

        if len(cleaned_text) < settings.MIN_INPUT_LENGTH:
            raise HTTPException(
                status_code=400,
                detail="输入内容太短，无法抽取 claim",
            )

        cleaned_text = truncate_text(cleaned_text, settings.MAX_INPUT_LENGTH)

        # 6. Claim extraction
        extraction_start = time.time()

        if processing_mode == "text_rumor":
            claims = claim_extractor.extract_claims(cleaned_text)
        else:
            claims = claim_extractor.extract_claims_multimodal(
                user_text=text or "",
                url_text=url_text or "",
                ocr_text=ocr_text or "",
                image_description=image_description or "",
                image_filename=image_filename,
            )

        print(f"[CLAIM_EXTRACTION] cost={time.time() - extraction_start:.2f}s")
        print(f"[TOTAL_REQUEST] cost={time.time() - total_start:.2f}s")

        message = f"Claim extraction completed successfully. mode={processing_mode}"

        if processing_mode == "image_only":
            message += "。当前为仅图片输入，若缺少时间、地点或事件背景，建议补充配文以便后续验证。"

        # 7. 返回结果，保持兼容人员 B
        return ClaimExtractionResponse(
            success=True,
            raw_input=raw_input,
            cleaned_text=cleaned_text,
            claims=claims,
            claim_count=len(claims),
            next_module_input={
                "claims": [
                    {
                        "id": c.id,
                        "claim": c.claim,
                        "type": c.type,
                        "confidence": c.confidence,
                        "source_modalities": c.source_modalities,
                        "claim_scope": c.claim_scope,
                    }
                    for c in claims
                ]
            },
            message=message,
            mode=processing_mode,
            diagnostics={
                "source_type": source_type,
                "image_filename": image_filename,
                "url_text_available": has_url_text,
                "local_ocr_text_available": bool(local_ocr_text and local_ocr_text.strip()),
                "vlm_ocr_text_available": bool(vlm_ocr_text and vlm_ocr_text.strip()),
                "ocr_text_available": has_ocr_text,
                "image_description_available": has_image_desc,
                "vision_enabled": settings.USE_VISION_LLM,
                "vision_provider": settings.VISION_PROVIDER,
                "vision_model": settings.VISION_MODEL if settings.USE_VISION_LLM else None,
                "local_ocr_enabled": settings.ENABLE_LOCAL_OCR,
                "total_cost_seconds": round(time.time() - total_start, 2),
            },
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"内部错误: {str(e)}",
        )
import base64
import json
import re
from typing import Any, Dict, Optional

from openai import OpenAI

from app.config import settings


class VisionLLMService:
    def __init__(self):
        self.client = (
            OpenAI(
                api_key=settings.VISION_API_KEY,
                base_url=settings.VISION_BASE_URL,
            )
            if settings.VISION_API_KEY
            else None
        )
        self.model = settings.VISION_MODEL

    def _image_bytes_to_data_url(
        self,
        image_bytes: bytes,
        content_type: Optional[str] = None,
    ) -> str:
        if not content_type:
            content_type = "image/jpeg"

        encoded = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{content_type};base64,{encoded}"

    def _parse_json_from_model_output(self, content: str) -> Dict[str, str]:
        """Parse JSON even if the model accidentally wraps it in Markdown."""
        if not content:
            return {"ocr_text": "", "image_description": ""}

        text = content.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

        try:
            data: Dict[str, Any] = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                return {"ocr_text": "", "image_description": text}
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return {"ocr_text": "", "image_description": text}

        return {
            "ocr_text": str(data.get("ocr_text", "") or "").strip(),
            "image_description": str(data.get("image_description", "") or "").strip(),
        }

    def analyze_image(
        self,
        image_bytes: bytes,
        content_type: Optional[str] = None,
        language: str = "zh",
    ) -> Dict[str, str]:
        """
        Use a vision LLM to do both image OCR and image description.
        This avoids requiring every teammate to install local Tesseract OCR.
        """
        if not settings.USE_VISION_LLM or not self.client:
            return {"ocr_text": "", "image_description": ""}

        image_data_url = self._image_bytes_to_data_url(
            image_bytes=image_bytes,
            content_type=content_type,
        )

        if language == "en":
            prompt = """
Analyze this image for a rumor detection claim extraction system.
Return JSON only, with no Markdown.

Requirements:
1. ocr_text: transcribe clearly visible text in the image. If there is no readable text, return an empty string.
2. image_description: describe the visible scene, people, objects, environment, signs, and possible event context.
3. Do not verify whether any rumor is true.
4. Do not invent time, place, identity, source, cause, or event details if they are not visible.

Output format:
{
  "ocr_text": "...",
  "image_description": "..."
}
"""
        else:
            prompt = """
请为谣言检测系统分析这张图片。
只输出 JSON，不要输出 Markdown、代码块或额外解释。

要求：
1. ocr_text：提取图片中清晰可见的文字。如果没有可读文字，返回空字符串。
2. image_description：描述图片中的可见场景、人物、物体、环境、文字标识、可能的事件背景。
3. 不要判断真假。
4. 如果图片中看不出时间、地点、人物身份、来源、原因或具体事件，不要编造。

输出格式：
{
  "ocr_text": "...",
  "image_description": "..."
}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_data_url,
                                    "detail": settings.VISION_DETAIL,
                                },
                            },
                        ],
                    }
                ],
                temperature=0.1,
                max_tokens=800,
                timeout=settings.REQUEST_TIMEOUT,
            )

            content = response.choices[0].message.content or ""
            return self._parse_json_from_model_output(content)

        except Exception as e:
            print(f"[VISION_LLM_ERROR] {str(e)}")
            return {"ocr_text": "", "image_description": ""}

    def describe_image(
        self,
        image_bytes: bytes,
        content_type: Optional[str] = None,
        language: str = "zh",
    ) -> str:
        """Backward-compatible helper used by older tests or endpoints."""
        result = self.analyze_image(
            image_bytes=image_bytes,
            content_type=content_type,
            language=language,
        )
        return result.get("image_description", "")

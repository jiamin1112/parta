from io import BytesIO
from typing import Optional

from PIL import Image
import pytesseract


class OCRService:
    def extract_text_from_image(
        self,
        image_bytes: bytes,
        language: str = "chi_sim+eng",
    ) -> str:
        """
        OCR 图片文字识别。
        注意：pytesseract 需要本机安装 Tesseract OCR 程序。
        如果未安装或识别失败，返回空字符串，避免 demo 崩溃。
        """
        try:
            image = Image.open(BytesIO(image_bytes))
            text = pytesseract.image_to_string(image, lang=language)
            return text.strip() if text else ""
        except Exception:
            return ""

import re
from typing import List, Any, Dict

from app.config import settings
from app.prompts.claim_prompt import CLAIM_EXTRACTION_SYSTEM_PROMPT
from app.prompts.multimodal_claim_prompt import MULTIMODAL_CLAIM_EXTRACTION_SYSTEM_PROMPT
from app.services.llm_client import LLMClient
from app.schemas import ClaimItem


VALID_CLAIM_TYPES = {
    "event",
    "statistic",
    "person",
    "organization",
    "location",
    "medical",
    "policy",
    "other",
}

VALID_CLAIM_SCOPES = {
    "text_only",
    "image_ocr",
    "image_visual",
    "image_text_relation",
}

VALID_SOURCE_MODALITIES = {
    "text",
    "url",
    "image_ocr",
    "image_visual",
}


class ClaimExtractor:
    def __init__(self):
        self.llm_client = LLMClient()

    def _build_user_prompt(self, text: str) -> str:
        return f"""
请从下面文本中提取可核查 claims。

文本：
{text}

请只输出 JSON，不要输出解释、Markdown、代码块或额外文字。
"""

    def _build_multimodal_user_prompt(
        self,
        user_text: str = "",
        url_text: str = "",
        ocr_text: str = "",
        image_description: str = "",
    ) -> str:
        return f"""
请从下面的多模态输入中提取可核查 claims。

[用户输入文字]
{user_text or "无"}

[URL 正文]
{url_text or "无"}

[图片 OCR 文本]
{ocr_text or "无"}

[图片视觉描述]
{image_description or "无"}

请特别注意：
- 如果用户文字声称“这张图是某地某事件现场”，请抽取为 image_text_relation claim。
- 如果只有图片，没有用户文字，则优先从 OCR 文本和图片视觉描述中抽取可核查 claim。
- 不要判断真假。
- 不要编造输入中没有的信息。
- 请只输出 JSON，不要输出解释、Markdown、代码块或额外文字。
"""

    def _normalize_claim_type(self, claim_type: Any) -> str:
        if not claim_type:
            return "other"
        claim_type = str(claim_type).strip().lower()
        return claim_type if claim_type in VALID_CLAIM_TYPES else "other"

    def _normalize_confidence(self, confidence: Any) -> float | None:
        if confidence is None:
            return None
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            return None
        if confidence < 0:
            return 0.0
        if confidence > 1:
            return 1.0
        return confidence

    def _normalize_claim_scope(self, scope: Any) -> str | None:
        if not scope:
            return None
        scope = str(scope).strip().lower()
        return scope if scope in VALID_CLAIM_SCOPES else None

    def _normalize_source_modalities(self, modalities: Any) -> List[str] | None:
        if not modalities:
            return None
        if isinstance(modalities, str):
            modalities = [modalities]
        if not isinstance(modalities, list):
            return None

        normalized = []
        for modality in modalities:
            m = str(modality).strip().lower()
            if m in VALID_SOURCE_MODALITIES and m not in normalized:
                normalized.append(m)

        return normalized or None

    def _postprocess_claims(self, raw_claims: list) -> List[ClaimItem]:
        seen = set()
        results = []

        for item in raw_claims:
            if not isinstance(item, dict):
                continue

            claim_text = str(item.get("claim", "")).strip()
            if not claim_text or len(claim_text) < 6:
                continue
            if claim_text in seen:
                continue

            seen.add(claim_text)
            claim_type = self._normalize_claim_type(item.get("type", "other"))
            confidence = self._normalize_confidence(item.get("confidence", None))

            results.append(
                ClaimItem(
                    id=len(results) + 1,
                    claim=claim_text,
                    type=claim_type,
                    confidence=confidence,
                )
            )

            if len(results) >= settings.MAX_CLAIMS:
                break

        return results

    def _postprocess_multimodal_claims(
        self,
        raw_claims: list,
        user_text: str = "",
        url_text: str = "",
        ocr_text: str = "",
        image_description: str = "",
        image_filename: str | None = None,
    ) -> List[ClaimItem]:
        seen = set()
        results = []

        for item in raw_claims:
            if not isinstance(item, dict):
                continue

            claim_text = str(item.get("claim", "")).strip()
            if not claim_text or len(claim_text) < 6:
                continue
            if claim_text in seen:
                continue

            seen.add(claim_text)

            claim_type = self._normalize_claim_type(item.get("type", "other"))
            confidence = self._normalize_confidence(item.get("confidence", None))
            claim_scope = self._normalize_claim_scope(item.get("claim_scope"))
            source_modalities = self._normalize_source_modalities(item.get("source_modalities"))

            # Fallback modality inference if model omits fields.
            if not source_modalities:
                inferred = []
                if user_text:
                    inferred.append("text")
                if url_text:
                    inferred.append("url")
                if ocr_text:
                    inferred.append("image_ocr")
                if image_description:
                    inferred.append("image_visual")
                source_modalities = inferred or None

            results.append(
                ClaimItem(
                    id=len(results) + 1,
                    claim=claim_text,
                    type=claim_type,
                    confidence=confidence,
                    source_modalities=source_modalities,
                    claim_scope=claim_scope,
                    evidence_hint={
                        "has_user_text": bool(user_text),
                        "has_url_text": bool(url_text),
                        "has_ocr_text": bool(ocr_text),
                        "has_image_description": bool(image_description),
                        "ocr_text": ocr_text,
                        "image_description": image_description,
                        "image_filename": image_filename,
                    },
                )
            )

            if len(results) >= settings.MAX_CLAIMS:
                break

        return results

    def _extract_claims_mock(self, text: str) -> List[ClaimItem]:
        sentences = re.split(r"[。！？；!?;]", text)
        results = []
        seen = set()

        for sentence in sentences:
            s = sentence.strip()
            if len(s) < 6:
                continue
            if s in seen:
                continue
            seen.add(s)

            results.append(
                ClaimItem(
                    id=len(results) + 1,
                    claim=s,
                    type="other",
                    confidence=0.5,
                )
            )

            if len(results) >= settings.MAX_CLAIMS:
                break

        return results

    def extract_claims(self, text: str) -> List[ClaimItem]:
        """
        文本版 Claim Extraction。
        """
        if settings.USE_MOCK:
            return self._extract_claims_mock(text)

        if not settings.DEEPSEEK_API_KEY:
            return self._extract_claims_mock(text)

        user_prompt = self._build_user_prompt(text)

        try:
            response_json: Dict[str, Any] = self.llm_client.chat_json(
                system_prompt=CLAIM_EXTRACTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
        except Exception:
            return self._extract_claims_mock(text)

        raw_claims = response_json.get("claims", [])
        if not isinstance(raw_claims, list):
            return []

        return self._postprocess_claims(raw_claims)

    def extract_claims_multimodal(
        self,
        user_text: str = "",
        url_text: str = "",
        ocr_text: str = "",
        image_description: str = "",
        image_filename: str | None = None,
    ) -> List[ClaimItem]:
        """
        多模态 Claim Extraction。
        输入：用户文字、URL 正文、OCR 文本、视觉大模型图片描述。
        输出：text_only / image_ocr / image_visual / image_text_relation claims。
        """
        combined_text = "\n\n".join(
            part for part in [user_text, url_text, ocr_text, image_description] if part
        )

        if settings.USE_MOCK:
            return self._extract_claims_mock(combined_text)

        if not settings.DEEPSEEK_API_KEY:
            return self._extract_claims_mock(combined_text)

        user_prompt = self._build_multimodal_user_prompt(
            user_text=user_text,
            url_text=url_text,
            ocr_text=ocr_text,
            image_description=image_description,
        )

        try:
            response_json: Dict[str, Any] = self.llm_client.chat_json(
                system_prompt=MULTIMODAL_CLAIM_EXTRACTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
        except Exception:
            return self._extract_claims_mock(combined_text)

        raw_claims = response_json.get("claims", [])
        if not isinstance(raw_claims, list):
            return []

        return self._postprocess_multimodal_claims(
            raw_claims=raw_claims,
            user_text=user_text,
            url_text=url_text,
            ocr_text=ocr_text,
            image_description=image_description,
            image_filename=image_filename,
        )

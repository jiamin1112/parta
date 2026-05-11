from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field, HttpUrl, ConfigDict


class ClaimItem(BaseModel):
    id: int = Field(..., description="Claim 编号")
    claim: str = Field(..., description="抽取出的可核查陈述")

    type: Optional[str] = Field(
        default="other",
        description="Claim 类型，如 event/statistic/person/organization/location/medical/policy/other",
    )

    confidence: Optional[float] = Field(
        default=None,
        description="模型对该 claim 的抽取置信度，可选",
    )

    # 多模态扩展字段：全部为 Optional，保证原文本版接口兼容
    source_modalities: Optional[List[str]] = Field(
        default=None,
        description="claim 来源模态，如 text/url/image_ocr/image_visual",
    )

    claim_scope: Optional[str] = Field(
        default=None,
        description="claim 范围，如 text_only/image_ocr/image_visual/image_text_relation",
    )

    evidence_hint: Optional[Dict[str, Any]] = Field(
        default=None,
        description="给后续 RAG 的辅助信息，如 OCR 文本、图片描述、文件名等",
    )


class ClaimExtractionRequest(BaseModel):
    text: Optional[str] = Field(
        default="",
        description="用户输入的原始文本；不输入时留空",
        examples=[
            "网传某市昨晚发生大规模停电，官方称已有30万人受影响，预计今晚恢复供电。"
        ],
    )

    url: Optional[HttpUrl] = Field(
        default=None,
        description="可选新闻链接或网页链接；不输入时可填 null",
        examples=["https://example.com/news/article"],
    )

    language: Optional[str] = Field(
        default="zh",
        description="语言，如 zh / en",
        examples=["zh"],
    )

    source_type: Optional[str] = Field(
        default="news",
        description="输入来源类型，如 news/social_media/article/chat/notice/other",
        examples=["news"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "网传某市昨晚发生大规模停电，官方称已有30万人受影响，预计今晚恢复供电。",
                "url": "https://example.com/news/article",
                "language": "zh",
                "source_type": "news",
            }
        }
    )


class ClaimExtractionResponse(BaseModel):
    success: bool
    raw_input: str
    cleaned_text: str
    claims: List[ClaimItem]
    claim_count: int
    next_module_input: Dict[str, Any]
    message: str

    mode: Optional[str] = Field(
        default=None,
        description="处理模式：text_rumor/multimodal_rumor/image_only",
    )

    diagnostics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="调试信息",
    )
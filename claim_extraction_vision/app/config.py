import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME = os.getenv("APP_NAME", "Claim Extraction Service")
    APP_VERSION = os.getenv("APP_VERSION", "0.4.0")

    # Text LLM: DeepSeek uses an OpenAI-compatible API.
    # Do not hard-code API keys in source code.
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # Vision LLM: generic OpenAI-compatible configuration.
    # Recommended for this demo: Qwen-VL through Alibaba Cloud Model Studio / DashScope.
    USE_VISION_LLM = os.getenv("USE_VISION_LLM", "false").lower() == "true"
    VISION_PROVIDER = os.getenv("VISION_PROVIDER", "qwen")
    VISION_API_KEY = os.getenv("VISION_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    VISION_BASE_URL = os.getenv(
        "VISION_BASE_URL",
        os.getenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    )
    VISION_MODEL = os.getenv("VISION_MODEL", "qwen-vl-plus")
    VISION_DETAIL = os.getenv("VISION_DETAIL", "low")

    # Local OCR is optional. If Tesseract is not installed, the app will skip it and use VLM OCR.
    ENABLE_LOCAL_OCR = os.getenv("ENABLE_LOCAL_OCR", "true").lower() == "true"

    MAX_INPUT_LENGTH = int(os.getenv("MAX_INPUT_LENGTH", 5000))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))
    MAX_CLAIMS = int(os.getenv("MAX_CLAIMS", 10))
    MIN_INPUT_LENGTH = int(os.getenv("MIN_INPUT_LENGTH", 10))

    # Mock mode keeps the demo running without LLM calls.
    USE_MOCK = os.getenv("USE_MOCK", "false").lower() == "true"


settings = Settings()

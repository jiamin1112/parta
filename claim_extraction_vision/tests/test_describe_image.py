from app.services.vision_llm_service import VisionLLMService


def test_analyze_image(image_path: str):
    service = VisionLLMService()

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    result = service.analyze_image(
        image_bytes=image_bytes,
        content_type="image/jpeg",
        language="zh",
    )

    print("========== VLM OCR 文本 ==========")
    print(result.get("ocr_text", ""))

    print("\n========== 图片描述 ==========")
    print(result.get("image_description", ""))


if __name__ == "__main__":
    # Put your image in the project root and rename it to test.jpg, or change this path.
    test_analyze_image("test.jpg")

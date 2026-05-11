import json
import mimetypes
from pathlib import Path

import requests


API_URL = "http://127.0.0.1:8000/extract_claims_multimodal"


def guess_content_type(image_path: str) -> str:
    content_type, _ = mimetypes.guess_type(image_path)
    return content_type or "application/octet-stream"


def print_result(data: dict):
    print("\n========== 基本信息 ==========")
    print(f"success: {data.get('success')}")
    print(f"mode: {data.get('mode')}")
    print(f"message: {data.get('message')}")
    print(f"claim_count: {data.get('claim_count')}")

    diagnostics = data.get("diagnostics") or {}
    print("\n========== 诊断信息 ==========")
    print(f"vision_provider: {diagnostics.get('vision_provider')}")
    print(f"vision_model: {diagnostics.get('vision_model')}")
    print(f"ocr_text_available: {diagnostics.get('ocr_text_available')}")
    print(f"image_description_available: {diagnostics.get('image_description_available')}")
    print(f"total_cost_seconds: {diagnostics.get('total_cost_seconds')}")

    print("\n========== Claims ==========")
    for item in data.get("claims", []):
        print(f'{item.get("id")}. [{item.get("type")}] {item.get("claim")}')
        print(f'   confidence: {item.get("confidence")}')
        print(f'   source_modalities: {item.get("source_modalities")}')
        print(f'   claim_scope: {item.get("claim_scope")}')

    print("\n========== 给人员 B 的 next_module_input ==========")
    print(json.dumps(data.get("next_module_input"), ensure_ascii=False, indent=2))

    print("\n========== 完整 JSON ==========")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def test_text_plus_image(image_path: str):
    data = {
        "text": "网传这是《乘风》二公上半场直播现场，两位嘉宾正在进行全开麦真实竞技。",
        "url": "",
        "language": "zh",
        "source_type": "social_media",
    }

    path = Path(image_path)

    with open(path, "rb") as f:
        files = {
            "image": (
                path.name,
                f,
                guess_content_type(str(path)),
            )
        }
        response = requests.post(API_URL, data=data, files=files)

    response.raise_for_status()
    print_result(response.json())


def test_image_only(image_path: str):
    data = {
        "text": "",
        "url": "",
        "language": "zh",
        "source_type": "social_media",
    }

    path = Path(image_path)

    with open(path, "rb") as f:
        files = {
            "image": (
                path.name,
                f,
                guess_content_type(str(path)),
            )
        }
        response = requests.post(API_URL, data=data, files=files)

    response.raise_for_status()
    print_result(response.json())


if __name__ == "__main__":
    # 只测图片
    # test_image_only(r"E:\hero_demo\test.png")

    # 测图文联合
    test_text_plus_image(r"E:\hero_demo\test.png")
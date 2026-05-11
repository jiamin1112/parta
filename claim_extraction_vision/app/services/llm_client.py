import json
from typing import Dict, Any

from openai import OpenAI
from app.config import settings


class LLMClient:
    def __init__(self):
        self.client = (
            OpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
            )
            if settings.DEEPSEEK_API_KEY
            else None
        )
        self.model = settings.DEEPSEEK_MODEL

    def chat_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """
        调用文本 LLM，并强制期望返回 JSON。
        如果 API 调用失败或返回非 JSON，会抛出 ValueError。
        """
        if not self.client:
            raise ValueError("DEEPSEEK_API_KEY is not set.")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
                timeout=settings.REQUEST_TIMEOUT,
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("LLM returned empty content.")

            return json.loads(content)

        except json.JSONDecodeError as e:
            raise ValueError(f"LLM 返回内容不是合法 JSON: {str(e)}")
        except Exception as e:
            raise ValueError(f"LLM 调用失败: {str(e)}")

from typing import Type

import google.generativeai as genai

from app.llm.base import LLMClient, ProviderError, SchemaT


class GeminiClient(LLMClient):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model)

    def generate(self, prompt: str, schema: Type[SchemaT]) -> SchemaT:
        try:
            response = self._model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                },
            )
        except Exception as exc:  # noqa: BLE001 - SDK raises various transport errors
            status_code, retry_after = _classify_gemini_error(exc)
            raise ProviderError(str(exc), status_code=status_code, retry_after=retry_after) from exc

        return schema.model_validate_json(response.text)


def _classify_gemini_error(exc: Exception) -> tuple[int, float | None]:
    status_code = getattr(exc, "code", None) or getattr(exc, "status_code", 500)
    retry_after = getattr(exc, "retry_after", None)
    return int(status_code) if isinstance(status_code, int) else 500, retry_after

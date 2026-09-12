from typing import Type

from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.llm.base import LLMClient, ProviderError, SchemaT


class GeminiClient(LLMClient):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-3.6-flash"):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate(self, prompt: str, schema: Type[SchemaT]) -> SchemaT:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
        except APIError as exc:
            retry_after = _extract_retry_after(exc)
            raise ProviderError(str(exc), status_code=exc.code or 500, retry_after=retry_after) from exc

        return schema.model_validate_json(response.text)


def _extract_retry_after(exc: APIError) -> float | None:
    details = getattr(exc, "details", None) or {}
    for entry in details.get("error", {}).get("details", []):
        if entry.get("@type", "").endswith("RetryInfo"):
            delay = entry.get("retryDelay", "")
            if delay.endswith("s"):
                try:
                    return float(delay[:-1])
                except ValueError:
                    return None
    return None

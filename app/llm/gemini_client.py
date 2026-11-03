from typing import Type

from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import ValidationError

from app.llm.base import Image, LLMClient, ProviderError, SchemaT


class GeminiClient(LLMClient):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-3.6-flash"):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate(self, prompt: str, schema: Type[SchemaT], images: list[Image] | None = None) -> SchemaT:
        contents = [prompt, *(types.Part.from_bytes(data=data, mime_type=mime) for data, mime in images)] if images else prompt
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    # response_json_schema, not response_schema: the latter rejects dict fields
                    # (additionalProperties) with a client-side ValueError on the Developer API.
                    response_json_schema=schema.model_json_schema(),
                ),
            )
        except APIError as exc:
            retry_after = _extract_retry_after(exc)
            raise ProviderError(str(exc), status_code=exc.code or 500, retry_after=retry_after) from exc
        except Exception as exc:  # noqa: BLE001 - SDK-side failures must still trigger router fallback
            raise ProviderError(str(exc), status_code=500) from exc

        try:
            return schema.model_validate_json(response.text)
        except (ValidationError, TypeError) as exc:
            raise ProviderError(f"Gemini returned output not matching the schema: {exc}", status_code=502) from exc


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

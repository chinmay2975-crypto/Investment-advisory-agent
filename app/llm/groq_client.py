import base64
from typing import Type

from groq import Groq
from pydantic import ValidationError

from app.llm.base import Image, LLMClient, ProviderError, SchemaT


class GroqClient(LLMClient):
    name = "groq"

    def __init__(self, api_key: str, model: str = "openai/gpt-oss-120b", vision_model: str = "qwen/qwen3.8-27b"):
        self._client = Groq(api_key=api_key)
        self._model = model
        self._vision_model = vision_model  # the text model can't read images

    def generate(self, prompt: str, schema: Type[SchemaT], images: list[Image] | None = None) -> SchemaT:
        user_content: str | list = prompt
        if images:
            user_content = [{"type": "text", "text": prompt}] + [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}}
                for data, mime in images
            ]
        try:
            response = self._client.chat.completions.create(
                model=self._vision_model if images else self._model,
                messages=[
                    {
                        "role": "system",
                        "content": f"Respond only with JSON matching this schema: {schema.model_json_schema()}",
                    },
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # noqa: BLE001 - SDK raises various transport errors
            status_code, retry_after = _classify_groq_error(exc)
            raise ProviderError(str(exc), status_code=status_code, retry_after=retry_after) from exc

        content = response.choices[0].message.content
        try:
            return schema.model_validate_json(content or "")
        except ValidationError as exc:
            raise ProviderError(f"Groq returned output not matching the schema: {exc}", status_code=502) from exc


def _classify_groq_error(exc: Exception) -> tuple[int, float | None]:
    status_code = getattr(exc, "status_code", 500)
    retry_after = None
    response = getattr(exc, "response", None)
    if response is not None:
        header = response.headers.get("Retry-After") if hasattr(response, "headers") else None
        if header is not None:
            try:
                retry_after = float(header)
            except ValueError:
                retry_after = None
    return int(status_code) if isinstance(status_code, int) else 500, retry_after

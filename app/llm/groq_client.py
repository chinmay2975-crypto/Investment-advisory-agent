from typing import Type

from groq import Groq

from app.llm.base import LLMClient, ProviderError, SchemaT


class GroqClient(LLMClient):
    name = "groq"

    def __init__(self, api_key: str, model: str = "openai/gpt-oss-120b"):
        self._client = Groq(api_key=api_key)
        self._model = model

    def generate(self, prompt: str, schema: Type[SchemaT]) -> SchemaT:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": f"Respond only with JSON matching this schema: {schema.model_json_schema()}",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # noqa: BLE001 - SDK raises various transport errors
            status_code, retry_after = _classify_groq_error(exc)
            raise ProviderError(str(exc), status_code=status_code, retry_after=retry_after) from exc

        content = response.choices[0].message.content
        return schema.model_validate_json(content)


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

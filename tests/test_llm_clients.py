from unittest.mock import MagicMock, patch

import pytest

from app.llm.base import LLMClient, ProviderError
from app.llm.gemini_client import GeminiClient
from app.llm.groq_client import GroqClient
from app.llm.router import LLMRouter
from app.schemas.recommendation import RecommendationOutput

VALID_JSON = (
    '{"what": "60/40", "target_allocation": {"stocks": 60, "bonds": 40}, "suggested_instruments": ["VTI"], '
    '"why": "w", "expected_behavior": "e", "goal_probability": 0.7, "risks": ["r"]}'
)


def gemini_with(generate_content) -> GeminiClient:
    with patch("app.llm.gemini_client.genai.Client") as client_cls:
        client_cls.return_value.models.generate_content = generate_content
        return GeminiClient(api_key="test")


def test_gemini_sends_json_schema_supporting_dict_fields():
    generate = MagicMock(return_value=MagicMock(text=VALID_JSON))
    out = gemini_with(generate).generate("p", RecommendationOutput)

    config = generate.call_args.kwargs["config"]
    assert config.response_json_schema == RecommendationOutput.model_json_schema()
    assert out.target_allocation == {"stocks": 60, "bonds": 40}


def test_gemini_sdk_side_error_becomes_provider_error():
    client = gemini_with(MagicMock(side_effect=ValueError("additionalProperties is only supported ...")))
    with pytest.raises(ProviderError):
        client.generate("p", RecommendationOutput)


def test_gemini_invalid_json_becomes_provider_error():
    client = gemini_with(MagicMock(return_value=MagicMock(text='{"what": "missing fields"}')))
    with pytest.raises(ProviderError):
        client.generate("p", RecommendationOutput)


def test_groq_invalid_json_becomes_provider_error():
    with patch("app.llm.groq_client.Groq") as groq_cls:
        message = MagicMock(content="not json")
        groq_cls.return_value.chat.completions.create.return_value = MagicMock(choices=[MagicMock(message=message)])
        client = GroqClient(api_key="test")
    with pytest.raises(ProviderError):
        client.generate("p", RecommendationOutput)


class Working(LLMClient):
    name = "working"

    def generate(self, prompt, schema):
        return schema.model_validate_json(VALID_JSON)


def test_router_falls_back_when_gemini_fails_client_side():
    failing_gemini = gemini_with(MagicMock(side_effect=ValueError("schema not supported")))
    router = LLMRouter([failing_gemini, Working()])
    providers = {router.generate("p", RecommendationOutput)[1] for _ in range(4)}
    assert providers == {"working"}  # Gemini cools down and Groq-equivalent serves every call


def test_gemini_attaches_images_as_parts():
    generate = MagicMock(return_value=MagicMock(text=VALID_JSON))
    gemini_with(generate).generate("read this", RecommendationOutput, images=[(b"\xff\xd8\xffjpeg", "image/jpeg")])
    contents = generate.call_args.kwargs["contents"]
    assert contents[0] == "read this"
    assert contents[1].inline_data.mime_type == "image/jpeg"


def test_groq_uses_vision_model_and_data_url_for_images():
    with patch("app.llm.groq_client.Groq") as groq_cls:
        create = groq_cls.return_value.chat.completions.create
        create.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content=VALID_JSON))])
        client = GroqClient(api_key="test")
        client.generate("read this", RecommendationOutput, images=[(b"abc", "image/png")])
        kwargs = create.call_args.kwargs
        assert kwargs["model"] == "qwen/qwen3.8-27b"
        user_content = kwargs["messages"][1]["content"]
        assert user_content[1]["image_url"]["url"].startswith("data:image/png;base64,")

        client.generate("text only", RecommendationOutput)
        assert create.call_args.kwargs["model"] == "openai/gpt-oss-120b"


def test_router_passes_images_and_keeps_text_only_clients_working():
    seen = {}

    class Vision(LLMClient):
        name = "vision"

        def generate(self, prompt, schema, images=None):
            seen["images"] = images
            return schema.model_validate_json(VALID_JSON)

    LLMRouter([Vision()]).generate("p", RecommendationOutput, images=[(b"x", "image/png")])
    assert seen["images"] == [(b"x", "image/png")]
    # text-only clients that don't accept `images` still work for plain prompts
    assert LLMRouter([Working()]).generate("p", RecommendationOutput)[1] == "working"


def test_router_prefers_named_provider_but_falls_back():
    class Named(LLMClient):
        def __init__(self, name, fail=False):
            self.name, self.fail = name, fail

        def generate(self, prompt, schema, images=None):
            if self.fail:
                raise ProviderError("busy", status_code=503)
            return schema.model_validate_json(VALID_JSON)

    router = LLMRouter([Named("groq"), Named("gemini")])
    assert {router.generate("p", RecommendationOutput, prefer="gemini")[1] for _ in range(4)} == {"gemini"}

    busy = LLMRouter([Named("groq"), Named("gemini", fail=True)])
    assert busy.generate("p", RecommendationOutput, prefer="gemini")[1] == "groq"

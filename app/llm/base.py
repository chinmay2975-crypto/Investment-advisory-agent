from abc import ABC, abstractmethod
from typing import Type, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class ProviderError(Exception):
    """Raised by a provider client on rate-limit (429) or transient server (5xx) errors."""

    def __init__(self, message: str, status_code: int, retry_after: float | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class LLMClient(ABC):
    """Common interface every provider client implements.

    Engines call this abstraction, never a provider SDK directly, so the
    router can swap providers transparently on failure.
    """

    name: str

    @abstractmethod
    def generate(self, prompt: str, schema: Type[SchemaT]) -> SchemaT:
        """Call the provider and return output validated/coerced into `schema`.

        Raises ProviderError on rate-limit or transient failures so the
        router can mark this provider cooling_down and retry elsewhere.
        """
        raise NotImplementedError

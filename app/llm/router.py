import time
from dataclasses import dataclass, field
from typing import Type

from app.llm.base import Image, LLMClient, ProviderError, SchemaT

DEFAULT_COOLDOWN_SECONDS = 30.0


@dataclass
class ProviderState:
    client: LLMClient
    cooling_down_until: float = 0.0
    success_count: int = 0
    failure_count: int = 0

    def is_available(self) -> bool:
        return time.monotonic() >= self.cooling_down_until

    def cooldown_remaining(self) -> float:
        return max(0.0, self.cooling_down_until - time.monotonic())

    def mark_cooling_down(self, seconds: float):
        self.cooling_down_until = time.monotonic() + seconds
        self.failure_count += 1

    def mark_success(self):
        self.success_count += 1


class LLMRouter:
    """Alternates between LLMClient providers, falling back on rate limits/errors.

    Every engine should call `generate()` on this router rather than a
    provider client directly, so it never needs to know which provider
    actually served the request (Section 7a of the tech-stack doc).
    """

    def __init__(self, providers: list[LLMClient]):
        if not providers:
            raise ValueError("LLMRouter requires at least one provider")
        self._states: list[ProviderState] = [ProviderState(client=p) for p in providers]
        self._next_index = 0

    def generate(
        self,
        prompt: str,
        schema: Type[SchemaT],
        images: list[Image] | None = None,
        prefer: str | None = None,
    ) -> tuple[SchemaT, str]:
        """Returns (result, provider_name) so callers can log which provider served the request.

        `prefer` names a provider to try first when it is available (e.g. the one that is more
        accurate for a task); the others remain fallbacks, so alternation on errors still applies.
        """
        order = self._ordered_states()
        if prefer:
            order.sort(key=lambda s: s.client.name != prefer)  # stable: keeps round-robin among the rest
        last_error: Exception | None = None

        def call(client: LLMClient) -> SchemaT:
            # Only pass images when there are some, so text-only clients keep their simple signature.
            return client.generate(prompt, schema, images=images) if images else client.generate(prompt, schema)

        for state in order:
            if not state.is_available():
                continue
            try:
                result = call(state.client)
            except ProviderError as exc:
                cooldown = exc.retry_after if exc.retry_after else DEFAULT_COOLDOWN_SECONDS
                state.mark_cooling_down(cooldown)
                last_error = exc
                continue
            else:
                state.mark_success()
                return result, state.client.name

        # All providers cooling down: wait out whichever recovers first, then retry once.
        soonest = min(order, key=lambda s: s.cooldown_remaining())
        wait = soonest.cooldown_remaining()
        if wait > 0:
            time.sleep(wait)
        try:
            result = call(soonest.client)
        except ProviderError as exc:
            raise exc if last_error is None else last_error
        soonest.mark_success()
        return result, soonest.client.name

    def _ordered_states(self) -> list[ProviderState]:
        """Round-robin by default; prefers whichever has a lower failure rate."""
        states = sorted(self._states, key=lambda s: s.failure_count)
        self._next_index = (self._next_index + 1) % len(states)
        return states[self._next_index:] + states[:self._next_index]

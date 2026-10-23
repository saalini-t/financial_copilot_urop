"""A thin client for a locally running Ollama server.

Talks to Ollama's `/api/generate` endpoint directly over HTTP via `requests`
(already present in the environment; not declared as a project dependency
yet, but no new package is needed for this). One responsibility only: send a
prompt, return the model's raw text or raise one clearly-messaged exception.
Parsing that text into an ExperimentOutput is the caller's job (see
src/agents/baseline.py), not this module's -- this stays a dumb transport.

No retry logic. A single local call either works or it doesn't; the caller
(baseline.py) treats any failure here as one thing -- abstain -- so retrying
here would only add complexity without changing what happens next.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_TIMEOUT_SECONDS = 60.0


class LLMClientError(Exception):
    """Raised for every failure talking to the model -- connection refused,
    timeout, a non-200 status, an unparseable response body, or an empty
    generation. The message always names which of these it was; callers
    don't need to inspect anything beyond the message to log it usefully."""


@dataclass
class LLMResponse:
    raw_text: str
    model: str


class OllamaLLMClient:
    """Wraps one Ollama model. No connection pooling, no streaming, no
    retries -- the smallest client that can make one real call."""

    def __init__(
        self,
        model: str = "qwen2.5:3b",
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, prompt: str, *, temperature: float = 0.0) -> LLMResponse:
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature},
                },
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise LLMClientError(
                f"Ollama request timed out after {self.timeout}s (model={self.model})"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise LLMClientError(
                f"Could not reach Ollama at {self.base_url} (model={self.model}): {exc}"
            ) from exc

        if response.status_code != 200:
            raise LLMClientError(
                f"Ollama returned HTTP {response.status_code} (model={self.model}): "
                f"{response.text[:500]}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise LLMClientError(
                f"Ollama response was not valid JSON (model={self.model}): {response.text[:500]}"
            ) from exc

        text = payload.get("response", "")
        if not text or not text.strip():
            raise LLMClientError(f"Ollama returned an empty response (model={self.model})")

        return LLMResponse(raw_text=text, model=payload.get("model", self.model))

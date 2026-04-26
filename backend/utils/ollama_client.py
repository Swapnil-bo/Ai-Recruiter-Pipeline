import json
import httpx
import asyncio
import logging
from typing import AsyncGenerator, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from backend.core.config import settings

logger = logging.getLogger(__name__)


# ── Custom Exceptions ──────────────────────────────────────────────────────────

class OllamaConnectionError(Exception):
    """Ollama server is unreachable."""

class OllamaModelNotFoundError(Exception):
    """Requested model is not pulled."""

class OllamaTimeoutError(Exception):
    """Inference exceeded timeout."""

class OllamaJSONParseError(Exception):
    """Model returned malformed JSON when structured output was expected."""


# ── Ollama Client ──────────────────────────────────────────────────────────────

class OllamaClient:
    def __init__(
        self,
        base_url: str = settings.ollama_base_url,
        model: str = settings.ollama_model,
        timeout: int = settings.ollama_timeout,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            return httpx.AsyncClient(timeout=self.timeout)
        return self._client

    # ── Health ─────────────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Returns True if Ollama server is running."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def is_model_available(self, model: Optional[str] = None) -> bool:
        """Returns True if the model is pulled and ready."""
        target = model or self.model
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                models = [m["name"] for m in r.json().get("models", [])]
                return any(target in m for m in models)
        except Exception:
            return False

    async def assert_ready(self):
        """Raises descriptive errors if Ollama or model isn't ready."""
        if not await self.health_check():
            raise OllamaConnectionError(
                f"Cannot reach Ollama at {self.base_url}. Is it running?"
            )
        if not await self.is_model_available():
            raise OllamaModelNotFoundError(
                f"Model '{self.model}' not found. Run: ollama pull {self.model}"
            )

    # ── Core Chat ──────────────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def chat(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> str:
        """
        Single-turn chat. Returns the assistant response as a string.
        Retries up to 3x on connection/timeout errors.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }

        try:
            client = self._get_client()
            owned = self._client is None
            if owned:
                client = httpx.AsyncClient(timeout=self.timeout)

            try:
                r = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                r.raise_for_status()
                return r.json()["message"]["content"].strip()
            finally:
                if owned:
                    await client.aclose()

        except httpx.TimeoutException:
            raise OllamaTimeoutError(
                f"Ollama inference timed out after {self.timeout}s. "
                f"Try increasing OLLAMA_TIMEOUT in .env"
            )
        except httpx.ConnectError:
            raise OllamaConnectionError(
                f"Lost connection to Ollama at {self.base_url}"
            )

    # ── Structured JSON Output ─────────────────────────────────────────────────

    async def chat_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.2,        # low temp for structured output
        model: Optional[str] = None,
        retries: int = 2,
    ) -> dict:
        """
        Like chat() but forces JSON output and parses it.
        Appends JSON instruction to system prompt automatically.
        Retries parsing up to `retries` times if model returns malformed JSON.
        """
        json_system = (
            (system or "") +
            "\n\nYou MUST respond with valid JSON only. "
            "No markdown, no backticks, no explanation. Raw JSON only."
        ).strip()

        for attempt in range(retries + 1):
            raw = await self.chat(
                prompt=prompt,
                system=json_system,
                temperature=temperature,
                model=model,
            )

            # Strip accidental markdown fences
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()

            try:
                return json.loads(cleaned)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"JSON parse failed (attempt {attempt + 1}/{retries + 1}): {e}"
                    f"\nRaw response: {raw[:300]}"
                )
                if attempt == retries:
                    raise OllamaJSONParseError(
                        f"Model failed to return valid JSON after {retries + 1} attempts.\n"
                        f"Last raw response: {raw[:500]}"
                    )
                await asyncio.sleep(1)

    # ── Streaming ──────────────────────────────────────────────────────────────

    async def stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streams response tokens as they arrive.
        Usage:
            async for token in client.stream("Write a cover letter..."):
                print(token, end="", flush=True)
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model or self.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature},
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                chunk = json.loads(line)
                                token = chunk.get("message", {}).get("content", "")
                                if token:
                                    yield token
                                if chunk.get("done"):
                                    break
                            except json.JSONDecodeError:
                                continue

        except httpx.TimeoutException:
            raise OllamaTimeoutError(
                f"Stream timed out after {self.timeout}s."
            )
        except httpx.ConnectError:
            raise OllamaConnectionError(
                f"Lost connection to Ollama during stream."
            )

    # ── Convenience ───────────────────────────────────────────────────────────

    async def stream_to_string(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """Collects full stream into a single string."""
        chunks = []
        async for token in self.stream(prompt, system, temperature):
            chunks.append(token)
        return "".join(chunks)


# ── Singleton ──────────────────────────────────────────────────────────────────

ollama = OllamaClient()
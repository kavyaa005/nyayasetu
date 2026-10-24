"""One small client for every LLM provider we use (all speak the OpenAI-compatible API).

Usage:
    from nyayasetu.generation.llm import chat
    result = chat("groq", "<model-id>", [{"role": "user", "content": "Hello"}])
"""
import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

from nyayasetu.ingestion.layout import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")

PROVIDERS = {
    "groq": {"base_url": "https://api.groq.com/openai/v1", "key_env": "GROQ_API_KEY"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "key_env": "GEMINI_API_KEY"},
    "ollama": {"base_url": "http://localhost:11434/v1", "key_env": None},   # local, no key needed
}


@dataclass
class ChatResult:
    text: str
    provider: str
    model: str
    prompt_tokens: int | None       # tokens we sent
    completion_tokens: int | None   # tokens the model generated
    latency_s: float                # seconds from request to full answer


def get_client(provider: str) -> OpenAI:
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r}; choose from {list(PROVIDERS)}")
    cfg = PROVIDERS[provider]
    key = "ollama"   # Ollama ignores the key, but the client requires one
    if cfg["key_env"]:
        key = os.getenv(cfg["key_env"])
        if not key:
            raise RuntimeError(f"{cfg['key_env']} is not set. Add it to the .env file in the project folder.")
    # max_retries: the library automatically waits and retries on rate-limit (HTTP 429) errors.
    return OpenAI(base_url=cfg["base_url"], api_key=key, max_retries=5, timeout=120)


def chat(provider: str, model: str, messages: list[dict], temperature: float = 0.0,
         max_tokens: int = 700) -> ChatResult:
    client = get_client(provider)
    start = time.perf_counter()
    response = client.chat.completions.create(
        model=model, messages=messages, temperature=temperature, max_tokens=max_tokens,
    )
    latency = time.perf_counter() - start
    usage = response.usage
    return ChatResult(
        text=response.choices[0].message.content or "",
        provider=provider,
        model=model,
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        completion_tokens=getattr(usage, "completion_tokens", None),
        latency_s=round(latency, 2),
    )


def list_models(provider: str) -> list[str]:
    return sorted(m.id for m in get_client(provider).models.list())

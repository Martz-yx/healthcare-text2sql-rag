import logging
import os
from typing import AsyncGenerator

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_small_brain_client = None
_big_brain_client = None


def _get_small_brain_client() -> AsyncOpenAI:
    global _small_brain_client
    if _small_brain_client is None:
        _small_brain_client = AsyncOpenAI(
            base_url=os.getenv("VLLM_SMALL_BRAIN_BASE_URL", "http://localhost:8001/v1"),
            api_key=os.getenv("VLLM_SMALL_BRAIN_API_KEY", "not-needed"),
        )
    return _small_brain_client


def _get_big_brain_client() -> AsyncOpenAI:
    global _big_brain_client
    if _big_brain_client is None:
        _big_brain_client = AsyncOpenAI(
            base_url=os.getenv("VLLM_BIG_BRAIN_BASE_URL", "http://localhost:8000/v1"),
            api_key=os.getenv("VLLM_BIG_BRAIN_API_KEY", "not-needed"),
        )
    return _big_brain_client


SMALL_BRAIN_MODEL = os.getenv("VLLM_SMALL_BRAIN_MODEL", "gemma-4-E4B-it")
SMALL_BRAIN_TEMPERATURE = float(os.getenv("VLLM_SMALL_BRAIN_TEMPERATURE", "1.0"))
SMALL_BRAIN_TOP_P = float(os.getenv("VLLM_SMALL_BRAIN_TOP_P", "0.95"))
SMALL_BRAIN_TOP_K = int(os.getenv("VLLM_SMALL_BRAIN_TOP_K", "64"))

BIG_BRAIN_MODEL = os.getenv("VLLM_BIG_BRAIN_MODEL", "gemma-4-31B-it")
BIG_BRAIN_TEMPERATURE = float(os.getenv("VLLM_BIG_BRAIN_TEMPERATURE", "0.1"))
BIG_BRAIN_TOP_P = float(os.getenv("VLLM_BIG_BRAIN_TOP_P", "0.95"))
BIG_BRAIN_TOP_K = int(os.getenv("VLLM_BIG_BRAIN_TOP_K", "64"))


def _build_messages(
    system_prompt: str, user_message: str, history: list[dict]
) -> list[dict]:
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages


async def stream_small_brain(
    system_prompt: str,
    user_message: str,
    history: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    client = _get_small_brain_client()
    messages = _build_messages(system_prompt, user_message, history or [])
    stream = await client.chat.completions.create(
        model=SMALL_BRAIN_MODEL,
        messages=messages,
        temperature=SMALL_BRAIN_TEMPERATURE,
        top_p=SMALL_BRAIN_TOP_P,
        extra_body={"top_k": SMALL_BRAIN_TOP_K},
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content


async def stream_big_brain(
    system_prompt: str,
    user_message: str,
    history: list[dict] | None = None,
    thinking: bool = True,
) -> AsyncGenerator[str, None]:
    client = _get_big_brain_client()
    messages = _build_messages(system_prompt, user_message, history or [])
    extra_body: dict = {
        "top_k": BIG_BRAIN_TOP_K,
        "chat_template_kwargs": {"enable_thinking": thinking},
    }
    if not thinking:
        extra_body["reasoning_effort"] = "none"
    prompt_tokens = sum(len(m.get("content", "")) for m in messages) // 4
    logger.info(
        "[BIG_BRAIN] thinking=%s, extra_body=%s, ~prompt_tokens=%d, history_msgs=%d",
        thinking, extra_body, prompt_tokens, len(messages) - 2,
    )
    stream = await client.chat.completions.create(
        model=BIG_BRAIN_MODEL,
        messages=messages,
        temperature=BIG_BRAIN_TEMPERATURE,
        top_p=BIG_BRAIN_TOP_P,
        extra_body=extra_body,
        stream=True,
    )
    thinking_started = False
    async for chunk in stream:
        delta = chunk.choices[0].delta
        # Gemma 4 sends reasoning in a separate field, not in content
        reasoning = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None)
        if reasoning:
            if not thinking_started:
                yield "<think>"
                thinking_started = True
            yield reasoning
        if delta.content:
            if thinking_started:
                yield "</think>"
                thinking_started = False
            yield delta.content
    # Close think tag if stream ended during reasoning
    if thinking_started:
        yield "</think>"


async def collect_small_brain(
    system_prompt: str,
    user_message: str,
    history: list[dict] | None = None,
) -> str:
    chunks: list[str] = []
    async for chunk in stream_small_brain(system_prompt, user_message, history):
        chunks.append(chunk)
    return "".join(chunks)


async def collect_big_brain(
    system_prompt: str,
    user_message: str,
    history: list[dict] | None = None,
    thinking: bool = True,
) -> str:
    chunks: list[str] = []
    async for chunk in stream_big_brain(system_prompt, user_message, history, thinking):
        chunks.append(chunk)
    return "".join(chunks)

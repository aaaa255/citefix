"""Small DeepSeek client: OpenAI-compatible chat completions over plain HTTP."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

API_URL = "https://api.deepseek.com/chat/completions"
BALANCE_URL = "https://api.deepseek.com/user/balance"

JUDGE_MODEL = os.environ.get("CITEFIX_JUDGE_MODEL", "deepseek-flash")
AGENT_MODEL = os.environ.get("CITEFIX_AGENT_MODEL", "deepseek-flash")
JUDGE_EFFORT = os.environ.get("CITEFIX_JUDGE_EFFORT", "low")
AGENT_EFFORT = os.environ.get("CITEFIX_AGENT_EFFORT", "low")


class LLMError(Exception):
    """The model could not be reached or gave no usable answer."""


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    cached_tokens: int = 0
    completion_tokens: int = 0


usage = Usage()
_usage_lock = threading.Lock()


def _key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise LLMError("DEEPSEEK_API_KEY is not set (put it in .env or in the environment).")
    return key


def chat(messages: list[dict], *, model: str = JUDGE_MODEL, tools: list[dict] | None = None,
         json_mode: bool = False, effort: str = JUDGE_EFFORT, max_tokens: int = 4000,
         timeout_s: int = 180) -> tuple[dict, str]:
    """One chat completion; returns (assistant message, finish_reason).

    effort is DeepSeek's reasoning_effort: "none" turns thinking off, "low"/"high"/"max" turn it on.
    """
    body: dict = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if effort == "none":
        body["thinking"] = {"type": "disabled"}
    else:
        body["thinking"] = {"type": "enabled"}
        body["reasoning_effort"] = effort
    if tools:
        body["tools"] = tools
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    request = urllib.request.Request(
        API_URL, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                data = json.loads(response.read())
            break
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", "replace")[:300]
            if err.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise LLMError(f"DeepSeek HTTP {err.code}: {detail}") from err
        except (OSError, ValueError) as err:  # network errors, timeouts, unreadable replies
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise LLMError(f"DeepSeek request failed: {err}") from err
    reported = data.get("usage") or {}
    with _usage_lock:
        usage.calls += 1
        usage.prompt_tokens += reported.get("prompt_tokens", 0)
        usage.cached_tokens += reported.get("prompt_cache_hit_tokens", 0)
        usage.completion_tokens += reported.get("completion_tokens", 0)
    choice = data["choices"][0]
    return choice["message"], choice.get("finish_reason") or ""


def ask_json(system: str, user: str, *, model: str = JUDGE_MODEL, effort: str = JUDGE_EFFORT,
             max_tokens: int = 4000) -> dict:
    """Ask for one JSON object. DeepSeek needs the word "json" and an example in the prompt."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for _ in range(2):
        message, finish = chat(messages, model=model, json_mode=True, effort=effort, max_tokens=max_tokens)
        text = (message.get("content") or "").strip()  # invalid JSON comes back as blank text
        if text:
            try:
                answer = json.loads(text)
                if isinstance(answer, dict):
                    return answer
            except ValueError:
                pass
        if finish == "length":
            max_tokens *= 2
    raise LLMError("the model did not return a valid json object")


def usage_summary(balance_before: tuple[float, str] | None = None) -> str:
    text = (f"DeepSeek: {usage.calls} calls, {usage.prompt_tokens} input tokens ({usage.cached_tokens} cached), "
            f"{usage.completion_tokens} output tokens")
    after = balance() if balance_before else None
    if balance_before and after:
        text += f"; balance {balance_before[0]:.2f} -> {after[0]:.2f} {after[1]}"
    return text


def balance() -> tuple[float, str] | None:
    """Account balance, e.g. (56.22, "CNY"), or None when it cannot be read."""
    try:
        request = urllib.request.Request(BALANCE_URL, headers={"Authorization": f"Bearer {_key()}"})
        with urllib.request.urlopen(request, timeout=20) as response:
            info = json.loads(response.read())["balance_infos"][0]
        return float(info["total_balance"]), info["currency"]
    except Exception:
        return None

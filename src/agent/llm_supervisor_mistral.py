from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
import os

# Mistral official SDK (pip install mistralai)
from mistralai import Mistral


DEFAULT_SYSTEM_PROMPT_PATH = Path("prompts/llm_supervisor_system.md")


class LLMOutputError(ValueError):
    pass


def load_system_prompt(path: Path = DEFAULT_SYSTEM_PROMPT_PATH) -> str:
    if not path.exists():
        raise FileNotFoundError(f"System prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def _safe_json_loads(text: str) -> Dict[str, Any]:
    """
    Enforce JSON-only output. If Mistral returns extra text, we fail fast.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMOutputError(f"Model did not return valid JSON. Raw output:\n{text}") from e


def run_llm_supervisor(
    payload: Dict[str, Any],
    model: str = "mistral-large-latest",
    system_prompt_path: Path = DEFAULT_SYSTEM_PROMPT_PATH,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    """
    Calls Mistral API and returns the supervisor JSON.
    """
    load_dotenv()
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY missing. Put it in .env and restart terminal.")

    system_prompt = load_system_prompt(system_prompt_path)

    client = Mistral(api_key=api_key)

    user_content = json.dumps(payload, ensure_ascii=False)

    # Chat API
    resp = client.chat.complete(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=temperature,
    )

    content = resp.choices[0].message.content
    if not isinstance(content, str):
        # Sometimes SDK returns structured; force to string
        content = str(content)

    out = _safe_json_loads(content)

    # Minimal schema checks (strict)
    required_keys = ["summary_fr", "risks", "recommended_actions", "communication_to_staff"]
    for k in required_keys:
        if k not in out:
            raise LLMOutputError(f"Missing key '{k}' in LLM output. Output was: {out}")

    return out

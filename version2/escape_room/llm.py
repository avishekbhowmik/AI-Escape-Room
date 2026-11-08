"""Thin wrapper around the Google Gemini API (google-genai SDK)."""

import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "gemini-2.5-flash"


class LLMError(RuntimeError):
    """Raised when the LLM cannot be reached or returns nothing."""


def is_available() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai  # imported lazily so offline mode needs no SDK

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set.")
        _client = genai.Client(api_key=api_key)
    return _client


def generate(system_prompt: str, user_text: str, temperature: float = 0.7, json_mode: bool = False) -> str:
    from google.genai import types

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=temperature,
        response_mime_type="application/json" if json_mode else "text/plain",
    )
    try:
        response = _get_client().models.generate_content(
            model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
            contents=user_text,
            config=config,
        )
    except Exception as exc:
        raise LLMError(f"Gemini request failed: {exc}") from exc
    if not response.text:
        raise LLMError("Gemini returned an empty response.")
    return response.text.strip()

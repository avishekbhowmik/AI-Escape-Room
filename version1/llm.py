"""Thin wrapper around the Google Gemini API (google-genai SDK)."""

import os

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()

DEFAULT_MODEL = "gemini-3.5-flash-lite"


class LLMError(RuntimeError):
    """Raised when the LLM cannot be reached or returns nothing."""


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your-gemini-api-key-here":
        raise LLMError("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")
    return genai.Client(api_key=api_key)


def chat(system_prompt: str, history: list[dict], temperature: float = 0.8) -> str:
    """Send the whole conversation to Gemini and return the model's reply.

    history is a list of {"role": "user" | "assistant", "content": str}.
    """
    client = get_client()
    contents = [
        {
            "role": "model" if msg["role"] == "assistant" else "user",
            "parts": [{"text": msg["content"]}],
        }
        for msg in history
    ]
    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=temperature),
        )
    except errors.APIError as exc:
        code = getattr(exc, "code", None)
        hints = {401: "check your API key", 403: "check your API key", 404: f"model '{model}' not found",
                 429: "free-tier rate limit reached, wait a minute"}
        raise LLMError(f"Gemini API error ({code}): {hints.get(code, getattr(exc, 'message', exc))}") from exc
    except Exception as exc:
        raise LLMError(f"Could not reach Gemini: {exc}") from exc

    if not response.text:
        raise LLMError("Gemini returned an empty response.")
    return response.text.strip()

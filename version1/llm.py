"""Thin wrapper around the Google Gemini API (google-genai SDK)."""

import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

DEFAULT_MODEL = "gemini-2.5-flash"


class LLMError(RuntimeError):
    """Raised when the LLM cannot be reached or returns nothing."""


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise LLMError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key."
        )
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
    try:
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
            ),
        )
    except Exception as exc:  # network errors, quota, invalid key ...
        raise LLMError(f"Gemini request failed: {exc}") from exc

    if not response.text:
        raise LLMError("Gemini returned an empty response.")
    return response.text.strip()

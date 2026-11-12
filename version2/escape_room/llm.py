"""Thin wrapper around the Google Gemini API (google-genai SDK).

Follows the error-handling and token-reporting pattern from the course
hands-on notebooks: API errors are turned into clear messages, and every
call can record its token usage so the cost of a turn is visible.
"""

import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "gemini-3.5-flash-lite"
PLACEHOLDER_KEYS = {"", "your-gemini-api-key-here", "your_api_key_here"}


class LLMError(RuntimeError):
    """Raised when the LLM cannot be reached or returns nothing usable."""


def model_name() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def is_available() -> bool:
    return os.getenv("GEMINI_API_KEY", "").strip() not in PLACEHOLDER_KEYS


_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai  # imported lazily so offline mode needs no SDK

        if not is_available():
            raise LLMError("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY").strip())
    return _client


def explain_api_error(code: int | None, message: str) -> str:
    if code in (401, 403):
        return f"Gemini rejected the API key ({code}). Check GEMINI_API_KEY and that the free tier is enabled."
    if code == 404:
        return f"Model '{model_name()}' was not found (404). Check GEMINI_MODEL in .env."
    if code == 429:
        return "Free-tier rate limit or quota reached (429). Wait a minute or switch Gemini off in the sidebar."
    return f"Gemini API error ({code}): {message}"


def record_usage(stats: dict | None, response=None) -> None:
    """Add one API call (and its tokens, when reported) to a stats dict."""
    if stats is None:
        return
    stats["api_calls"] = stats.get("api_calls", 0) + 1
    usage = getattr(response, "usage_metadata", None)
    if usage is not None:
        stats["input_tokens"] = stats.get("input_tokens", 0) + (getattr(usage, "prompt_token_count", 0) or 0)
        stats["output_tokens"] = stats.get("output_tokens", 0) + (getattr(usage, "candidates_token_count", 0) or 0)


def generate(
    system_prompt: str,
    user_text: str,
    temperature: float = 0.7,
    json_mode: bool = False,
    max_output_tokens: int = 400,
    stats: dict | None = None,
) -> str:
    from google.genai import errors, types

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        response_mime_type="application/json" if json_mode else "text/plain",
    )
    try:
        response = _get_client().models.generate_content(model=model_name(), contents=user_text, config=config)
    except errors.APIError as exc:
        record_usage(stats)
        raise LLMError(explain_api_error(getattr(exc, "code", None), getattr(exc, "message", str(exc)))) from exc
    except Exception as exc:  # network problems, timeouts
        raise LLMError(f"Could not reach Gemini ({type(exc).__name__}). Check your internet connection.") from exc

    record_usage(stats, response)
    if not response.text:
        raise LLMError("Gemini returned no text. The request may have been blocked or hit the token limit.")
    return response.text.strip()

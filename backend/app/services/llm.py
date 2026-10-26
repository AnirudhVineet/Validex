"""Thin wrapper around the Groq API for the two optional AI features.

- AI fallback reader for poor scans (vision model)       -> settings.ai_fallback_enabled
- Evidence-grounded case summary (text model)             -> settings.llm_summary_enabled

Both are OFF by default and need GROQ_API_KEY. Neither decides anything: the reader only
suggests field values that an officer must confirm, and the summary only restates findings.
Responses are constrained to a JSON schema (Groq structured outputs, strict mode).
"""
import json

from app.config import settings


class LLMUnavailable(Exception):
    """No key, network/API error, or an unusable response. Callers fall back to manual review."""


def chat_json(model: str, system: str, user_content: str | list, schema_name: str, schema: dict,
              timeout: float = 60.0) -> dict:
    """One chat completion constrained to `schema`. Returns the parsed JSON object."""
    if not settings.groq_api_key:
        raise LLMUnavailable("GROQ_API_KEY is not set")
    try:
        import groq
    except ImportError as exc:  # pragma: no cover - dependency is in requirements.txt
        raise LLMUnavailable("groq package not installed") from exc

    client = groq.Groq(api_key=settings.groq_api_key, timeout=timeout, max_retries=1)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_content}],
            response_format={"type": "json_schema",
                             "json_schema": {"name": schema_name, "strict": True, "schema": schema}},
            temperature=0,
            max_completion_tokens=4096,
        )
    except groq.AuthenticationError as exc:
        raise LLMUnavailable("Groq rejected the API key") from exc
    except groq.RateLimitError as exc:
        raise LLMUnavailable("Groq rate limit reached; try again shortly") from exc
    except groq.APIStatusError as exc:
        raise LLMUnavailable(f"Groq API error {exc.status_code}") from exc
    except groq.APIConnectionError as exc:
        raise LLMUnavailable("Could not reach Groq (network)") from exc

    text = (response.choices[0].message.content or "").strip()
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise LLMUnavailable("Groq returned a response that is not valid JSON") from exc
    if not isinstance(data, dict):
        raise LLMUnavailable("Groq returned JSON that is not an object")
    return data

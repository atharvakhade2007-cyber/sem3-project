"""Gemini transport layer — API calls, JSON cleanup, and structured output.

All prompt/parse logic for summaries, flashcards, and question banks lives in
``llm_service.py``; this module only provides the Gemini plumbing:
  - _call_gemini: plain-text generation with SDK/model fallbacks
  - _call_gemini_structured: schema-enforced (structured output) generation
  - _clean_and_parse_json / _sanitize_nul: robust JSON extraction
"""

import os
import json
import re
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()


def _get_gemini_api_key(api_key: Optional[str] = None) -> str:
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key or not key.strip():
        raise ValueError(
            "Gemini API Key is missing. Please set GEMINI_API_KEY in your environment/.env "
            "or enter your key in the form."
        )
    return key.strip()


def _call_gemini(prompt: str, api_key: Optional[str] = None) -> str:
    """Call Gemini API with the given prompt, trying multiple SDKs and models."""
    import time

    clean_key = _get_gemini_api_key(api_key)
    raw_response_text = ""
    errors_log = []

    # 1. Primary Method: New Official google.genai SDK
    try:
        from google import genai
        client = genai.Client(api_key=clean_key)

        base_fallbacks = [
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-pro",
        ]

        candidate_models = []
        try:
            for m in client.models.list():
                m_name = getattr(m, 'name', '') or ''
                if m_name.startswith("models/"):
                    m_name = m_name[len("models/"):]
                if 'gemini' in m_name.lower():
                    if not any(x in m_name.lower() for x in ['embed', 'imagen', 'veo', 'whisper', 'tts', 'aqa']):
                        if m_name not in candidate_models:
                            candidate_models.append(m_name)
        except Exception:
            pass

        for m in base_fallbacks:
            if m not in candidate_models:
                candidate_models.append(m)

        for model_name in candidate_models:
            for attempt in range(2):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    if response and hasattr(response, 'text') and response.text:
                        raw_response_text = response.text
                        break
                except Exception as model_err:
                    err_str = str(model_err)
                    errors_log.append(f"{model_name} (attempt {attempt+1}): {err_str}")
                    if "API_KEY_INVALID" in err_str or "API key not valid" in err_str:
                        raise ValueError("Your Gemini API Key is invalid.")
                    if ("429" in err_str or "Quota exceeded" in err_str or "RESOURCE_EXHAUSTED" in err_str) and attempt == 0:
                        time.sleep(2.5)
                        continue
                    break
            if raw_response_text:
                break

    except ValueError:
        raise
    except Exception as sdk_err:
        errors_log.append(f"GenAI SDK init error: {str(sdk_err)}")

    # 2. Legacy SDK Fallback
    if not raw_response_text:
        try:
            import google.generativeai as genai_legacy
            genai_legacy.configure(api_key=clean_key)
            for m_name in ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-pro"]:
                try:
                    m = genai_legacy.GenerativeModel(m_name)
                    res = m.generate_content(prompt)
                    if res and res.text:
                        raw_response_text = res.text
                        break
                except Exception as leg_err:
                    errors_log.append(f"Legacy {m_name}: {str(leg_err)}")
        except Exception:
            pass

    # 3. HTTP REST Fallback
    if not raw_response_text:
        try:
            import requests
            for rest_model in ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash"]:
                rest_url = f"https://generativelanguage.googleapis.com/v1beta/models/{rest_model}:generateContent?key={clean_key}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.3}
                }
                res = requests.post(rest_url, headers=headers, json=payload, timeout=60)
                if res.status_code == 200:
                    data = res.json()
                    raw_response_text = data['candidates'][0]['content']['parts'][0]['text']
                    break
                else:
                    errors_log.append(f"REST API ({rest_model}): HTTP {res.status_code}")
        except Exception as rest_ex:
            errors_log.append(f"REST Exception: {str(rest_ex)}")

    if not raw_response_text:
        log_summary = "\n".join(errors_log[:3])
        if "429" in log_summary or "Quota exceeded" in log_summary or "RESOURCE_EXHAUSTED" in log_summary:
            raise RuntimeError("Gemini API Quota Exceeded. Please wait or create a new API key.")
        raise RuntimeError(f"Gemini API generation failed:\n{log_summary}")

    return raw_response_text


def _sanitize_nul(obj: Any) -> Any:
    """Recursively strip NUL (0x00) and other C0 control chars from strings.

    LLM output occasionally contains \\u0000 escapes; PostgreSQL rejects string
    literals containing NUL bytes, so any value heading to the DB must be
    cleaned. Non-string values pass through untouched.
    """
    if isinstance(obj, str):
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", obj)
    if isinstance(obj, list):
        return [_sanitize_nul(item) for item in obj]
    if isinstance(obj, dict):
        return {
            (_sanitize_nul(k) if isinstance(k, str) else k): _sanitize_nul(v)
            for k, v in obj.items()
        }
    return obj


def _clean_and_parse_json(raw_text: str) -> Any:
    """Strips markdown formatting, extracts JSON, and parses it safely."""
    cleaned = raw_text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    # Try to find a JSON object or array
    start_obj = cleaned.find("{")
    end_obj = cleaned.rfind("}")
    start_arr = cleaned.find("[")
    end_arr = cleaned.rfind("]")

    if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
        if start_arr == -1 or start_obj < start_arr:
            cleaned = cleaned[start_obj:end_obj + 1]
    elif start_arr != -1 and end_arr != -1 and end_arr > start_arr:
        cleaned = cleaned[start_arr:end_arr + 1]

    try:
        return _sanitize_nul(json.loads(cleaned))
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON response: {e}\nRaw Response:\n{raw_text}")


def _call_gemini_structured(
    prompt: str,
    response_schema: Dict[str, Any],
    api_key: Optional[str] = None,
) -> Any:
    """
    Call Gemini with JSON schema enforcement (structured output).

    Uses response_mime_type="application/json" + a response_schema dict so the
    model is constrained to emit valid JSON matching the schema. Falls back to
    a plain-text call + _clean_and_parse_json if the SDK/model doesn't support
    schemas, so this never hard-fails on model availability.

    Args:
        prompt: The instruction prompt.
        response_schema: Gemini JSON schema (plain dict, e.g.
            {"type": "ARRAY", "items": {"type": "OBJECT", ...}}).
        api_key: Optional override; otherwise env/.env key is used.

    Returns:
        The parsed JSON payload (dict / list / etc.).

    Raises:
        ValueError: On invalid API key or unparseable JSON.
        RuntimeError: When every model attempt fails.
    """
    clean_key = _get_gemini_api_key(api_key)
    errors_log = []

    # Primary path: google-genai SDK with response_schema
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=clean_key)
        models_to_try = [
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
        ]

        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        response_mime_type="application/json",
                        response_schema=response_schema,
                    ),
                )
                if response and hasattr(response, 'text') and response.text:
                    return _clean_and_parse_json(response.text)
            except Exception as err:
                err_str = str(err)
                errors_log.append(f"{model_name} (structured): {err_str}")
                if "API_KEY_INVALID" in err_str or "API key not valid" in err_str:
                    raise ValueError("Your Gemini API Key is invalid.")

    except ValueError:
        raise
    except Exception as sdk_err:
        errors_log.append(f"Structured SDK init error: {str(sdk_err)}")

    # Fallback: plain text generation, then parse (schema still requested in prompt)
    raw_response_text = _call_gemini(prompt, clean_key)
    return _clean_and_parse_json(raw_response_text)

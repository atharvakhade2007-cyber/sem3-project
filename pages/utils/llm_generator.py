import os
import json
import re
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()


def _get_gemini_api_key(api_key: Optional[str] = None) -> str:
    DEFAULT_API_KEY = "AQ.Ab8RN6KWR5JDKet3qlgLjdhIrZQL-uZDZHFOc6U_zpv3mQJxzA"
    key = api_key or os.environ.get("GEMINI_API_KEY") or DEFAULT_API_KEY
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
            "gemini-2.5-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
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
            for m_name in ["gemini-2.5-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-pro"]:
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
            for rest_model in ["gemini-2.5-flash", "gemini-3.6-flash", "gemini-3.5-flash"]:
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
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON response: {e}\nRaw Response:\n{raw_text}")


# ──────────────────────────────────────────────
#  Summary generation
# ──────────────────────────────────────────────

def generate_summary(
    text: str,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a multi-tiered summary from extracted text.
    Returns dict with keys: executive_summary, key_concepts, terminology
    """
    max_char_limit = 20000
    truncated_text = text[:max_char_limit]

    prompt = f"""You are an expert academic summarizer.

Given the following study material, produce a comprehensive summary structured as a JSON object with these EXACT keys:
1. "executive_summary": A concise 3-5 sentence TL;DR paragraph capturing the most important points.
2. "key_concepts": An array of 8-15 bullet-point strings, each being a core concept or takeaway.
3. "terminology": An array of objects, each with "term" and "definition" keys, covering 6-10 important terms from the text.

OUTPUT RULES (CRITICAL):
1. Output ONLY a valid raw JSON object. No commentary, no markdown blocks.
2. Each item in key_concepts must be a single clear sentence starting with a bullet point marker (•).
3. Each terminology entry must have "term" (string) and "definition" (string, one sentence).

STUDY MATERIAL TEXT:
{truncated_text}
"""
    raw_response = _call_gemini(prompt, api_key)
    parsed = _clean_and_parse_json(raw_response)

    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON object from LLM")

    return {
        "executive_summary": parsed.get("executive_summary", ""),
        "key_concepts": parsed.get("key_concepts", []),
        "terminology": parsed.get("terminology", []),
    }


# ──────────────────────────────────────────────
#  Flashcard generation
# ──────────────────────────────────────────────

def generate_flashcards(
    text: str,
    num_cards: int = 20,
    api_key: Optional[str] = None
) -> List[Dict[str, str]]:
    """
    Generate flashcards from extracted text.
    Returns list of dicts with 'front' and 'back' keys.
    """
    max_char_limit = 20000
    truncated_text = text[:max_char_limit]

    prompt = f"""You are an expert educator creating study flashcards.

Generate exactly {num_cards} high-quality flashcards from the provided study material.
Each flashcard should cover a distinct concept, term, or key idea.

OUTPUT RULES (CRITICAL):
1. Output ONLY a valid raw JSON array. No commentary, no markdown blocks.
2. Each object MUST have EXACTLY these keys:
   - "front": string — a question, prompt, or concept name (the side the user sees first)
   - "back": string — a concise, clear answer or definition
3. Cards should progress from foundational to advanced topics.

STUDY MATERIAL TEXT:
{truncated_text}
"""
    raw_response = _call_gemini(prompt, api_key)
    parsed = _clean_and_parse_json(raw_response)

    if not isinstance(parsed, list):
        raise ValueError("Expected JSON list from LLM")

    for card in parsed:
        if "front" not in card or "back" not in card:
            raise ValueError(f"Flashcard missing 'front' or 'back': {card}")

    return parsed


# ──────────────────────────────────────────────
#  Question bank generation (continuous Elo)
# ──────────────────────────────────────────────

def generate_question_bank(
    text: str,
    num_questions: int = 20,
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Generate a question bank with continuous difficulty ratings.
    
    Returns list of dicts with keys:
    - question, options (list of 4), correct_index (0-3),
      explanation, difficulty_label, difficulty_rating
    """
    max_char_limit = 20000
    truncated_text = text[:max_char_limit]

    prompt = f"""You are an expert educational assessment creator specializing in adaptive testing.

Generate exactly {num_questions} high-quality multiple-choice questions from the provided study text.

OUTPUT RULES (CRITICAL):
1. Output ONLY a valid raw JSON array. No commentary, no markdown blocks.
2. Each object MUST have EXACTLY these keys:
   - "question": string (the question text)
   - "options": array of exactly 4 strings (the answer choices)
   - "correct_index": integer 0-3 (index of the correct answer in the options array)
   - "explanation": string (1-2 sentences explaining why the correct answer is right)
   - "difficulty_label": string ("easy", "medium", or "hard")
   - "difficulty_rating": number (Elo-style difficulty rating)
     - Easy questions: between 800-1000
     - Medium questions: between 1200-1400
     - Hard questions: between 1600-1800

3. Distribute questions roughly evenly: ~7 easy, ~7 medium, ~6 hard
4. Questions should cover different concepts from the material
5. Each question must have exactly 4 distinct options

STUDY MATERIAL TEXT:
{truncated_text}
"""
    raw_response = _call_gemini(prompt, api_key)
    parsed = _clean_and_parse_json(raw_response)

    if not isinstance(parsed, list):
        raise ValueError("Expected JSON list from LLM")

    # Validate and normalize
    for i, q in enumerate(parsed):
        required = {"question", "options", "correct_index", "explanation"}
        missing = required - set(q.keys())
        if missing:
            raise ValueError(f"Question #{i+1} missing fields: {missing}")

        if not isinstance(q["options"], list) or len(q["options"]) != 4:
            raise ValueError(f"Question #{i+1} must have exactly 4 options")

        idx = q["correct_index"]
        if not isinstance(idx, int) or idx not in {0, 1, 2, 3}:
            raise ValueError(f"Question #{i+1} has invalid correct_index: {idx}")

        # Normalize difficulty
        label = q.get("difficulty_label", "medium").lower().strip()
        if label not in {"easy", "medium", "hard"}:
            label = "medium"
        q["difficulty_label"] = label

        # Ensure difficulty_rating is set
        rating = q.get("difficulty_rating")
        if not isinstance(rating, (int, float)):
            # Seed based on label
            seeds = {"easy": 900.0, "medium": 1300.0, "hard": 1700.0}
            rating = seeds[label]
        q["difficulty_rating"] = float(rating)

        q.setdefault("explanation", "")

    return parsed


# Keep backward compatibility alias
generate_adaptive_questions = generate_question_bank

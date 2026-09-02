"""
Daily Quiz Service — Generates GK & Current Affairs questions via Gemini.

Uses the existing Gemini integration from pages.utils.llm_generator.
"""

from datetime import date
from typing import List, Dict, Any

from pages.utils.llm_generator import _call_gemini, _clean_and_parse_json


def generate_daily_gk_questions(
    target_date: date,
    num_questions: int = 10,
    api_key: str = None,
) -> List[Dict[str, Any]]:
    """
    Generate 10 GK & Current Affairs MCQs for a given date.

    Returns list of dicts with keys:
    - question_text, options (list of 4), correct_index (0-3), explanation
    """
    date_str = target_date.strftime("%B %d, %Y")

    prompt = f"""You are an expert General Knowledge and Current Affairs quiz maker.

Generate exactly {num_questions} high-quality multiple-choice questions suitable for a daily GK quiz dated {date_str}.

COVER THESE TOPICS (rotate across categories):
- World News & Geopolitics
- Science & Technology
- Sports & Awards
- Economy & Business
- Environment & Climate
- History & Culture (on this day)
- Indian Affairs (if applicable)
- Important Days & Events

OUTPUT RULES (CRITICAL):
1. Output ONLY a valid raw JSON array. No commentary, no markdown blocks.
2. Each object MUST have EXACTLY these keys:
   - "question_text": string — the question
   - "options": array of EXACTLY 4 strings — the answer choices
   - "correct_index": integer 0-3 — index of the correct answer
   - "explanation": string — 1-2 sentences explaining why the correct answer is right
3. Each question must be factually accurate and unambiguous.
4. Options should be plausible — no obviously wrong distractors.
5. Vary difficulty: mix of easy, medium, and hard questions.

Generate exactly {num_questions} questions now.
"""
    raw_response = _call_gemini(prompt, api_key)
    parsed = _clean_and_parse_json(raw_response)

    if not isinstance(parsed, list):
        raise ValueError("Expected JSON list from LLM for daily quiz generation")

    # Validate and normalize
    for i, q in enumerate(parsed):
        required = {"question_text", "options", "correct_index", "explanation"}
        missing = required - set(q.keys())
        if missing:
            raise ValueError(f"Question #{i + 1} missing fields: {missing}")

        if not isinstance(q["options"], list) or len(q["options"]) != 4:
            raise ValueError(f"Question #{i + 1} must have exactly 4 options")

        idx = q["correct_index"]
        if not isinstance(idx, int) or idx not in {0, 1, 2, 3}:
            raise ValueError(f"Question #{i + 1} has invalid correct_index: {idx}")

        q.setdefault("explanation", "")

    return parsed

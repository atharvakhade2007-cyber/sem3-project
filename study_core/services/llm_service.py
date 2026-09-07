"""
LLM Service — Generates summaries, flashcards, and question banks.

Wraps the Gemini integration in services.llm_generator and provides a clean
service interface for the study_core app.
"""

import os
import json
import re
from typing import List, Dict, Any, Optional

# Reuse the existing Gemini infrastructure
from .llm_generator import (
    _call_gemini,
    _clean_and_parse_json,
)


def generate_summary(
    text: str,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a structured summary from extracted text.

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


def generate_flashcards(
    text: str,
    num_cards: int = 20,
    api_key: Optional[str] = None,
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


def generate_question_bank(
    text: str,
    num_questions: int = 20,
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Generate a difficulty-labeled question bank for the adaptive assessment engine.

    Returns list of dicts with keys:
    - question, options (list of 4), correct_index (0-3),
      explanation, difficulty_label ('easy'|'medium'|'hard'),
      difficulty_rating (Elo-style float)

    IMPORTANT: questions are tagged ONLY by difficulty, never by persona.
    Persona targeting is handled downstream by the study_core views using the
    user's active sub-tier and served_question_ids.
    """
    max_char_limit = 20000
    truncated_text = text[:max_char_limit]

    prompt = f"""You are an expert educational assessment creator specializing in adaptive testing.

Generate exactly {num_questions} high-quality multiple-choice questions from the provided study text.
These questions will later be served to students in one of three difficulty tiers.
You must NOT try to predict student personas — you only assign a difficulty label.

OUTPUT RULES (CRITICAL):
1. Output ONLY a valid raw JSON array. No commentary, no markdown blocks.
2. Each object MUST have EXACTLY these keys:
   - "question": string (the question text)
   - "options": array of exactly 4 strings (the answer choices)
   - "correct_index": integer 0-3 (index of the correct answer in the options array)
   - "explanation": string (1-2 sentences explaining why the correct answer is right)
   - "difficulty_label": string — EXACTLY one of "easy", "medium", or "hard"
   - "difficulty_rating": number (Elo-style difficulty rating)
     - Easy questions: between -400 and -200
     - Medium questions: between 0 and 200
     - Hard questions: between 400 and 600
     (0-based scale: a brand-new learner is rated 0 Elo)

3. Distribute questions as evenly as possible across the three difficulties.
   For example, for 18 questions use 6/6/6; for 20 use 7/7/6; for 24 use 8/8/8.
   The difference between any two difficulty counts must never exceed 1.
4. Questions should cover different concepts from the material
5. Each question must have exactly 4 distinct options

STUDY MATERIAL TEXT:
{truncated_text}
"""
    raw_response = _call_gemini(prompt, api_key)
    parsed = _clean_and_parse_json(raw_response)

    if not isinstance(parsed, list):
        raise ValueError("Expected JSON list from LLM")

    # Validate, normalize, and enforce difficulty distribution.
    normalized: List[Dict[str, Any]] = []
    seen_texts: set = set()
    for i, q in enumerate(parsed):
        # Drop verbatim duplicate questions returned by the LLM so the bank
        # never contains the same question twice.
        q_key = re.sub(r'[^a-z0-9]+', '', str(q.get('question', '')).lower())
        if not q_key or q_key in seen_texts:
            continue
        seen_texts.add(q_key)

        required = {"question", "options", "correct_index", "explanation"}
        missing = required - set(q.keys())
        if missing:
            raise ValueError(f"Question #{i + 1} missing fields: {missing}")

        if not isinstance(q["options"], list) or len(q["options"]) != 4:
            raise ValueError(f"Question #{i + 1} must have exactly 4 options")

        idx = q["correct_index"]
        if not isinstance(idx, int) or idx not in {0, 1, 2, 3}:
            raise ValueError(f"Question #{i + 1} has invalid correct_index: {idx}")

        label = q.get("difficulty_label", "medium").lower().strip()
        if label not in {"easy", "medium", "hard"}:
            label = "medium"

        rating = q.get("difficulty_rating")
        if not isinstance(rating, (int, float)):
            seeds = {"easy": -300.0, "medium": 100.0, "hard": 500.0}
            rating = seeds[label]
        else:
            rating = float(rating)

        q_out: Dict[str, Any] = {
            "question": str(q["question"]).strip(),
            "options": [str(o).strip() for o in q["options"]],
            "correct_index": int(idx),
            "explanation": str(q.get("explanation", "")).strip(),
            "difficulty_label": label,
            "difficulty_rating": rating,
        }
        normalized.append(q_out)

    return _force_even_difficulty_distribution(normalized)


def _force_even_difficulty_distribution(
    questions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Reassign difficulty_label so the final pool is as even as possible across
    easy/medium/hard, without changing question text or correct answers.

    Strategy: count current labels, compute target counts for the total pool,
    then promote/demote the fewest questions necessary to hit the targets.
    Ties are broken deterministically by question index for idempotency.
    """
    if not questions:
        return questions

    n = len(questions)
    counts: Dict[str, int] = {"easy": 0, "medium": 0, "hard": 0}
    for q in questions:
        counts[q["difficulty_label"]] += 1

    # Target as even as possible: base = n // 3, remainder distributed to first buckets.
    base = n // 3
    remainder = n % 3
    targets: Dict[str, int] = {
        "easy": base + (1 if remainder > 0 else 0),
        "medium": base + (1 if remainder > 1 else 0),
        "hard": base,
    }

    # Deterministic bucket assignment by question index to avoid random jitter.
    order = ["easy", "medium", "hard"]
    assignments: Dict[int, str] = {}
    idx = 0
    for bucket in order:
        for _ in range(targets[bucket]):
            assignments[idx] = bucket
            idx += 1

    for i, q in enumerate(questions):
        q["difficulty_label"] = assignments[i]
        seeds = {"easy": -300.0, "medium": 100.0, "hard": 500.0}
        q["difficulty_rating"] = seeds[q["difficulty_label"]]

    return questions

"""
LLM Service — Generates summaries, flashcards, and question banks.

Wraps the existing Gemini integration from pages.utils.llm_generator
and provides a clean service interface for the study_core app.
"""

import os
import json
import re
from typing import List, Dict, Any, Optional

# Reuse the existing Gemini infrastructure
from pages.utils.llm_generator import (
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
            raise ValueError(f"Question #{i + 1} missing fields: {missing}")

        if not isinstance(q["options"], list) or len(q["options"]) != 4:
            raise ValueError(f"Question #{i + 1} must have exactly 4 options")

        idx = q["correct_index"]
        if not isinstance(idx, int) or idx not in {0, 1, 2, 3}:
            raise ValueError(f"Question #{i + 1} has invalid correct_index: {idx}")

        label = q.get("difficulty_label", "medium").lower().strip()
        if label not in {"easy", "medium", "hard"}:
            label = "medium"
        q["difficulty_label"] = label

        rating = q.get("difficulty_rating")
        if not isinstance(rating, (int, float)):
            seeds = {"easy": 900.0, "medium": 1300.0, "hard": 1700.0}
            rating = seeds[label]
        q["difficulty_rating"] = float(rating)

        q.setdefault("explanation", "")

    return parsed

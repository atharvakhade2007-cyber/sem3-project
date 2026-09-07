"""
Daily Quiz Service — Adaptive GK & Current Affairs generation via Gemini.

Quiz composition per calendar day (one DailyQuiz row):
- 5 Current Affairs questions (category='current_affairs') — universally
  identical for every user that day.
- 15 General Knowledge questions (category='gk'), 5 per difficulty
  tier (easy / medium / hard). The serving endpoint returns the 5 GK
  questions matching the user's optimal tier, computed by the 1PL IRT
  engine (see services/irt_engine.py) from their persistent Elo skill
  rating so their expected success rate stays near 70%.

The legacy rule-based tier promotion/demotion (≥4/5 → up, ≤1/5 → down)
has been replaced: after each completion, the user's Elo is nudged by the
online IRT update for every answered GK question, so the next day's tier
naturally tracks their performance.

Uses structured Gemini output (response_schema) for robust JSON parsing.
"""

from datetime import date
from typing import List, Dict, Any, Optional

from django.db import transaction

from .llm_generator import _call_gemini_structured

from study_core.models import DailyQuiz, DailyQuestion, UserProfile
from study_core.services import irt_engine as irt

# ─── Composition constants ─────────────────────────────────
CA_COUNT = 5                 # Current Affairs questions (universal)
GK_PER_TIER = 5              # GK questions per difficulty tier
TIER_ORDER = ['easy', 'medium', 'hard']

# Online learning rate applied to the user's Elo per answered GK question
# after a daily quiz is completed (drives tomorrow's tier via θ).
GK_LEARNING_RATE = 0.15


# ─── Gemini JSON schema (structured output) ─────────────────

_QUESTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "question_text": {"type": "STRING"},
        "options": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "minItems": 4,
            "maxItems": 4,
        },
        "correct_index": {"type": "INTEGER"},
        "explanation": {"type": "STRING"},
        "category": {
            "type": "STRING",
            "enum": ["current_affairs", "gk"],
        },
        "difficulty_tier": {
            "type": "STRING",
            "enum": ["easy", "medium", "hard"],
        },
    },
    "required": [
        "question_text", "options", "correct_index", "explanation",
        "category", "difficulty_tier",
    ],
}

DAILY_QUIZ_SCHEMA = {
    "type": "ARRAY",
    "items": _QUESTION_SCHEMA,
}


def generate_daily_quiz_questions(
    target_date: date,
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Generate 20 questions for one calendar day: 5 Current Affairs + 15 GK
    (5 easy, 5 medium, 5 hard), in a single Gemini structured-output call.

    Returns a list of dicts, each with keys:
    - question_text (str)
    - options (list of exactly 4 strings)
    - correct_index (int 0-3)
    - explanation (str)
    - category ('current_affairs' | 'gk')
    - difficulty_tier ('easy' | 'medium' | 'hard', or None for Current Affairs)
    """
    date_str = target_date.strftime("%B %d, %Y")

    prompt = f"""You are an expert quiz maker for an EdTech daily quiz app.

Today's quiz date is {date_str}. Generate EXACTLY 20 high-quality multiple-choice questions as a JSON array:

A) 5 "Current Affairs" questions (category "current_affairs"):
   - Strictly focused on RECENT global/national news from the last ~7 days before {date_str}:
     world news, geopolitics, science & technology, sports, awards, economy, environment.
   - They must be factual, current, and verifiable. Do not use evergreen trivia here.

B) 15 "General Knowledge" (GK) questions (category "gk"):
   - Classic GK across history, geography, science, culture, books, etc.
   - Exactly 5 must be difficulty_tier "easy", exactly 5 "medium", exactly 5 "hard".
   - Easy = common knowledge; Medium = requires some study; Hard = obscure/advanced.

RULES FOR EVERY QUESTION:
1. "question_text": a clear, unambiguous question.
2. "options": EXACTLY 4 distinct plausible strings (A, B, C, D). No obviously wrong distractors.
3. "correct_index": integer 0-3 pointing at the correct option.
4. "explanation": 1-2 concise factual sentences explaining why the answer is right.
5. "category": "current_affairs" or "gk" as specified above.
6. "difficulty_tier": for GK questions use exactly "easy"/"medium"/"hard" per the split above.
   For current_affairs questions set it to "medium" as a placeholder (it is ignored).

Output ONLY the JSON array. No commentary, no markdown."""
    raw_data = _call_gemini_structured(prompt, DAILY_QUIZ_SCHEMA, api_key=api_key)

    if not isinstance(raw_data, list):
        raise ValueError("Expected a JSON array from Gemini for daily quiz generation")

    # Validate shape and normalize
    normalized: List[Dict[str, Any]] = []
    for i, q in enumerate(raw_data):
        if not isinstance(q, dict):
            raise ValueError(f"Question #{i + 1} is not an object")

        required = {"question_text", "options", "correct_index", "explanation",
                    "category", "difficulty_tier"}
        missing = required - set(q.keys())
        if missing:
            raise ValueError(f"Question #{i + 1} missing fields: {sorted(missing)}")

        if not isinstance(q["options"], list) or len(q["options"]) != 4:
            raise ValueError(f"Question #{i + 1} must have exactly 4 options")

        idx = q["correct_index"]
        if not isinstance(idx, int) or idx not in {0, 1, 2, 3}:
            raise ValueError(f"Question #{i + 1} has invalid correct_index: {idx}")

        category = str(q["category"]).strip().lower()
        if category not in {"current_affairs", "gk"}:
            raise ValueError(f"Question #{i + 1} has invalid category: {category}")

        tier = str(q.get("difficulty_tier", "")).strip().lower()
        if tier not in TIER_ORDER:
            raise ValueError(f"Question #{i + 1} has invalid difficulty_tier: {tier}")

        normalized.append({
            "question_text": q["question_text"],
            "options": q["options"],
            "correct_index": idx,
            "explanation": q.get("explanation", ""),
            "category": category,
            # difficulty_tier only meaningful for GK; CA is always tier-less
            "difficulty_tier": tier if category == "gk" else None,
        })

    # Verify composition: 5 CA + 15 GK split 5/5/5
    ca_count = sum(1 for q in normalized if q["category"] == "current_affairs")
    gk_counts = {
        tier: sum(1 for q in normalized if q["category"] == "gk" and q["difficulty_tier"] == tier)
        for tier in TIER_ORDER
    }

    if ca_count != CA_COUNT:
        raise ValueError(
            f"Expected {CA_COUNT} Current Affairs questions, got {ca_count}"
        )

    for tier in TIER_ORDER:
        if gk_counts[tier] != GK_PER_TIER:
            raise ValueError(
                f"Expected {GK_PER_TIER} GK questions for tier '{tier}', got {gk_counts[tier]}"
            )

    return normalized


# ─── Persistence ─────────────────────────────────────────────


def _order_questions(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Order questions: Current Affairs 1-5, then GK grouped easy→medium→hard."""
    ca = [q for q in questions if q["category"] == "current_affairs"]
    gk: List[Dict[str, Any]] = []
    for tier in TIER_ORDER:
        gk.extend(
            q for q in questions
            if q["category"] == "gk" and q["difficulty_tier"] == tier
        )
    return ca + gk


def create_daily_quiz_for_date(
    target_date: date,
    api_key: Optional[str] = None,
) -> DailyQuiz:
    """
    Generate and persist the daily quiz for `target_date`.

    Raises ValueError if a quiz already exists for that date — callers should
    use ensure_daily_quiz_for_date() for idempotent behaviour.
    """
    if DailyQuiz.objects.filter(date=target_date).exists():
        raise ValueError(f"Quiz for {target_date} already exists")

    questions_data = generate_daily_quiz_questions(target_date, api_key=api_key)
    ordered = _order_questions(questions_data)

    with transaction.atomic():
        quiz = DailyQuiz.objects.create(
            date=target_date,
            title=f'Daily GK & Current Affairs — {target_date.strftime("%B %d, %Y")}',
        )
        DailyQuestion.objects.bulk_create([
            DailyQuestion(
                quiz=quiz,
                question_text=q["question_text"],
                options=q["options"],
                correct_index=q["correct_index"],
                explanation=q.get("explanation", ""),
                category=q["category"],
                difficulty_tier=q["difficulty_tier"],
                order=i + 1,
            )
            for i, q in enumerate(ordered)
        ])

    return quiz


def ensure_daily_quiz_for_date(
    target_date: date,
    api_key: Optional[str] = None,
) -> DailyQuiz:
    """Return the quiz for `target_date`, generating + persisting it if missing.

    A stored quiz with fewer than 20 questions is the result of a partially
    failed earlier generation (e.g. an LLM rate limit mid-run). Such broken
    quizzes are deleted and regenerated so users never see a truncated quiz.
    """
    existing = DailyQuiz.objects.filter(date=target_date).first()
    if existing is not None:
        if existing.questions.count() < 20:
            # Partial generation — discard and rebuild.
            existing.delete()
        else:
            return existing
    return create_daily_quiz_for_date(target_date, api_key=api_key)


# ─── Serving & gamification helpers ─────────────────────────


def questions_for_user(quiz: DailyQuiz, tier: str) -> List[DailyQuestion]:
    """
    The 10 questions a user sees: 5 universal Current Affairs + the 5 GK
    questions matching their tier. Ordered CA first, then GK.
    """
    from django.db.models import Q

    return list(
        quiz.questions.filter(
            Q(category=DailyQuestion.Category.CURRENT_AFFAIRS)
            | Q(category=DailyQuestion.Category.GK, difficulty_tier=tier)
        ).order_by('order')
    )


def select_gk_tier(profile: UserProfile) -> str:
    """Optimal GK tier for a profile, from their Elo via the IRT engine.

    θ = f(elo); the tier whose expected success rate is closest to the 0.70
    target wins (see irt_engine.select_tier_for_ability).
    """
    theta = irt.ability_from_elo(profile.elo_rating)
    return irt.select_tier_for_ability(theta)


def served_questions_for_user(quiz: DailyQuiz, profile: UserProfile) -> List[DailyQuestion]:
    """
    The 10 questions to show this user, with the tier decided by their Elo.

    Also persists the chosen tier back onto ``profile.gk_skill_tier`` so the
    UI badge / leaderboard reflect the current adaptive state. The tier is
    stable within a single day unless the user's Elo changes (it cannot
    mid-day), so the same call is safe from the /today/, /check/ and
    /submit/ endpoints.
    """
    tier = select_gk_tier(profile)
    if profile.gk_skill_tier != tier:
        profile.gk_skill_tier = tier
        profile.save(update_fields=['gk_skill_tier'])
    return questions_for_user(quiz, tier)


class QuizAnswerConflict(Exception):
    """Raised when a user tries to change a locked (already answered) question."""


def record_daily_quiz_answer(quiz, user, question, selected_index):
    """
    Grade and lock a single daily-quiz answer for ``user`` on ``question``.

    Idempotent: replaying the same selection returns the existing row without
    creating a duplicate. Attempting a different selection on an answered
    question raises ``QuizAnswerConflict`` — the answer is locked the moment it
    is revealed, which is what keeps instant feedback fair (one attempt per
    question, no retry-after-seeing-the-answer).

    Returns the DailyQuizAnswer row.
    """
    from study_core.models import DailyQuizAnswer

    existing = DailyQuizAnswer.objects.filter(
        user=user, quiz=quiz, question=question
    ).first()
    if existing is not None:
        if existing.selected_index == selected_index:
            return existing
        raise QuizAnswerConflict(
            'This question is already answered and locked.'
        )

    is_correct = selected_index == question.correct_index
    return DailyQuizAnswer.objects.create(
        user=user,
        quiz=quiz,
        question=question,
        selected_index=selected_index,
        is_correct=is_correct,
    )


def recorded_answers_for_user(quiz, user):
    """All locked answers for ``user`` on ``quiz`` (newest-last), question joined."""
    from study_core.models import DailyQuizAnswer

    return list(
        DailyQuizAnswer.objects.filter(user=user, quiz=quiz)
        .select_related('question')
        .order_by('created_at')
    )


def apply_quiz_completion(
    profile: UserProfile,
    gk_answers: List[tuple],
    completed_date,
) -> None:
    """
    Update a profile after a daily quiz submission, in place (no save):

    1. Streak: if the user also completed yesterday, current_streak += 1;
       otherwise the streak resets to 1. longest_streak is kept in sync.
    2. Adaptive ability: for every answered GK question, advance the
       persistent Elo rating by the online IRT update
       (θ ← θ + LR·(S − P), converted back to Elo). Because the next day's
       tier is derived from Elo, this is what makes tomorrow's quiz reflect
       today's performance — replacing the old rule-based promotion/demotion.

    Args:
        gk_answers: List of (tier, is_correct) tuples, one per answered
            GK question (excludes universal Current-Affairs items).
    """
    from datetime import timedelta

    today = completed_date
    last = profile.last_quiz_completed_date

    if last == today:
        # Completed today already (duplicate) — do not touch the streak.
        pass
    elif last == today - timedelta(days=1):
        profile.current_streak += 1
    else:
        # No completion yesterday → consecutive-day streak broken, restart at 1.
        profile.current_streak = 1

    profile.longest_streak = max(profile.longest_streak, profile.current_streak)
    profile.last_quiz_completed_date = today

    # Adaptive ability: sequential online IRT update per GK answer, folded
    # back into the persistent Elo rating (which drives tomorrow's tier).
    for tier, is_correct in gk_answers:
        theta = irt.ability_from_elo(profile.elo_rating)
        b = irt.difficulty_from_tier(tier)
        theta_new = irt.update_theta(
            theta, b, is_correct, learning_rate=GK_LEARNING_RATE
        )
        profile.elo_rating = irt.elo_from_ability(theta_new)

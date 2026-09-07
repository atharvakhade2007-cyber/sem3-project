"""Two-tier adaptive assessment persona engine for the PDF quiz workflow.

 Responsibilities
 ───────────────
 1. Cold-start persona selection for users with fewer than 3 completed quizzes.
 2. Macro persona prediction from the pre-trained RandomForest in model.pkl
    once the user has enough quiz history (Phase 2 in the spec).
 3. Micro adaptive sub-tier selection within the user's persona tier
    (Phase 3 in the spec) — Easy/Medium/Hard promotion/demotion on streaks.
 4. Elo clamping for the PDF assessment path (never negative, minimum 100.0).

 This module does NOT replace the existing AdaptiveEloEngine or IRT logic.
 It only decides the starting persona, the first sub-tier, and the promotion
 rules; the existing engine still computes the per-answer Elo/IRT updates.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone

from study_core.models import (
    Question,
    QuizSessionState,
    TestSession,
    UserProfile,
)
from study_core.services.adaptive_engine import AdaptiveEloEngine

PERSONA_CHOICES = ('Beginner', 'Intermediate', 'Advanced')
SUB_TIER_ORDER = ('Easy', 'Medium', 'Hard')

PERSONA_DEFAULTS = {
    'Beginner': 'Easy',
    'Intermediate': 'Medium',
    'Advanced': 'Hard',
}

# Minimum Elo for the PDF assessment path (never goes below this).
MIN_PDF_ELO = 100.0


def clamp_pdf_elo(elo: float) -> float:
    """Enforce the non-negative, 100+ Elo contract for the PDF assessment path."""
    return max(MIN_PDF_ELO, float(elo))


def determine_and_predict_persona(
    profile: UserProfile,
) -> Tuple[str, Dict[str, float]]:
    """
    Two-tier persona selection for the PDF quiz workflow.

    Phase 1 (cold start): if the user has completed fewer than 3 quizzes,
    bypass ML and assign the default persona ('Intermediate').

    Phase 2 (macro persona prediction): otherwise, load model.pkl and predict
    the initial student level from the cumulative performance metrics on the
    profile.

    Returns (persona_tier, probabilities).

    The result is persisted to profile.persona_tier so every surface
    (profile header, overview, analytics, leaderboards) reads the SAME
    ML-predicted level instead of diverging hardcoded/stale values.
    """
    completed = profile.total_quizzes_completed
    if completed < 3:
        # Cold start default.
        persona = 'Intermediate'
        probs = {
            'Beginner': 0.33,
            'Intermediate': 0.34,
            'Advanced': 0.33,
        }
        _persist_persona(profile, persona)
        return persona, probs

    persona, probs = predict_initial_persona(profile)
    _persist_persona(profile, persona)
    return persona, probs


def _persist_persona(profile: UserProfile, persona: str) -> None:
    """Persist the current persona prediction to the UserProfile.

    Keeps profile.persona_tier in sync with the prediction system so the
    analytics endpoint and the profile API expose one authoritative value.
    No-op when the tier is already current, to avoid redundant writes.
    """
    if persona not in PERSONA_CHOICES or profile.persona_tier == persona:
        return
    profile.persona_tier = persona
    profile.persona_predicted_at = timezone.now()
    profile.save(update_fields=['persona_tier', 'persona_predicted_at'])


def predict_initial_persona(profile: UserProfile) -> Tuple[str, Dict[str, float]]:
    """
    Phase 2 macro persona prediction.

    Loads the pre-trained model.pkl and predicts the initial student level
    from the current cumulative performance metrics stored on the profile.

    Returns (persona, probabilities).
    """
    from ml.prediction.predict import predict_student_level

    features = _build_profile_feature_vector(profile)
    persona, probs = predict_student_level(features)
    if persona not in PERSONA_CHOICES:
        # Fail-safe: if the model somehow returns an unexpected class, fall
        # back to the profile's existing persona.
        persona = profile.persona_tier
    return persona, probs


def initial_sub_tier_for_persona(persona_tier: str) -> str:
    """Return the starting sub-tier for a freshly predicted persona.

    Spec: start from the Medium sub-band of the user's predicted persona.
    We map Beginner->Easy, Intermediate->Medium, Advanced->Hard so the first
    question is representative of the predicted tier.
    """
    return PERSONA_DEFAULTS.get(persona_tier, 'Medium')


def _build_profile_feature_vector(profile: UserProfile) -> Dict[str, Any]:
    """
    Build the 13-feature vector expected by model.pkl from the UserProfile.

    Feature order matches model.pkl.features:
      quiz_attempts, questions_attempted, correct_answers, wrong_answers,
      accuracy, avg_time_per_question, easy_correct, medium_correct,
      hard_correct, previous_avg_score, current_elo_rating,
      question_difficulty_rating, total_answered
    """
    total = profile.total_questions_answered
    correct = profile.correct_answers
    wrong = profile.wrong_answers
    attempted = profile.questions_attempted

    accuracy = profile.accuracy
    if attempted > 0 and not math.isfinite(accuracy):
        accuracy = 0.0
    if attempted > 0 and accuracy == 0.0 and (correct + wrong) > 0:
        # Derive accuracy from counts if not already set.
        accuracy = correct / max(attempted, 1)

    avg_time = profile.avg_time_per_question
    if not math.isfinite(avg_time):
        avg_time = 0.0

    return {
        'quiz_attempts': int(profile.quiz_attempts),
        'questions_attempted': int(attempted),
        'correct_answers': int(correct),
        'wrong_answers': int(wrong),
        'accuracy': float(accuracy),
        'avg_time_per_question': float(avg_time),
        'easy_correct': int(profile.easy_correct),
        'medium_correct': int(profile.medium_correct),
        'hard_correct': int(profile.hard_correct),
        'previous_avg_score': float(profile.previous_avg_score),
        'current_elo_rating': float(profile.current_elo_rating),
        'question_difficulty_rating': float(profile.question_difficulty_rating),
        'total_answered': int(total),
    }


def select_next_sub_tier_from_state(
    persona_tier: str,
    active_sub_tier: Optional[str] = None,
    consecutive_correct: int = 0,
    consecutive_wrong: int = 0,
) -> str:
    """
    Phase 3 micro-adaptive sub-tier selection within a persona tier.

    Rules (from spec):
      - Start serving from the Medium sub-band of the user's predicted persona.
        (For persona Tier X, the starting sub-tier is PERSONA_DEFAULTS[Tier] —
         Beginner->Easy, Intermediate->Medium, Advanced->Hard.)
      - If 2 consecutive correct -> promote one sub-tier (Easy->Medium, Medium->Hard).
      - If 2 consecutive wrong -> demote one sub-tier (Hard->Medium, Medium->Easy).
      - Clamp strictly between Easy and Hard within the persona.

    The "start from Medium sub-band" requirement is interpreted as: the very
    first sub-tier shown to a freshly predicted persona is PERSONA_DEFAULTS[tier].
    After that, promotion/demotion rules apply on streaks.
    """
    if persona_tier not in PERSONA_CHOICES:
        persona_tier = 'Intermediate'

    # Determine starting tier if no active sub-tier is provided.
    if active_sub_tier is None:
        active_sub_tier = PERSONA_DEFAULTS.get(persona_tier, 'Medium')

    if active_sub_tier not in SUB_TIER_ORDER:
        active_sub_tier = PERSONA_DEFAULTS.get(persona_tier, 'Medium')

    # Apply streak-driven promotion/demotion.
    current_idx = SUB_TIER_ORDER.index(active_sub_tier)

    if consecutive_correct >= 2:
        current_idx = min(len(SUB_TIER_ORDER) - 1, current_idx + 1)
    elif consecutive_wrong >= 2:
        current_idx = max(0, current_idx - 1)

    return SUB_TIER_ORDER[current_idx]


def select_question_for_sub_tier_from_state(
    session: TestSession,
    state: QuizSessionState,
    questions: List[Question],
) -> Optional[Question]:
    """
    Pick the best next question from `questions` that:
      - Has not already been served in this session.
      - Matches the current active sub-tier's difficulty band.
      - Is the closest ZPD match among those, using AdaptiveEloEngine.

    If no question exists in the current sub-tier, fall back to the closest
    ZPD question across all remaining questions so the session never stalls.
    """
    served = set(state.served_question_ids or [])
    available = [q for q in questions if str(q.id) not in served]
    if not available:
        return None

    sub_tier = state.active_sub_tier
    band_min, band_max = _sub_tier_band(sub_tier)

    def in_band(q: Question) -> bool:
        r = q.difficulty_rating
        return band_min <= r <= band_max

    candidates = [q for q in available if in_band(q)]
    if not candidates:
        candidates = available

    # Use the existing adaptive engine to pick the optimal ZPD question.
    # We only pass difficulty_rating so the existing select_next_question logic
    # selects the closest-to-target question among candidates.
    best = AdaptiveEloEngine.select_next_question(
        session.start_elo,
        [{'id': q.id, 'difficulty_rating': q.difficulty_rating} for q in candidates],
    )
    if best is None:
        return None

    for q in candidates:
        if str(q.id) == str(best['id']):
            return q
    return candidates[0]


def _sub_tier_band(sub_tier: str) -> Tuple[float, float]:
    """Return (min_rating, max_rating) assumed for a given sub-tier label."""
    bands = {
        'Easy': (-400.0, -100.0),
        'Medium': (-100.0, 300.0),
        'Hard': (300.0, 800.0),
    }
    return bands.get(sub_tier, (-100.0, 300.0))


def select_next_question_for_session(
    session: TestSession,
    state: Optional[QuizSessionState],
    questions: List[Question],
    answered_ids,
) -> Tuple[Optional[Question], str, str]:
    """
    Select the next question for a session using the persona sub-tier logic.

    Returns (question, active_sub_tier, transition_reason).
    If no question remains, returns (None, current_sub_tier, 'no_questions').
    """
    if state is None:
        sub_tier = initial_sub_tier_for_persona(session.persona_tier)
        answered = {str(a) for a in (answered_ids or [])}
        candidates = [q for q in questions if str(q.id) not in answered]
        if not candidates:
            return None, sub_tier, 'no_questions'
        best = AdaptiveEloEngine.select_next_question(
            session.start_elo,
            [{'id': q.id, 'difficulty_rating': q.difficulty_rating} for q in candidates],
        )
        if best is None:
            return None, sub_tier, 'no_questions'
        for q in candidates:
            if str(q.id) == str(best['id']):
                return q, sub_tier, 'initial'
        return candidates[0], sub_tier, 'initial'

    # A question counts as served if it was tracked in the session state OR
    # already answered (recorded in SessionResponse). This guarantees the same
    # question is never served twice within a session.
    answered = {str(a) for a in (answered_ids or [])}
    served = set(state.served_question_ids or []) | answered
    available = [q for q in questions if str(q.id) not in served]
    if not available:
        return None, state.active_sub_tier, 'no_questions'

    sub_tier = state.active_sub_tier
    band_min, band_max = _sub_tier_band(sub_tier)

    def in_band(q: Question) -> bool:
        r = q.difficulty_rating
        return band_min <= r <= band_max

    candidates = [q for q in available if in_band(q)]
    if not candidates:
        candidates = available

    best = AdaptiveEloEngine.select_next_question(
        session.start_elo,
        [{'id': q.id, 'difficulty_rating': q.difficulty_rating} for q in candidates],
    )
    if best is None:
        return None, sub_tier, 'no_questions'

    for q in candidates:
        if str(q.id) == str(best['id']):
            _record_served(state, q)
            return q, sub_tier, 'held'
    chosen = candidates[0]
    _record_served(state, chosen)
    return chosen, sub_tier, 'held'


def _record_served(state: Optional[QuizSessionState], question: Question) -> None:
    """Persist the chosen question id so it can never be served again."""
    if state is None:
        return
    served = list(state.served_question_ids or [])
    sid = str(question.id)
    if sid not in served:
        served.append(sid)
        state.served_question_ids = served
        state.save(update_fields=['served_question_ids'])


def normalize_question_key(text: str) -> str:
    """Canonical key for duplicate detection (letters/digits only)."""
    return re.sub(r'[^a-z0-9]+', '', (text or '').lower())


def dedupe_bank(questions: List[Question]) -> List[Question]:
    """Remove duplicate questions from a bank without deleting DB rows.

    Banks generated before strict LLM-side dedup may contain repeated
    questions; a session must only ever see each question once.
    """
    seen = set()
    unique = []
    for q in questions:
        key = normalize_question_key(q.question_text)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(q)
    return unique


def update_session_state_after_answer(
    state: QuizSessionState,
    is_correct: bool,
) -> Tuple[str, str]:
    """
    Update the session state after a single answer and return the new sub-tier.

    Rules (Phase 3):
      - On correct: increment consecutive_correct, reset consecutive_wrong.
      - On wrong: increment consecutive_wrong, reset consecutive_correct.
      - If consecutive_correct >= 2: promote sub-tier, reset counter.
      - If consecutive_wrong >= 2: demote sub-tier, reset counter.
      - Clamp strictly between Easy and Hard.

    Returns (new_sub_tier, transition_reason).
    """
    if is_correct:
        state.consecutive_correct = (state.consecutive_correct or 0) + 1
        state.consecutive_wrong = 0
    else:
        state.consecutive_wrong = (state.consecutive_wrong or 0) + 1
        state.consecutive_correct = 0

    new_sub_tier = select_next_sub_tier_from_state(
        persona_tier=state.session.persona_tier if hasattr(state.session, 'persona_tier') else 'Intermediate',
        active_sub_tier=state.active_sub_tier,
        consecutive_correct=state.consecutive_correct,
        consecutive_wrong=state.consecutive_wrong,
    )

    transition = ''
    if new_sub_tier != state.active_sub_tier:
        if state.consecutive_correct >= 2:
            transition = 'promoted'
        elif state.consecutive_wrong >= 2:
            transition = 'demoted'
        state.active_sub_tier = new_sub_tier
        state.save(update_fields=['active_sub_tier', 'consecutive_correct', 'consecutive_wrong'])
        # Reset streak counters after a transition.
        state.consecutive_correct = 0
        state.consecutive_wrong = 0
        state.save(update_fields=['consecutive_correct', 'consecutive_wrong'])
    else:
        state.save(update_fields=['consecutive_correct', 'consecutive_wrong'])

    return new_sub_tier, transition


def select_first_question(
    session: TestSession,
    state: QuizSessionState,
    questions: List[Question],
) -> Tuple[Optional[Question], str, str]:
    """
    Select the first question for a freshly started session.

    Returns (question, active_sub_tier, reason).
    """
    sub_tier = initial_sub_tier_for_persona(session.persona_tier)
    state.active_sub_tier = sub_tier
    state.save(update_fields=['active_sub_tier'])

    candidates = [q for q in questions if str(q.id) not in state.served_question_ids]
    if not candidates:
        return None, sub_tier, 'no_questions'

    best = AdaptiveEloEngine.select_next_question(
        session.start_elo,
        [{'id': q.id, 'difficulty_rating': q.difficulty_rating} for q in candidates],
    )
    if best is None:
        return None, sub_tier, 'no_questions'

    for q in candidates:
        if str(q.id) == str(best['id']):
            state.served_question_ids.append(str(q.id))
            state.save(update_fields=['served_question_ids'])
            return q, sub_tier, 'initial'

    chosen = candidates[0]
    state.served_question_ids.append(str(chosen.id))
    state.save(update_fields=['served_question_ids'])
    return chosen, sub_tier, 'initial'


@transaction.atomic
def finalize_session_metrics(
    session: TestSession,
    profile: UserProfile,
    responses,
) -> None:
    """
    After a session is completed, persist cumulative metrics back to the
    profile so the next ML prediction has up-to-date features.

    Only questions actually answered are counted; generated-but-unused pool
    questions do not inflate the metrics.
    """
    total = responses.count()
    correct = responses.filter(is_correct=True).count()
    wrong = total - correct

    easy = medium = hard = 0
    time_sum = 0.0
    difficulty_sum = 0.0
    answered_count = 0

    for resp in responses.select_related('question'):
        q = resp.question
        label = q.difficulty_label
        if label == 'easy':
            easy += 1
        elif label == 'medium':
            medium += 1
        elif label == 'hard':
            hard += 1

        time_sum += resp.time_taken_sec or 0.0
        difficulty_sum += q.difficulty_rating
        answered_count += 1

    profile.quiz_attempts += 1
    profile.questions_attempted = (profile.questions_attempted or 0) + total
    profile.correct_answers = (profile.correct_answers or 0) + correct
    profile.wrong_answers = (profile.wrong_answers or 0) + wrong
    profile.easy_correct = (profile.easy_correct or 0) + easy
    profile.medium_correct = (profile.medium_correct or 0) + medium
    profile.hard_correct = (profile.hard_correct or 0) + hard

    if total > 0:
        profile.accuracy = correct / total
        profile.avg_time_per_question = time_sum / total
        profile.question_difficulty_rating = difficulty_sum / total
    else:
        profile.accuracy = 0.0
        profile.avg_time_per_question = 0.0
        profile.question_difficulty_rating = 0.0

    # previous_avg_score is the running average of session accuracy percentages.
    total_answered_before = profile.total_answered
    new_answered = total_answered_before + total
    old_pct = profile.previous_avg_score
    if new_answered > 0 and total > 0:
        profile.previous_avg_score = (
            (old_pct * max(total_answered_before, 0)) + (correct / total * 100)
        ) / new_answered
    elif total > 0:
        profile.previous_avg_score = correct / total * 100
    else:
        profile.previous_avg_score = 0.0

    profile.total_answered = new_answered
    profile.total_questions_answered = (
        (profile.total_questions_answered or 0) + total
    )

    # Keep current_elo_rating in sync with the latest profile Elo for the
    # PDF assessment path, clamped to the 100+ floor.
    profile.current_elo_rating = clamp_pdf_elo(profile.elo_rating)

    profile.save(update_fields=[
        'quiz_attempts',
        'questions_attempted',
        'correct_answers',
        'wrong_answers',
        'accuracy',
        'avg_time_per_question',
        'easy_correct',
        'medium_correct',
        'hard_correct',
        'previous_avg_score',
        'current_elo_rating',
        'question_difficulty_rating',
        'total_answered',
        'total_questions_answered',
    ])

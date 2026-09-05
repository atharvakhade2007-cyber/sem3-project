"""
student_features.py — Bridge between Django's real user data and the ML model.

Aggregates a user's actual performance history (SessionResponse rows,
DailyQuizAnswer rows, UserProfile counters) into the EXACT 13-feature vector
expected by ml/prediction/predict.py, then calls `predict_student_level()` to
obtain the student's INITIAL level (Beginner / Intermediate / Advanced).

The ML prediction is used ONLY to seed the first question's difficulty
(through `initial_seed_elo`). After the quiz starts, the existing
AdaptiveEloEngine / IRT engine take over entirely — this module never
overrides real-time Elo/IRT updates and never retrains the model.

Design notes:
- All ML imports are LAZY (inside functions) so the Django app starts and
  serves quizzes even if the ML dependencies or model.pkl are unavailable.
- Missing / corrupt model.pkl degrades gracefully: prediction returns None
  and the caller falls back to the user's stored Elo (original behaviour).
"""

from django.db.models import Avg, Count

from study_core.models import (
    UserProfile,
    SessionResponse,
    DailyQuizAnswer,
    DailyQuizSession,
    TestSession,
)
from study_core.services.adaptive_engine import AdaptiveEloEngine

# Seed Elo per predicted level — matches the project's own difficulty seeds
# (easy -300 / medium 100 / hard 500 on the 0-based Elo scale).
LEVEL_SEED_ELO = {
    "Beginner": -300.0,
    "Intermediate": 100.0,
    "Advanced": 500.0,
}

# Sensible neutral defaults for a brand-new user with no answer history yet.
# These sit inside the training distribution so the ML prediction is
# meaningful instead of degenerate.
_DEFAULTS = {
    "quiz_attempts": 1,
    "questions_attempted": 10,
    "correct_answers": 7,
    "wrong_answers": 3,
    "accuracy": 0.70,
    "avg_time_per_question": 35.0,
    "easy_correct": 3,
    "medium_correct": 3,
    "hard_correct": 1,
    "previous_avg_score": 70.0,
    "current_elo_rating": 0.0,
    "question_difficulty_rating": 0.0,
    "total_answered": 0,
}

# ─── Feature aggregation ──────────────────────────────────────


def _difficulty_label_from_rating(rating: float) -> str:
    """easy/medium/hard from an Elo difficulty rating (project mapping)."""
    return AdaptiveEloEngine.get_difficulty_label(rating)


def build_student_features(user) -> dict:
    """
    Aggregate a user's real performance history into the 13 ML features.

    The returned dict always contains exactly the 13 feature keys, in any
    order (predict.py reorders them internally). Values are floats/ints.

    Mapping from actual DB data:
      quiz_attempts            → completed adaptive TestSessions + DailyQuizSessions
      questions_attempted      → SessionResponse count + DailyQuizAnswer count
      correct_answers          → correct answers across both flows
      wrong_answers            → attempted − correct
      accuracy                 → correct / attempted
      avg_time_per_question    → mean SessionResponse.time_taken_sec
      easy/medium/hard_correct → correct answers bucketed by question difficulty
      previous_avg_score       → mean % (daily score×10, adaptive accuracy)
      current_elo_rating       → UserProfile.elo_rating
      question_difficulty_rating → mean difficulty_rating of answered questions
      total_answered           → UserProfile.total_questions_answered
    """
    profile, _ = UserProfile.objects.get_or_create(user=user)
    features = dict(_DEFAULTS)
    features["current_elo_rating"] = float(profile.elo_rating)
    features["total_answered"] = int(profile.total_questions_answered)

    adaptive_responses = list(
        SessionResponse.objects.filter(session__user=user)
        .select_related("question")
    )
    daily_answers = list(
        DailyQuizAnswer.objects.filter(user=user).select_related("question")
    )

    attempted = len(adaptive_responses) + len(daily_answers)
    if attempted == 0:
        # No history — keep neutral defaults (seed Elo stays meaningful).
        return features

    correct = (
        sum(1 for r in adaptive_responses if r.is_correct)
        + sum(1 for a in daily_answers if a.is_correct)
    )
    wrong = attempted - correct

    features["questions_attempted"] = attempted
    features["correct_answers"] = correct
    features["wrong_answers"] = wrong
    features["accuracy"] = round(correct / attempted, 4)

    times = [r.time_taken_sec for r in adaptive_responses if r.time_taken_sec > 0]
    if times:
        features["avg_time_per_question"] = round(sum(times) / len(times), 2)

    easy_correct = medium_correct = hard_correct = 0
    ratings = []
    for r in adaptive_responses:
        if not r.is_correct:
            continue
        ratings.append(float(r.question.difficulty_rating))
        label = _difficulty_label_from_rating(r.question.difficulty_rating)
        if label == "easy":
            easy_correct += 1
        elif label == "hard":
            hard_correct += 1
        else:
            medium_correct += 1
    for a in daily_answers:
        if not a.is_correct:
            continue
        tier = a.question.difficulty_tier
        if tier == "easy":
            easy_correct += 1
        elif tier == "hard":
            hard_correct += 1
        else:
            medium_correct += 1

    features["easy_correct"] = easy_correct
    features["medium_correct"] = medium_correct
    features["hard_correct"] = hard_correct

    if ratings:
        features["question_difficulty_rating"] = round(sum(ratings) / len(ratings), 2)

    # previous_avg_score: mean percentage across completed attempts.
    scores = []
    for sess in TestSession.objects.filter(user=user, is_completed=True):
        total = sess.responses.count()
        if total:
            ok = sess.responses.filter(is_correct=True).count()
            scores.append(round(ok / total * 100.0, 2))
    for ds in DailyQuizSession.objects.filter(user=user):
        if ds.total_time_sec is not None:
            scores.append(round(ds.score * 10.0, 2))  # score is /10 → percent
    if scores:
        features["previous_avg_score"] = round(sum(scores) / len(scores), 2)

    features["quiz_attempts"] = (
        TestSession.objects.filter(user=user, is_completed=True).count()
        + DailyQuizSession.objects.filter(user=user).count()
    )
    if features["quiz_attempts"] < 1:
        features["quiz_attempts"] = 1

    return features


# ─── Prediction wrapper ───────────────────────────────────────


def predict_initial_level(user):
    """
    Predict the student's INITIAL level from their real performance data.

    Returns:
        {"predicted_level": "Beginner"|"Intermediate"|"Advanced"|None,
         "probabilities": {...}|None,
         "features": {...}|None,
         "error": str|None}

    Never raises for missing model / missing ML deps — it returns
    predicted_level=None so callers fall back to the existing behaviour.
    """
    try:
        # Lazy import: the Django app must start even without ML packages.
        from ml.prediction.predict import predict_student_level
    except (ImportError, ModuleNotFoundError) as exc:
        return {
            "predicted_level": None,
            "probabilities": None,
            "features": None,
            "error": f"ML module unavailable: {exc}",
        }

    try:
        features = build_student_features(user)
        result = predict_student_level(features)
        return {
            "predicted_level": result.get("predicted_level"),
            "probabilities": result.get("probabilities"),
            "features": features,
            "error": None,
        }
    except (FileNotFoundError, ValueError) as exc:
        return {
            "predicted_level": None,
            "probabilities": None,
            "features": None,
            "error": str(exc),
        }


def initial_seed_elo(user) -> tuple:
    """
    Elo used to select the FIRST question, seeded by the ML-predicted level.

    Returns (seed_elo, prediction_dict). Falls back to the user's stored Elo
    when the model is unavailable — preserving the original behaviour exactly.

    This seeds ONE question only; every subsequent question is selected by
    the existing adaptive engine from live Elo/IRT state.
    """
    prediction = predict_initial_level(user)
    level = prediction.get("predicted_level")
    if level in LEVEL_SEED_ELO:
        return LEVEL_SEED_ELO[level], prediction
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return float(profile.elo_rating), prediction
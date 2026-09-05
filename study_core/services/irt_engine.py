"""
1-Parameter (Rasch) Item Response Theory engine — real-time ability estimation
and content routing.

Replaces rigid rule-based branching (e.g. ">= 4/5 correct → promote a tier")
with a clean psychometric model:

    P(correct | θ, b) = 1 / (1 + e^-(θ - b))

- θ (ability) is estimated directly from the user's persistent Elo/skill
  rating. The mapping is chosen so the IRT probability is EXACTLY the Elo
  expected score against a difficulty-0 (medium) question:

      θ = (elo - 0) · ln(10) / 400          ⟺  elo = θ · 400 / ln(10)

  Ratings are 0-based: every new user starts at 0 Elo (= neutral θ = 0).

- b (question difficulty) is calibrated by the generation prompt:
  easy = -1.0, medium = 0.0, hard = +1.0 (logit scale).

- Content routing targets the optimal learning "flow state": pick the item /
  tier whose P(correct) is closest to TARGET_SUCCESS_RATE (0.70).

- Online learning: after every response, θ ← θ + LR·(S − P). Wired into the
  daily quiz (per-completion batch) today; the PDF adaptive-test flow will
  use the same update in real time via ``select_next_question``.

All functions are pure — no database access, no side effects.
"""

import math
from typing import Dict, Any, Optional, Sequence

# ─── Calibration constants ────────────────────────────────────

ELO_MEAN = 0.0                        # Default / neutral Elo rating (0-based)
ELO_TO_THETA = math.log(10.0) / 400.0  # θ = R·ln10/400 (anchor at 0)
THETA_TO_ELO = 400.0 / math.log(10.0)  # inverse

TARGET_SUCCESS_RATE = 0.70           # Optimal learning "flow state"
DEFAULT_LEARNING_RATE = 0.15         # Online θ step (K-factor analog)

# Difficulty calibration per the Gemini generation prompt.
TIER_ORDER = ('easy', 'medium', 'hard')
TIER_DIFFICULTY = {
    'easy': -1.0,
    'medium': 0.0,
    'hard': 1.0,
}

_LOGIT_CLAMP = 36.0                  # e^±36 → P is 1.0/0.0 to double precision


# ─── Ability ↔ Elo ────────────────────────────────────────────


def ability_from_elo(elo: float) -> float:
    """Map a persistent Elo rating (0-based) to the IRT ability parameter θ.

    θ = elo · ln(10) / 400, so P(correct) on a difficulty-0 item equals the
    Elo expected score against a rating-0 opponent. A brand-new user at 0 Elo
    sits at θ = 0 (a 50/50 chance on medium items).
    """
    return (float(elo) - ELO_MEAN) * ELO_TO_THETA


def elo_from_ability(theta: float) -> float:
    """Inverse of :func:`ability_from_elo` — write θ updates back to Elo."""
    return ELO_MEAN + float(theta) * THETA_TO_ELO


# ─── Difficulty calibration ───────────────────────────────────


def difficulty_from_tier(tier: str) -> float:
    """Difficulty parameter b for a tier label (easy=−1, medium=0, hard=+1)."""
    try:
        return TIER_DIFFICULTY[tier]
    except KeyError:
        raise ValueError(f"Unknown difficulty tier: {tier!r}")


def tier_from_difficulty(b: float) -> str:
    """Nearest tier label for a difficulty parameter b."""
    best, best_dist = TIER_ORDER[0], float('inf')
    for tier in TIER_ORDER:
        dist = abs(float(b) - TIER_DIFFICULTY[tier])
        if dist < best_dist:
            best, best_dist = tier, dist
    return best


# ─── Core psychometric functions ──────────────────────────────


def p_correct(theta: float, b: float) -> float:
    """Rasch item characteristic curve: P(correct | θ, b) = σ(θ − b)."""
    x = float(theta) - float(b)
    if x >= _LOGIT_CLAMP:
        return 1.0
    if x <= -_LOGIT_CLAMP:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def expected_on_tier(theta: float, tier: str) -> float:
    """P(correct) for the user on an entire difficulty tier."""
    return p_correct(theta, difficulty_from_tier(tier))


def update_theta(
    theta: float,
    b: float,
    is_correct: bool,
    learning_rate: float = DEFAULT_LEARNING_RATE,
) -> float:
    """Online ability update after one response.

    θ′ = θ + LR · (S − P)   where S = 1 (correct) / 0 (wrong).

    A correct answer on an already-easy item barely moves θ (it was
    expected); a wrong answer on the same item moves it a lot (surprising).
    """
    s = 1.0 if is_correct else 0.0
    p = p_correct(theta, b)
    return float(theta) + learning_rate * (s - p)


# ─── Content routing ──────────────────────────────────────────


def select_tier_for_ability(
    theta: float,
    target: float = TARGET_SUCCESS_RATE,
) -> str:
    """Pick the GK tier whose difficulty keeps P(correct) closest to ``target``.

    This is the daily-quiz routing rule: the 5 GK questions served to a user
    are the pre-generated tier minimizing |P(correct) − 0.70| for their θ.
    """
    best_tier, best_dist = TIER_ORDER[0], float('inf')
    for tier in TIER_ORDER:
        dist = abs(p_correct(theta, TIER_DIFFICULTY[tier]) - target)
        if dist < best_dist:
            best_tier, best_dist = tier, dist
    return best_tier


def _question_difficulty(q: Dict[str, Any]) -> float:
    """Extract a logit-scale difficulty b from a question dict.

    Accepts either 'difficulty' (logit b, as calibrated) or
    'difficulty_rating' (legacy Elo-scale rating, converted via
    :func:`ability_from_elo`) so the PDF adaptive-test flow can reuse this
    selector against its existing question records.
    """
    if 'difficulty' in q:
        return float(q['difficulty'])
    if 'difficulty_rating' in q:
        return ability_from_elo(float(q['difficulty_rating']))
    raise ValueError(
        "Question dict needs a 'difficulty' (logit b) or "
        "'difficulty_rating' (Elo scale) key."
    )


def select_next_question(
    questions: Sequence[Dict[str, Any]],
    theta: float,
    target: float = TARGET_SUCCESS_RATE,
) -> Optional[Dict[str, Any]]:
    """Pick the next question minimizing |P(correct) − target| (flow state).

    Args:
        questions: Unanswered question dicts, each with an 'id' plus
            'difficulty' (logit b) or 'difficulty_rating' (Elo scale).
        theta: Current ability estimate.

    Returns the selected question dict, or None if the pool is empty.
    """
    if not questions:
        return None

    best_q, best_dist = None, float('inf')
    for q in questions:
        dist = abs(p_correct(theta, _question_difficulty(q)) - target)
        if dist < best_dist:
            best_q, best_dist = q, dist
    return best_q

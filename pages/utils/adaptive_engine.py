"""
Adaptive Testing Engine — Continuous Online Elo Algorithm

Implements a psychometric model with:
- Dynamic K-factor decay
- Response latency weighting
- Zone of Proximal Development targeting (65% success rate)
- Time-decay weighting for confidence calibration
"""

import math
from typing import Tuple


# ─── Constants ───────────────────────────────────────────────

# Question difficulty seeding tiers on the 0-based Elo scale. These are the
# 0-anchored equivalents of the old 1200-centered seeds (900/1300/1700): a new
# learner at 0 Elo faces easy questions at ~85% expected success, matching the
# old behaviour where a 1200-rated learner faced 900-rated easy items.
DIFFICULTY_SEEDS = {
    'easy': -300.0,
    'medium': 100.0,
    'hard': 500.0,
}

# User level bands (0-based Elo). Shared by the adaptive-test badge and any
# UI that turns a rating into a "level".
LEVEL_BANDS = (
    (0, 'Beginner'),
    (200, 'Intermediate'),
    (500, 'Advanced'),
    (900, 'Expert'),
)


def elo_level_name(elo: float) -> str:
    """Map a 0-based Elo rating to its level name.

    <200 Beginner · <500 Intermediate · <900 Advanced · 900+ Expert.
    """
    name = LEVEL_BANDS[0][1]
    for threshold, label in LEVEL_BANDS:
        if float(elo) >= threshold:
            name = label
    return name

# Target success rate (Zone of Proximal Development)
TARGET_SUCCESS_RATE = 0.65

# Question update K-factor (fixed, lower than user K)
QUESTION_K = 16.0

# User K-factor bounds
K_MIN = 16.0
K_MAX = 64.0

# Latency thresholds (seconds)
FAST_CORRECT_THRESHOLD = 15.0
SLOW_CORRECT_THRESHOLD = 60.0
SPAM_INCORRECT_THRESHOLD = 4.0

# Latency multipliers
FAST_CORRECT_BONUS = 1.15      # Quick correct = high confidence
SLOW_CORRECT_PENALTY = 0.85    # Slow correct = hesitant guess
SPAM_INCORRECT_PENALTY = 1.25  # Fast wrong = spam clicking
DEFAULT_MULTIPLIER = 1.0


# ─── Core Elo Functions ──────────────────────────────────────

def expected_win_probability(user_elo: float, question_elo: float) -> float:
    """
    Calculate expected win probability for the user.
    
    E_u = 1 / (1 + 10^((R_q - R_u) / 400))
    
    Args:
        user_elo: User's current Elo rating (R_u)
        question_elo: Question's current difficulty rating (R_q)
    
    Returns:
        Expected probability of user answering correctly (0.0 to 1.0)
    """
    exponent = (question_elo - user_elo) / 400.0
    return 1.0 / (1.0 + math.pow(10.0, exponent))


def dynamic_k_factor(total_answered: int) -> float:
    """
    Calculate dynamic K-factor with decay.
    
    K = max(K_MIN, K_MAX / sqrt(N + 1))
    
    As N increases, K decreases — early answers have more impact.
    
    Args:
        total_answered: User's cumulative total answered questions
    
    Returns:
        K-factor value
    """
    return max(K_MIN, K_MAX / math.sqrt(total_answered + 1))


def response_latency_weight(
    is_correct: bool,
    time_taken_sec: float
) -> float:
    """
    Calculate response latency weighting factor.
    
    Rules:
    - Correct + fast (< 15s): 1.15 (rapid mastery)
    - Correct + slow (> 60s): 0.85 (hesitant guess)
    - Incorrect + very fast (< 4s): 1.25 (spam clicking penalty)
    - Otherwise: 1.0
    
    Args:
        is_correct: Whether the user answered correctly
        time_taken_sec: Response time in seconds
    
    Returns:
        Weighting multiplier for the Elo update
    """
    if is_correct:
        if time_taken_sec < FAST_CORRECT_THRESHOLD:
            return FAST_CORRECT_BONUS
        elif time_taken_sec > SLOW_CORRECT_THRESHOLD:
            return SLOW_CORRECT_PENALTY
    else:
        if time_taken_sec < SPAM_INCORRECT_THRESHOLD:
            return SPAM_INCORRECT_PENALTY
    
    return DEFAULT_MULTIPLIER


def calculate_elo_update(
    user_elo: float,
    question_elo: float,
    is_correct: bool,
    total_answered: int,
    time_taken_sec: float
) -> Tuple[float, float]:
    """
    Calculate updated Elo ratings for both user and question.
    
    User update:  R_u' = R_u + K * (S - E_u) * w_t
    Question update: R_q' = R_q + QUESTION_K * (E_u - S)
    
    Args:
        user_elo: User's current Elo rating
        question_elo: Question's current difficulty rating
        is_correct: Whether the answer was correct
        total_answered: User's total questions answered (for K-factor)
        time_taken_sec: Response time in seconds
    
    Returns:
        Tuple of (new_user_elo, new_question_elo)
    """
    # Expected probability
    e_u = expected_win_probability(user_elo, question_elo)
    
    # Actual score
    s = 1.0 if is_correct else 0.0
    
    # Dynamic K-factor
    k = dynamic_k_factor(total_answered)
    
    # Latency weight
    w_t = response_latency_weight(is_correct, time_taken_sec)
    
    # User update
    new_user_elo = user_elo + k * (s - e_u) * w_t
    
    # Question update (fixed K, no latency weight)
    new_question_elo = question_elo + QUESTION_K * (e_u - s)
    
    return new_user_elo, new_question_elo


def select_next_question(
    user_elo: float,
    available_questions: list
) -> dict:
    """
    Select the optimal next question targeting the Zone of Proximal Development.
    
    For all unserved questions, calculate E_u and select the one
    that minimizes |E_u - TARGET_SUCCESS_RATE|.
    
    Args:
        user_elo: User's current Elo rating
        available_questions: List of dicts with at least 'id' and 'difficulty_rating'
    
    Returns:
        The selected question dict, or None if no questions available
    """
    if not available_questions:
        return None
    
    best_question = None
    min_distance = float('inf')
    
    for q in available_questions:
        e_u = expected_win_probability(user_elo, q['difficulty_rating'])
        distance = abs(e_u - TARGET_SUCCESS_RATE)
        
        if distance < min_distance:
            min_distance = distance
            best_question = q
    
    return best_question


def get_difficulty_label(difficulty_rating: float) -> str:
    """
    Convert a numerical difficulty rating (0-based Elo scale) to a label.
    
    Thresholds are the 0-anchored equivalents of the old 1100/1500 cutoffs.
    
    Returns:
        'easy', 'medium', or 'hard'
    """
    if difficulty_rating < -100:
        return 'easy'
    elif difficulty_rating < 300:
        return 'medium'
    else:
        return 'hard'


def get_difficulty_badge(score: float) -> str:
    """Return the user's level name for a 0-based Elo rating.

    Legacy name kept for API compatibility; delegates to
    :func:`elo_level_name` (Beginner < 200, Intermediate < 500,
    Advanced < 900, Expert 900+).
    """
    return elo_level_name(score)

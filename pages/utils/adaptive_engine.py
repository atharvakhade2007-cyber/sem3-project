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

# Question difficulty seeding tiers
DIFFICULTY_SEEDS = {
    'easy': 900.0,
    'medium': 1300.0,
    'hard': 1700.0,
}

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
    Convert a numerical difficulty rating to a human-readable label.
    
    Args:
        difficulty_rating: Elo-style difficulty rating
    
    Returns:
        'easy', 'medium', or 'hard'
    """
    if difficulty_rating < 1100:
        return 'easy'
    elif difficulty_rating < 1500:
        return 'medium'
    else:
        return 'hard'


def get_difficulty_badge(score: float) -> str:
    """
    Return a human-readable badge name based on user Elo score.
    
    Args:
        score: Normalized rating score
    
    Returns:
        Badge name string
    """
    if score >= 1700:
        return "Grandmaster"
    elif score >= 1500:
        return "Master"
    elif score >= 1300:
        return "Expert"
    elif score >= 1100:
        return "Skilled"
    elif score >= 900:
        return "Learner"
    else:
        return "Beginner"

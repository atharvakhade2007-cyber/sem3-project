"""
Adaptive Elo Engine — Continuous Online Elo Algorithm

Implements a psychometric model with:
- Dynamic K-factor decay
- Response latency weighting (time multiplier w_t)
- Zone of Proximal Development targeting (65% success rate)
"""

import math
from typing import Tuple, Optional, List, Dict, Any


# ─── Constants ───────────────────────────────────────────────

TARGET_SUCCESS_RATE = 0.65
QUESTION_K = 16.0
K_MIN = 16.0
K_MAX = 64.0


class AdaptiveEloEngine:
    """
    Static methods implementing the continuous adaptive Elo algorithm.
    All math is pure — no database access, no side effects.
    """

    @staticmethod
    def expected_probability(user_elo: float, question_elo: float) -> float:
        """
        E_u = 1.0 / (1.0 + 10 ** ((question_rating - user_rating) / 400.0))

        Args:
            user_elo: User's current Elo rating (R_u)
            question_elo: Question's current difficulty rating (R_q)

        Returns:
            Expected probability of answering correctly (0.0 to 1.0)
        """
        exponent = (question_elo - user_elo) / 400.0
        return 1.0 / (1.0 + math.pow(10.0, exponent))

    @staticmethod
    def dynamic_k_factor(total_answered: int) -> float:
        """
        K = max(16.0, 64.0 / sqrt(total_answered + 1))

        As N increases, K decreases — early answers have more impact.

        Args:
            total_answered: User's cumulative total questions answered

        Returns:
            K-factor value
        """
        return max(K_MIN, K_MAX / math.sqrt(total_answered + 1))

    @staticmethod
    def time_multiplier(is_correct: bool, time_taken_sec: float) -> float:
        """
        Time Multiplier (w_t):
        - Correct & time < 15s:  1.15
        - Correct & time > 60s:  0.85
        - Incorrect & time < 4s: 1.25
        - Otherwise:             1.0

        Args:
            is_correct: Whether the user answered correctly
            time_taken_sec: Response time in seconds

        Returns:
            Weighting multiplier for the Elo update
        """
        if is_correct and time_taken_sec < 15.0:
            return 1.15
        if is_correct and time_taken_sec > 60.0:
            return 0.85
        if not is_correct and time_taken_sec < 4.0:
            return 1.25
        return 1.0

    @staticmethod
    def calculate_elo_update(
        user_elo: float,
        question_elo: float,
        is_correct: bool,
        total_answered: int,
        time_taken_sec: float,
    ) -> Tuple[float, float]:
        """
        Calculate updated Elo ratings for both user and question.

        Rating Updates:
        - new_user_rating = user_rating + K * (S - E_u) * w_t
        - new_question_rating = question_rating + 16.0 * (E_u - S)

        Where:
        - S = 1 if correct, else 0
        - E_u = expected_probability(user_elo, question_elo)
        - K = dynamic_k_factor(total_answered)
        - w_t = time_multiplier(is_correct, time_taken_sec)

        Args:
            user_elo: User's current Elo rating
            question_elo: Question's current difficulty rating
            is_correct: Whether the answer was correct
            total_answered: User's total questions answered (for K-factor)
            time_taken_sec: Response time in seconds

        Returns:
            Tuple of (new_user_elo, new_question_elo)
        """
        e_u = AdaptiveEloEngine.expected_probability(user_elo, question_elo)
        s = 1.0 if is_correct else 0.0
        k = AdaptiveEloEngine.dynamic_k_factor(total_answered)
        w_t = AdaptiveEloEngine.time_multiplier(is_correct, time_taken_sec)

        new_user_elo = user_elo + k * (s - e_u) * w_t
        new_question_elo = question_elo + QUESTION_K * (e_u - s)

        return new_user_elo, new_question_elo

    @staticmethod
    def select_next_question(
        user_elo: float,
        available_questions: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Select the optimal next question targeting the Zone of Proximal Development.

        From unserved_questions, pick the one minimizing |E_u - 0.65|.

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
            e_u = AdaptiveEloEngine.expected_probability(user_elo, q['difficulty_rating'])
            distance = abs(e_u - TARGET_SUCCESS_RATE)

            if distance < min_distance:
                min_distance = distance
                best_question = q

        return best_question

    @staticmethod
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
        return 'hard'

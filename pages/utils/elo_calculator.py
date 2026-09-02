def calculate_new_ratings(
    user_elo: int, 
    question_elo: int, 
    is_correct: bool, 
    K: int = 32
) -> tuple[int, int]:
    """
    Calculates updated Elo ratings for a user and a question based on standard Elo rating formula.

    :param user_elo: Current Elo rating of the user.
    :param question_elo: Current Elo rating of the question.
    :param is_correct: True if user answered correctly, False otherwise.
    :param K: K-factor controlling max rating adjustment per answer (default: 32).
    :return: Tuple of (new_user_elo, new_question_elo) rounded to nearest integer.
    """
    # Expected score for user
    e_user = 1.0 / (1.0 + 10.0 ** ((question_elo - user_elo) / 400.0))
    # Expected score for question
    e_question = 1.0 - e_user

    # Actual outcome S: 1.0 for correct, 0.0 for incorrect
    s_user = 1.0 if is_correct else 0.0
    s_question = 1.0 - s_user

    # Rating updates
    new_user_elo = user_elo + K * (s_user - e_user)
    new_question_elo = question_elo + K * (s_question - e_question)

    return round(new_user_elo), round(new_question_elo)

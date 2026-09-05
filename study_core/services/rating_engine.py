"""
Rating Engine — Elo for 1v1 asynchronous friend duels.

Pure math (expected score, dynamic K, tie-break resolution) lives in module
functions so it is trivially testable. The one database-touching entry point,
``apply_duel_elo_ratings``, serialises concurrent completions with
``transaction.atomic()`` + ``select_for_update()`` on the challenge row and on
both ``UserProfile`` rows (locked in ascending pk order to avoid deadlocks),
which makes it safe for async duels completing at the same time.

Scoring semantics (shared with the submission view so the displayed verdict
always matches the rating update):

    E_A = 1 / (1 + 10 ** ((R_B - R_A) / 400))
    R'_A = R_A + K * (S_A - E_A)

    K = 40  provisional — fewer than 20 duels played
    K = 10  high tier    — 20+ duels and rating > 800 (0-based scale)
    K = 20  standard     — otherwise

    S_A: 1.0 win, 0.5 draw, 0.0 loss.
    Tie-break: higher raw score wins; on equal scores the faster total time
    wins, but total times within 1 second of each other score as a draw.
"""

import math

from django.db import transaction
from django.db.models import Q

from study_core.models import QuizChallenge, UserProfile

# ─── Constants ───────────────────────────────────────────────

K_PROVISIONAL = 40.0
K_STANDARD = 20.0
K_HIGH_TIER = 10.0
PROVISIONAL_MIN_DUELS = 20   # fewer than this many duels → provisional K
# Ratings are 0-based; 800 is the 0-anchored equivalent of the old 2000
# cutoff on the previous 1200-centered scale (2000 − 1200 = 800).
HIGH_TIER_RATING = 800.0     # above this rating → reduced high-tier K
TIME_DRAW_TOLERANCE_SEC = 1.0  # equal scores within 1s → draw


# ─── Pure math ───────────────────────────────────────────────


def expected_score(rating_a: float, rating_b: float) -> float:
    """
    E_A = 1 / (1 + 10 ** ((R_B - R_A) / 400))

    Probability that player A beats player B given their ratings.
    """
    return 1.0 / (1.0 + math.pow(10.0, (rating_b - rating_a) / 400.0))


def k_factor(duels_played: int, rating: float) -> float:
    """
    Dynamic K-factor:

    - 40 while provisional (fewer than 20 completed duels)
    - 10 once the player is established (20+ duels) AND above 800 rating
      (0-based scale; equivalent of the old 2000 cutoff)
    - 20 otherwise (standard established players)
    """
    if duels_played < PROVISIONAL_MIN_DUELS:
        return K_PROVISIONAL
    if rating > HIGH_TIER_RATING:
        return K_HIGH_TIER
    return K_STANDARD


def resolve_duel_outcome(
    challenger_score: int,
    challenger_time_sec: float,
    challenged_score: int,
    challenged_time_sec: float,
):
    """
    Resolve who won an async duel.

    Returns ``(side, challenger_score_value)`` where ``side`` is one of
    ``'challenger'`` / ``'challenged'`` / ``'draw'`` and
    ``challenger_score_value`` is the Elo result S_A from the challenger's
    perspective (1.0 / 0.5 / 0.0).

    Rules:
    - Higher raw score wins.
    - Equal scores → faster total completion time wins.
    - Equal scores and times within 1 second of each other → draw (0.5).
    """
    if challenger_score != challenged_score:
        if challenger_score > challenged_score:
            return 'challenger', 1.0
        return 'challenged', 0.0

    time_gap = float(challenger_time_sec or 0.0) - float(challenged_time_sec or 0.0)
    if abs(time_gap) >= TIME_DRAW_TOLERANCE_SEC:
        if time_gap < 0:
            return 'challenger', 1.0
        return 'challenged', 0.0
    return 'draw', 0.5


def duels_played(user) -> int:
    """Number of completed duels the user has participated in."""
    return QuizChallenge.objects.filter(
        Q(challenger=user) | Q(challenged_user=user),
        status=QuizChallenge.Status.COMPLETED,
    ).count()


# ─── Database entry point ────────────────────────────────────


@transaction.atomic
def apply_duel_elo_ratings(challenge) -> dict:
    """
    Update both players' ``UserProfile.elo_rating`` for a completed duel.

    Concurrency safety:
    - Runs inside ``transaction.atomic()``.
    - Locks both ``UserProfile`` rows, ordered by ``user_id`` (a consistent
      lock order) so concurrent duels that share a player cannot deadlock or
      lose a read-modify-write update. The caller serialises the *same* duel
      via a ``select_for_update`` on the challenge row before marking it
      completed, so a challenge is never rated twice.

    ``duels_played`` (used for the provisional K band) is derived from
    completed ``QuizChallenge`` rows, which already include the current duel
    because the caller persists the challenge as completed before invoking
    this function.

    Returns a summary dict of per-player rating changes.
    """
    if (
        challenge.status != QuizChallenge.Status.COMPLETED
        or challenge.challenged_score is None
    ):
        raise ValueError('Cannot rate a duel that is not completed.')

    challenger_id = challenge.challenger_id
    challenged_id = challenge.challenged_user_id

    # Lock both profile rows in ascending user_id order (consistent order →
    # no deadlocks between concurrent duels sharing a player).
    profiles = {
        p.user_id: p
        for p in UserProfile.objects.select_for_update()
        .filter(user_id__in=[challenger_id, challenged_id])
        .order_by('user_id')
    }
    challenger_profile = profiles.get(challenger_id)
    challenged_profile = profiles.get(challenged_id)
    # Profiles are auto-created on signup (signal), but be defensive anyway.
    if challenger_profile is None or challenged_profile is None:
        challenger_profile = challenger_profile or \
            UserProfile.objects.get_or_create(user_id=challenger_id)[0]
        challenged_profile = challenged_profile or \
            UserProfile.objects.get_or_create(user_id=challenged_id)[0]

    side, s_challenger = resolve_duel_outcome(
        challenge.challenger_score,
        challenge.challenger_time_seconds,
        challenge.challenged_score,
        challenge.challenged_time_seconds,
    )

    r_challenger = challenger_profile.elo_rating
    r_challenged = challenged_profile.elo_rating

    e_challenger = expected_score(r_challenger, r_challenged)
    k_challenger = k_factor(
        duels_played(challenge.challenger), r_challenger
    )
    k_challenged = k_factor(
        duels_played(challenge.challenged_user), r_challenged
    )

    s_challenged = 1.0 - s_challenger
    new_challenger = round(
        r_challenger + k_challenger * (s_challenger - e_challenger), 1
    )
    new_challenged = round(
        r_challenged + k_challenged * (s_challenged - (1.0 - e_challenger)), 1
    )

    challenger_profile.elo_rating = new_challenger
    challenged_profile.elo_rating = new_challenged
    challenger_profile.save(update_fields=['elo_rating'])
    challenged_profile.save(update_fields=['elo_rating'])

    return {
        'outcome': side,
        'challenger': {
            'username': challenge.challenger.username,
            'elo_before': r_challenger,
            'elo_after': new_challenger,
            'elo_change': round(new_challenger - r_challenger, 1),
            'k_factor': k_challenger,
        },
        'challenged': {
            'username': challenge.challenged_user.username,
            'elo_before': r_challenged,
            'elo_after': new_challenged,
            'elo_change': round(new_challenged - r_challenged, 1),
            'k_factor': k_challenged,
        },
    }

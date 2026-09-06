"""ML prediction wrapper for the pre-trained RandomForestClassifier.

Loads `ml/models/model.pkl` once and exposes `predict_student_level(student_data)`.

The model bundle is expected to be a dict with keys:
    - "model": trained sklearn estimator
    - "features": ordered list of feature names used during training
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, Optional, Tuple

import pandas as pd

_PICKLE_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "model.pkl")


def _load_model_bundle() -> Dict[str, Any]:
    """Load and validate the serialized model bundle."""
    if not os.path.isfile(_PICKLE_PATH):
        raise FileNotFoundError(
            "ML model not found at "
            f"{_PICKLE_PATH}. Place model.pkl from training in ml/models/."
        )
    import joblib

    bundle = joblib.load(_PICKLE_PATH)
    if not isinstance(bundle, dict):
        raise ValueError("model.pkl must contain a dict with 'model' and 'features'.")
    if "model" not in bundle or "features" not in bundle:
        raise ValueError("model.pkl bundle missing required keys: 'model', 'features'.")
    return bundle


_bundle: Optional[Dict[str, Any]] = None


def _get_bundle() -> Dict[str, Any]:
    global _bundle
    if _bundle is None:
        _bundle = _load_model_bundle()
    return _bundle


def _is_finite_number(value: Any) -> bool:
    """Return True if value is a finite int/float (including numpy numerics)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f)


def predict_student_level(
    student_data: Dict[str, Any],
) -> Tuple[str, Dict[str, float]]:
    """
    Predict the initial student level from a single performance record.

    Parameters
    ----------
    student_data : dict
        Must contain exactly the feature names listed in the trained model,
        e.g. quiz_attempts, questions_attempted, correct_answers, wrong_answers,
        accuracy, avg_time_per_question, easy_correct, medium_correct,
        hard_correct, previous_avg_score, current_elo_rating,
        question_difficulty_rating, total_answered.

    Returns
    -------
    (level, probabilities)
        level : str — one of "Beginner", "Intermediate", "Advanced"
        probabilities : dict mapping class name -> float probability
    """
    bundle = _get_bundle()
    features = bundle["features"]
    model = bundle["model"]

    missing = set(features) - set(student_data.keys())
    if missing:
        raise ValueError(f"Missing required features: {sorted(missing)}")

    # Reorder exactly as training expected.
    ordered = {k: student_data[k] for k in features}
    df = pd.DataFrame([ordered], columns=features)

    # Sanity check: every feature must be a finite number.
    for col in features:
        val = df[col].iloc[0]
        if not _is_finite_number(val):
            raise ValueError(f"Feature {col!r} must be a finite number, got {val!r}")

    prediction = model.predict(df)[0]
    probas = model.predict_proba(df)[0]

    classes = list(model.classes_)
    probs = {cls: float(probas[i]) for i, cls in enumerate(classes)}

    return str(prediction), probs

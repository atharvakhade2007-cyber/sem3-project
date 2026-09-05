"""
predict.py — Load the trained Random Forest model and predict a student's level.

This script:
1. Loads ml/models/model.pkl (trained model + feature order).
2. Provides the reusable function `predict_student_level(student_data)`.
3. Returns the predicted level (Beginner / Intermediate / Advanced) and the
   per-class prediction probabilities.
4. Supports a CLI demo with a sample student.

Prediction ONLY — this script never trains or retrains a model.

Usage:
    python ml/prediction/predict.py                 # run the built-in demo
    python ml/prediction/predict.py --json file.json   # predict from a JSON file
"""

import os
import json
import sys
from functools import lru_cache

import pandas as pd
import joblib

# Windows consoles default to cp1252, which cannot print '—'/'✓' etc.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


# ─── Paths (relative to project root: sem3-project/) ──────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH = os.path.join(PROJECT_ROOT, "ml", "models", "model.pkl")

# Expected feature order — must match ml/training/train_model.py exactly.
EXPECTED_FEATURES = [
    "quiz_attempts",
    "questions_attempted",
    "correct_answers",
    "wrong_answers",
    "accuracy",
    "avg_time_per_question",
    "easy_correct",
    "medium_correct",
    "hard_correct",
    "previous_avg_score",
    "current_elo_rating",
    "question_difficulty_rating",
    "total_answered",
]

VALID_LEVELS = {"Beginner", "Intermediate", "Advanced"}


# ─── Model loading ────────────────────────────────────────────


@lru_cache(maxsize=1)
def load_model():
    """
    Load the trained model bundle from ml/models/model.pkl (cached in memory
    so a long-running Django process only pays the 7 MB unpickle cost once).

    Returns a dict: {"model": <RandomForestClassifier>, "features": [list]}.

    Raises:
        FileNotFoundError: model.pkl is missing (run train_model.py first).
        ValueError: model.pkl exists but is corrupted or has the wrong shape.
    """
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"Model file not found at: {MODEL_PATH}\n"
            "Run training first:  python ml/training/train_model.py"
        )

    try:
        model_data = joblib.load(MODEL_PATH)
    except Exception as exc:
        raise ValueError(
            f"Failed to load model from {MODEL_PATH}: {exc}\n"
            "The file may be corrupted — retrain it with "
            "python ml/training/train_model.py"
        ) from exc

    if not isinstance(model_data, dict) or "model" not in model_data or "features" not in model_data:
        raise ValueError(
            f"Model bundle at {MODEL_PATH} has the wrong structure.\n"
            "Expected {'model': <classifier>, 'features': [list]} — retrain with "
            "python ml/training/train_model.py"
        )

    return model_data


# ─── Prediction ───────────────────────────────────────────────


def predict_student_level(student_data):
    """
    Predict a student's initial learning level from performance data.

    Args:
        student_data: dict (or list of dicts) of performance features, e.g.
            {
                "quiz_attempts": 2,
                "questions_attempted": 20,
                "correct_answers": 16,
                ...
            }

    Returns:
        dict with keys:
            "predicted_level": "Beginner" | "Intermediate" | "Advanced"
            "probabilities":   {"Beginner": 0.10, "Intermediate": 0.75, ...}
        For a list input, returns a list of such dicts.

    Raises:
        FileNotFoundError / ValueError: model missing or corrupted.
        ValueError: missing features or invalid input.
    """
    model_data = load_model()
    model = model_data["model"]
    features = list(model_data["features"])

    # Single dict → wrap into a list for uniform handling.
    single_input = isinstance(student_data, dict)
    records = [student_data] if single_input else list(student_data)

    if not records:
        raise ValueError("student_data is empty — provide at least one student record.")

    results = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(
                f"Each student record must be a dict, got {type(record).__name__}."
            )

        # Check every required feature is present.
        missing = [f for f in features if f not in record]
        if missing:
            raise ValueError(
                f"Missing feature(s): {missing}. "
                f"Required features: {features}"
            )

        # Reorder columns to EXACTLY the training feature order.
        row = {f: record[f] for f in features}
        df = pd.DataFrame([row], columns=features)

        # Validate numeric values.
        try:
            values = df[features].astype(float).values
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Non-numeric feature value in record: {exc}"
            ) from exc

        # Predict. (The model was fitted on raw arrays, so pass the numpy
        # array — avoids sklearn's feature-name mismatch warning.)
        level = str(model.predict(values)[0])

        # Probabilities (Random Forest supports predict_proba).
        probabilities = None
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(values)[0]
            probabilities = {
                str(cls): round(float(p), 4)
                for cls, p in zip(model.classes_, proba)
            }

        result = {"predicted_level": level, "probabilities": probabilities}
        results.append(result)

    return results[0] if single_input else results


# ─── CLI demo ─────────────────────────────────────────────────


def _demo_student():
    """The sample student from the project spec."""
    return {
        "quiz_attempts": 2,
        "questions_attempted": 20,
        "correct_answers": 16,
        "wrong_answers": 4,
        "accuracy": 0.80,
        "avg_time_per_question": 35,
        "easy_correct": 7,
        "medium_correct": 6,
        "hard_correct": 3,
        "previous_avg_score": 75,
        "current_elo_rating": 350,
        "question_difficulty_rating": 200,
        "total_answered": 40,
    }


def main():
    print("=" * 60)
    print("  AdaptiveQuiz AI — Student Level Prediction")
    print("=" * 60)

    if len(sys.argv) > 2 and sys.argv[1] == "--json":
        payload_path = sys.argv[2]
        if not os.path.exists(payload_path):
            print(f"✗ JSON file not found: {payload_path}")
            sys.exit(1)
        with open(payload_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"Loaded student data from: {payload_path}")
        results = predict_student_level(data)
        print(json.dumps(results, indent=2, default=str))
        sys.exit(0)

    # Default: run the demo prediction.
    student = _demo_student()
    print("\nStudent data:")
    for k, v in student.items():
        print(f"  {k:<28s} {v}")
    print("-" * 60)

    try:
        result = predict_student_level(student)
    except (FileNotFoundError, ValueError) as exc:
        print(f"✗ Prediction failed: {exc}")
        sys.exit(1)

    print(f"\nPredicted Level: {result['predicted_level']}")
    print("\nProbabilities:")
    if result["probabilities"]:
        for level, prob in result["probabilities"].items():
            print(f"  {level:<14s} {prob * 100:.1f}%")
    else:
        print("  (not available for this model)")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
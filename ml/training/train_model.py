"""
ML Training Script — RandomForestClassifier for student-level prediction.

Loads student_performance_elo_dataset.csv, validates it, trains a
RandomForestClassifier with Stratified 5-Fold cross-validation, prints
per-fold and average metrics, then saves the final trained model to
ml/models/model.pkl as a dict with keys:
    - 'model': trained RandomForestClassifier
    - 'features': ordered list of feature names
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.metrics import make_scorer, precision_score, recall_score, f1_score, accuracy_score
import joblib


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))


def _asset_path(relative: str) -> str:
    return os.path.join(REPO_ROOT, "ml", relative)


DATASET_PATH = _asset_path("dataset/student_performance_elo_dataset.csv")
MODEL_PATH = _asset_path("models/model.pkl")

FEATURE_COLUMNS: List[str] = [
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

TARGET_COLUMN = "student_level"
VALID_CLASSES = {"Beginner", "Intermediate", "Advanced"}

CLF_PARAMS: Dict[str, Any] = {
    "n_estimators": 200,
    "max_depth": 12,
    "random_state": 42,
    "class_weight": "balanced",
}

CV_PARAMS: Dict[str, Any] = {
    "n_splits": 5,
    "shuffle": True,
    "random_state": 42,
}


def _validate_dataset(df: pd.DataFrame) -> None:
    """Raise ValueError with actionable message if dataset is unusable."""
    missing_cols = set(FEATURE_COLUMNS + [TARGET_COLUMN]) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Dataset missing required columns: {sorted(missing_cols)}")

    dupes = df.duplicated().sum()
    if dupes > 0:
        print(f"[WARN] Dropping {dupes} duplicate row(s).")
        df.drop_duplicates(inplace=True)

    na_counts = df[FEATURE_COLUMNS + [TARGET_COLUMN]].isna().sum()
    if na_counts.any():
        print("[WARN] Missing values detected:")
        for col, cnt in na_counts[na_counts > 0].items():
            print(f"  {col}: {cnt} missing")
        for col in FEATURE_COLUMNS:
            if df[col].isna().any():
                df[col] = pd.to_numeric(df[col], errors="coerce")
                df[col].fillna(df[col].median(), inplace=True)

    invalid_targets = set(df[TARGET_COLUMN].unique()) - VALID_CLASSES
    if invalid_targets:
        raise ValueError(
            f"Unexpected target values (not in {VALID_CLASSES}): {invalid_targets}"
        )

    non_finite = []
    for col in FEATURE_COLUMNS:
        if not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        na_before = df[col].isna().sum()
        df[col] = df[col].astype(float)
        if not df[col].apply(lambda x: np.isfinite(x)).all():
            non_finite.append(col)
        if df[col].isna().sum() > na_before:
            print(f"  [WARN] Coerced non-numeric values to NaN in '{col}'; filling with median.")
            df[col].fillna(df[col].median(), inplace=True)


def build_feature_matrix(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """Return (X, y) with exactly the expected feature order."""
    X = df[FEATURE_COLUMNS].copy()
    y = df[TARGET_COLUMN].astype(str).str.strip()
    return X, y


def print_fold_results(cv_results: Dict[str, List[float]]) -> None:
    """Pretty-print per-fold metrics and the average row."""
    metric_keys = [
        ("test_accuracy", "Accuracy"),
        ("test_precision", "Precision"),
        ("test_recall", "Recall"),
        ("test_f1", "F1 Score"),
    ]
    n_folds = len(cv_results["test_accuracy"])
    for i in range(n_folds):
        print(f"\nFold {i + 1}:")
        for key, label in metric_keys:
            val = cv_results[key][i]
            print(f"    {label}: {val:.4f}")

    print("\nAverage Results:")
    for key, label in metric_keys:
        avg = sum(cv_results[key]) / n_folds
        print(f"    Average {label}: {avg:.4f}")


def train() -> None:
    """Load dataset, validate, cross-validate, train final model, save."""
    if not os.path.isfile(DATASET_PATH):
        sys.exit(f"ERROR: Dataset not found at {DATASET_PATH}")

    print(f"Loading dataset: {DATASET_PATH}")
    df = pd.read_csv(DATASET_PATH)
    print(f"Raw shape: {df.shape[0]} rows x {df.shape[1]} columns")

    _validate_dataset(df)
    print(f"Cleaned shape: {df.shape[0]} rows x {df.shape[1]} columns")

    X, y = build_feature_matrix(df)
    print(f"Feature matrix: {X.shape[0]} samples x {X.shape[1]} features")
    print(f"Target distribution:\n{y.value_counts().to_string()}")

    base_clf = RandomForestClassifier(**CLF_PARAMS)
    cv = StratifiedKFold(**CV_PARAMS)

    scorers = {
        "accuracy": make_scorer(accuracy_score),
        "precision": make_scorer(precision_score, average="macro", zero_division=0),
        "recall": make_scorer(recall_score, average="macro", zero_division=0),
        "f1": make_scorer(f1_score, average="macro", zero_division=0),
    }

    print("\nRunning Stratified 5-Fold Cross-Validation...")
    cv_results = cross_validate(
        base_clf, X, y, cv=cv, scoring=scorers, n_jobs=-1, return_train_score=False
    )
    print_fold_results(cv_results)

    print("\nTraining final model on full dataset...")
    final_model = RandomForestClassifier(**CLF_PARAMS)
    final_model.fit(X, y)

    bundle: Dict[str, Any] = {
        "model": final_model,
        "features": list(FEATURE_COLUMNS),
    }

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)
    print(f"\nModel saved to: {MODEL_PATH}")
    print(f"  Type: {type(final_model).__name__}")
    print(f"  Features ({len(bundle['features'])}): {bundle['features']}")
    print(f"  Classes: {list(final_model.classes_)}")


if __name__ == "__main__":
    train()

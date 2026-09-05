"""
train_model.py — Train a Random Forest Classifier for student level prediction.

This script:
1. Loads the student performance dataset (CSV).
2. Validates the dataset (missing values, column checks, class distribution).
3. Defines ML features and target.
4. Trains a RandomForestClassifier with Stratified 5-Fold Cross-Validation.
5. Displays per-fold and average metrics (Accuracy, Precision, Recall, F1).
6. Trains a final model on the complete dataset.
7. Saves the final model + feature order to ml/models/model.pkl using joblib.

ML Algorithm:    RandomForestClassifier(n_estimators=200, max_depth=12, random_state=42, class_weight="balanced")
Evaluation:      StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
Target:          student_level (Beginner / Intermediate / Advanced)

Usage:
    python ml/training/train_model.py
"""

import os
import sys
import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

# Windows consoles default to cp1252, which cannot print '✓'/'⚠' etc.
# Force UTF-8 so the output renders correctly on every platform.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


# ─── Configuration ────────────────────────────────────────────

# Paths relative to project root (sem3-project/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATASET_PATH = os.path.join(PROJECT_ROOT, "ml", "dataset", "student_performance_elo_dataset.csv")
MODEL_DIR = os.path.join(PROJECT_ROOT, "ml", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "model.pkl")

# Features used for training (in exact order — prediction must use the same)
FEATURES = [
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

TARGET = "student_level"

# Excluded columns (NOT features)
EXCLUDE_COLUMNS = ["student_id"]

# Random Forest configuration
RF_CONFIG = {
    "n_estimators": 200,
    "max_depth": 12,
    "random_state": 42,
    "class_weight": "balanced",
}

# Stratified K-Fold configuration
CV_CONFIG = {
    "n_splits": 5,
    "shuffle": True,
    "random_state": 42,
}


# ─── Dataset Loading & Validation ─────────────────────────────


def load_dataset() -> pd.DataFrame:
    """Load the CSV dataset and perform basic validation."""
    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(f"Dataset not found at: {DATASET_PATH}")

    df = pd.read_csv(DATASET_PATH)
    print(f"Dataset loaded: {len(df)} rows, {len(df.columns)} columns")
    print(f"File: {DATASET_PATH}")
    return df


def validate_dataset(df: pd.DataFrame) -> None:
    """Inspect the dataset for common issues before training."""
    print("\n" + "=" * 60)
    print("DATASET VALIDATION")
    print("=" * 60)

    # Check required columns exist
    required_columns = FEATURES + [TARGET] + EXCLUDE_COLUMNS
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    print(f"✓ All {len(FEATURES)} feature columns present")
    print(f"✓ Target column '{TARGET}' present")

    # Check for missing values in features
    missing_in_features = df[FEATURES].isnull().sum()
    cols_with_missing = missing_in_features[missing_in_features > 0]
    if len(cols_with_missing) > 0:
        print(f"\n⚠ Missing values found in features:")
        for col, count in cols_with_missing.items():
            print(f"  - {col}: {count} missing ({count/len(df)*100:.1f}%)")
        # Fill missing numeric values with median
        for col in cols_with_missing.index:
            median_val = df[col].median()
            df[col].fillna(median_val, inplace=True)
            print(f"  → Filled '{col}' missing values with median ({median_val:.2f})")
    else:
        print("✓ No missing values in features")

    # Check for missing target values
    missing_target = df[TARGET].isnull().sum()
    if missing_target > 0:
        print(f"\n⚠ {missing_target} rows have missing target values — dropping them")
        df.dropna(subset=[TARGET], inplace=True)
    else:
        print("✓ No missing target values")

    # Check for duplicate rows
    duplicates = df.duplicated().sum()
    if duplicates > 0:
        print(f"\n⚠ {duplicates} duplicate rows found — removing them")
        df.drop_duplicates(inplace=True)
    else:
        print("✓ No duplicate rows")

    # Check data types
    for feat in FEATURES:
        if not pd.api.types.is_numeric_dtype(df[feat]):
            print(f"\n⚠ Column '{feat}' is not numeric (dtype: {df[feat].dtype})")

    # Check target class distribution
    print(f"\nTarget class distribution ({TARGET}):")
    class_counts = df[TARGET].value_counts()
    for cls, count in class_counts.items():
        print(f"  - {cls}: {count} ({count/len(df)*100:.1f}%)")

    # Check valid target values
    valid_classes = {"Beginner", "Intermediate", "Advanced"}
    actual_classes = set(df[TARGET].unique())
    invalid_classes = actual_classes - valid_classes
    if invalid_classes:
        raise ValueError(f"Invalid target classes found: {invalid_classes}")

    print(f"✓ All target values are valid classes")
    print("=" * 60)


# ─── Model Training ───────────────────────────────────────────


def train_with_cross_validation(df: pd.DataFrame) -> None:
    """Perform Stratified 5-Fold Cross-Validation and print metrics."""
    X = df[FEATURES].values
    y = df[TARGET].values

    print(f"\nTraining data shape: X={X.shape}, y={y.shape}")
    print(f"Features: {FEATURES}")
    print(f"Target: {TARGET}")
    print(f"Algorithm: RandomForestClassifier(n_estimators=200, max_depth=12, class_weight='balanced')")
    print(f"Evaluation: Stratified {CV_CONFIG['n_splits']}-Fold Cross-Validation")

    skf = StratifiedKFold(
        n_splits=CV_CONFIG["n_splits"],
        shuffle=CV_CONFIG["shuffle"],
        random_state=CV_CONFIG["random_state"],
    )

    fold_accuracies = []
    fold_precisions = []
    fold_recalls = []
    fold_f1s = []

    print("\n" + "=" * 60)
    print("CROSS-VALIDATION RESULTS")
    print("=" * 60)

    for fold_idx, (train_index, val_index) in enumerate(skf.split(X, y), start=1):
        X_train, X_val = X[train_index], X[val_index]
        y_train, y_val = y[train_index], y[val_index]

        model = RandomForestClassifier(**RF_CONFIG)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_val)

        acc = accuracy_score(y_val, y_pred)
        prec = precision_score(y_val, y_pred, average="macro", zero_division=0)
        rec = recall_score(y_val, y_pred, average="macro", zero_division=0)
        f1 = f1_score(y_val, y_pred, average="macro", zero_division=0)

        fold_accuracies.append(acc)
        fold_precisions.append(prec)
        fold_recalls.append(rec)
        fold_f1s.append(f1)

        print(f"\nFold {fold_idx}:")
        print(f"  Accuracy:  {acc:.4f}")
        print(f"  Precision: {prec:.4f}")
        print(f"  Recall:    {rec:.4f}")
        print(f"  F1 Score:  {f1:.4f}")

    avg_acc = np.mean(fold_accuracies)
    avg_prec = np.mean(fold_precisions)
    avg_rec = np.mean(fold_recalls)
    avg_f1 = np.mean(fold_f1s)

    print("\n" + "-" * 40)
    print("AVERAGE RESULTS:")
    print("-" * 40)
    print(f"  Average Accuracy:  {avg_acc:.4f}")
    print(f"  Average Precision: {avg_prec:.4f}")
    print(f"  Average Recall:    {avg_rec:.4f}")
    print(f"  Average F1 Score:  {avg_f1:.4f}")
    print("=" * 60)


def train_final_model(df: pd.DataFrame) -> None:
    """Train the final Random Forest on the complete dataset and save to disk."""
    print("\n" + "=" * 60)
    print("TRAINING FINAL MODEL ON COMPLETE DATASET")
    print("=" * 60)

    X = df[FEATURES].values
    y = df[TARGET].values

    final_model = RandomForestClassifier(**RF_CONFIG)
    final_model.fit(X, y)

    print(f"Final model trained on {len(X)} samples")
    print(f"Number of trees: {final_model.n_estimators}")
    print(f"Max depth: {final_model.max_depth}")

    # Feature importance
    importances = final_model.feature_importances_
    print("\nFeature importances:")
    for feat, imp in sorted(zip(FEATURES, importances), key=lambda x: -x[1]):
        bar = "█" * int(imp * 50)
        print(f"  {feat:<30s} {imp:.4f}  {bar}")

    # Save model + features
    os.makedirs(MODEL_DIR, exist_ok=True)
    model_data = {
        "model": final_model,
        "features": FEATURES,
    }
    joblib.dump(model_data, MODEL_PATH)

    file_size = os.path.getsize(MODEL_PATH)
    print(f"\n✓ Model saved to: {MODEL_PATH}")
    print(f"  File size: {file_size / 1024:.1f} KB")
    print("=" * 60)


# ─── Main ─────────────────────────────────────────────────────


def main():
    print("=" * 60)
    print("  AdaptiveQuiz AI — Student Level Prediction Training")
    print("  Algorithm: Random Forest Classifier")
    print("  Evaluation: Stratified 5-Fold Cross-Validation")
    print("=" * 60)

    # Step 1: Load dataset
    df = load_dataset()

    # Step 2: Validate dataset (modifies df in-place for minor fixes)
    validate_dataset(df)

    # Step 3: Cross-validation
    train_with_cross_validation(df)

    # Step 4: Train final model and save
    train_final_model(df)

    print("\n✅ Training complete! model.pkl is ready for prediction.")
    print(f"   Next step: python ml/prediction/predict.py")


if __name__ == "__main__":
    main()

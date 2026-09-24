"""
Member 2 — Model 2: Machine Failure/Delay Risk Prediction.

Trains RandomForestClassifier and XGBClassifier on Member 1's
data/processed/ml_failure_risk.csv, evaluates both with accuracy / precision /
recall / F1 / confusion matrix on a chronological hold-out split, keeps the
better model (by F1, since the failure class is a minority class), and saves
it to models/failure_risk_model.pkl.

Run: python train_failure_risk_model.py
"""
import json
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                              f1_score, confusion_matrix, roc_auc_score)
from xgboost import XGBClassifier

from ml_features import RISK_NUMERIC, RISK_TARGET, load_risk_training_frame, time_split

MODELS_DIR = Path("models")
REPORTS_DIR = Path("reports")
MODELS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)


def evaluate(y_true, y_pred, y_prob) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def main():
    df = load_risk_training_frame()
    train, test = time_split(df)
    X_train, y_train = train[RISK_NUMERIC], train[RISK_TARGET]
    X_test, y_test = test[RISK_NUMERIC], test[RISK_TARGET]

    pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)  # handle class imbalance
    candidates = {
        "RandomForest": RandomForestClassifier(
            n_estimators=300, max_depth=8, min_samples_leaf=3,
            class_weight="balanced", random_state=42, n_jobs=-1),
        "XGBoost": XGBClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.9, colsample_bytree=0.9, scale_pos_weight=pos_weight,
            random_state=42, eval_metric="logloss", n_jobs=-1),
    }

    results = {}
    for name, clf in candidates.items():
        clf.fit(X_train, y_train)
        preds = clf.predict(X_test)
        probs = clf.predict_proba(X_test)[:, 1]
        results[name] = evaluate(y_test, preds, probs)
        print(f"{name:15s} -> {results[name]}")

    best_name = max(results, key=lambda n: results[n]["f1"])
    best_clf = candidates[best_name]
    print(f"\nSelected model: {best_name} (highest F1)")

    joblib.dump({"model": best_clf, "model_name": best_name, "features": RISK_NUMERIC},
                MODELS_DIR / "failure_risk_model.pkl")

    report = {"task": "failure_risk_classification", "train_rows": len(train),
              "test_rows": len(test), "positive_rate_train": round(float(y_train.mean()), 4),
              "results": results, "selected_model": best_name}
    with open(REPORTS_DIR / "failure_risk_metrics.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"Saved model -> models/failure_risk_model.pkl")
    print(f"Saved metrics -> reports/failure_risk_metrics.json")


if __name__ == "__main__":
    main()

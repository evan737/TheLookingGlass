"""
Fits a logistic regression that learns how much to actually trust the
edge/confidence signals your engines produce, based on real settled
outcomes -- rather than a fixed hand-picked threshold.

This is deliberately simple (logistic regression, not deep learning) --
with the amount of data a personal paper-trading project accumulates,
a simple, interpretable model is the right tool. This exact technique
(recalibrating a model's stated probabilities against real outcomes)
has a name in the ML literature: Platt scaling.

IMPORTANT HONESTY GATE: with only a handful of settled trades, ANY model
fit on this data is mostly memorizing noise, not learning a real pattern.
This script refuses to treat its own output as trustworthy until there's
a reasonable amount of data, and always reports cross-validated
performance (not just training accuracy) so you can see whether it's
actually better than the simple edge-threshold rule, not just fitting
noise. Don't wire this into a real trading decision until MIN_TRADES_TO_TRUST
is comfortably cleared and cross-validated performance actually looks good.
"""
import csv
import pickle
from pathlib import Path

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict, StratifiedKFold, LeaveOneOut
from sklearn.metrics import brier_score_loss, roc_auc_score

TRADE_LOG = Path("paper_trades.csv")
RESULTS_LOG = Path("paper_trade_results.csv")
MODEL_FILE = Path("calibration_model.pkl")

MIN_TRADES_TO_TRUST = 30  # below this, treat any model output as noise, not signal


def load_training_data():
    if not TRADE_LOG.exists() or not RESULTS_LOG.exists():
        return None

    with TRADE_LOG.open("r", newline="", encoding="utf-8") as file:
        trades = {row["ticker"]: row for row in csv.DictReader(file)}

    with RESULTS_LOG.open("r", newline="", encoding="utf-8") as file:
        results = list(csv.DictReader(file))

    rows = []
    for result in results:
        trade = trades.get(result["ticker"])
        if not trade:
            continue

        def to_float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        model_prob = to_float(trade.get("model_prob_pct"))
        edge = to_float(trade.get("edge_pct"))
        confidence = to_float(trade.get("confidence_pct"))

        if model_prob is None or edge is None:
            continue  # older rows without structured features -- skip, can't use them

        rows.append({
            "model_prob_pct": model_prob,
            "abs_edge_pct": abs(edge),
            "confidence_pct": confidence if confidence is not None else 50.0,
            "has_confidence": 1 if confidence is not None else 0,
            "category": trade.get("category", "Unknown"),
            "won": 1 if result["won"] == "True" else 0,
        })

    if not rows:
        return None

    return pd.DataFrame(rows)


def build_features(df):
    feature_cols = ["model_prob_pct", "abs_edge_pct", "confidence_pct", "has_confidence"]
    category_dummies = pd.get_dummies(df["category"], prefix="cat")
    X = pd.concat([df[feature_cols], category_dummies], axis=1)
    return X, list(X.columns)


def train_and_evaluate():
    df = load_training_data()

    if df is None or len(df) == 0:
        print("No settled trades with structured features found. Nothing to train on yet.")
        return

    n = len(df)
    print(f"Found {n} settled trades with usable features.")

    if n < MIN_TRADES_TO_TRUST:
        print(f"\n*** Only {n} examples -- below the {MIN_TRADES_TO_TRUST}-trade trust "
              f"threshold. ***")
        print("A model CAN be fit below, but treat its output as a curiosity, not a "
              "signal -- there isn't enough data yet to distinguish a real pattern "
              "from noise. Keep using the simple edge-threshold rule for actual "
              "decisions until this grows.")

    X, feature_columns = build_features(df)
    y = df["won"]

    if y.nunique() < 2:
        print("All settled trades have the same outcome (all wins or all losses) -- "
              "can't fit a meaningful model yet. Need examples of both outcomes.")
        return

    model = LogisticRegression(max_iter=1000)

    # Cross-validation, not just training accuracy -- this is the honest
    # measure of whether the model generalizes, or is just memorizing.
    cv = LeaveOneOut() if n < 20 else StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    try:
        cv_probs = cross_val_predict(model, X, y, cv=cv, method="predict_proba")[:, 1]
        cv_brier = brier_score_loss(y, cv_probs)
        naive_brier = brier_score_loss(y, df["model_prob_pct"] / 100)

        print(f"\nCross-validated Brier score (learned model): {cv_brier:.4f}")
        print(f"Brier score of the RAW model_prob_pct alone:   {naive_brier:.4f}")
        print("(lower is better -- if the learned model isn't clearly beating the "
              "raw probability, it's not adding real value yet)")

        if y.nunique() == 2 and n >= 10:
            cv_auc = roc_auc_score(y, cv_probs)
            print(f"Cross-validated AUC: {cv_auc:.3f} (0.5 = coin flip, 1.0 = perfect)")
    except Exception as error:
        print(f"Could not compute cross-validated metrics ({error}) -- likely too few examples.")

    # Fit on all available data for the saved model (cross-validation above
    # was just to HONESTLY MEASURE performance, not to pick the final model)
    model.fit(X, y)

    with MODEL_FILE.open("wb") as file:
        pickle.dump({"model": model, "feature_columns": feature_columns, "n_trained_on": n}, file)

    print(f"\nSaved model to {MODEL_FILE} (trained on {n} examples).")
    print("\nLearned coefficients (how much each feature moves the predicted win probability):")
    for name, coef in zip(feature_columns, model.coef_[0]):
        print(f"  {name}: {coef:+.4f}")


if __name__ == "__main__":
    train_and_evaluate()
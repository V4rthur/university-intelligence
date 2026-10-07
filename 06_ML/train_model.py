"""Train, compare and select the student academic-risk model (PHASE 7).

Evaluation design
    * Temporal split - the model is always tested on a LATER semester than it
      was trained on, which is how it will be used in practice:
          train = older semesters, validation = second-to-last, test = last.
    * Four models are compared. The winner is chosen on VALIDATION ROC-AUC
      (ranking quality, independent of any threshold); the TEST semester is
      touched only once, to report honest final numbers.
    * Accuracy alone is misleading here: most students are not at risk, so a
      model that flags nobody is "accurate" and useless. A false negative is a
      struggling student nobody contacts, so the decision threshold is tuned
      on validation to reach the recall target in config.TARGET_RECALL.

Usage:  python 06_ML/train_model.py
"""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (HistGradientBoostingClassifier, HistGradientBoostingRegressor,
                              RandomForestClassifier)
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score, roc_curve)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import risk_model as rm  # noqa: E402

CANDIDATES = {
    "Logistic Regression": lambda: make_pipeline(
        StandardScaler(), LogisticRegression(max_iter=2000)),
    "Decision Tree": lambda: DecisionTreeClassifier(
        max_depth=6, min_samples_leaf=50, random_state=42),
    "Random Forest": lambda: RandomForestClassifier(
        n_estimators=300, min_samples_leaf=20, n_jobs=-1, random_state=42),
    "Gradient Boosting": lambda: HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.05, max_depth=5, random_state=42),
}


def threshold_for_recall(y, prob, target: float) -> float:
    """Largest threshold whose recall on (y, prob) still reaches the target."""
    _, tpr, thr = roc_curve(y, prob)
    ok = np.flatnonzero(tpr >= target)
    return float(min(thr[ok[0]], 0.99)) if len(ok) else 0.5


def metrics(y, prob, threshold: float) -> dict:
    pred = (prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return dict(Threshold=round(threshold, 3), Accuracy=accuracy_score(y, pred),
                Precision=precision_score(y, pred, zero_division=0),
                Recall=recall_score(y, pred), F1=f1_score(y, pred),
                ROC_AUC=roc_auc_score(y, prob), TN=int(tn), FP=int(fp), FN=int(fn), TP=int(tp))


def main() -> None:
    engine = config.get_engine()
    snap = rm.load_snapshot(engine)
    labelled, _ = rm.build_dataset(snap)
    X, y, sem = labelled[rm.FEATURES], labelled["Target"], labelled["SemesterKey"]
    last = sem.max()
    train, val, test = sem < last - 1, sem == last - 1, sem == last
    print(f"labelled rows: {len(labelled):,} | at-risk rate {y.mean():.1%}")
    print(f"train {train.sum():,} (semesters <= {last - 2}) | validation {val.sum():,} "
          f"(semester {last - 1}) | test {test.sum():,} (semester {last})")

    rows, fitted = [], {}
    for name, make in CANDIDATES.items():
        model = make().fit(X[train], y[train])
        p_val = model.predict_proba(X[val])[:, 1]
        p_test = model.predict_proba(X[test])[:, 1]
        thr = threshold_for_recall(y[val], p_val, config.TARGET_RECALL)
        fitted[name] = (model, thr, roc_auc_score(y[val], p_val))
        rows.append(dict(Model=name, Split="validation", Rule="recall target",
                         **metrics(y[val], p_val, thr)))
        rows.append(dict(Model=name, Split="test", Rule="default 0.5", **metrics(y[test], p_test, 0.5)))
        rows.append(dict(Model=name, Split="test", Rule="recall target",
                         **metrics(y[test], p_test, thr)))
    results = pd.DataFrame(rows)
    best = max(fitted, key=lambda k: fitted[k][2])
    results["IsBest"] = (results["Model"] == best).astype(int)
    results["TrainedAt"] = pd.Timestamp.now().floor("s")
    show = results[results.Split == "test"].drop(columns=["Split", "IsBest", "TrainedAt"])
    print("\nTEST semester results:\n" + show.round(3).to_string(index=False))
    print(f"\nbest model (validation ROC-AUC): {best}")

    # permutation importance of the winner on the untouched test semester
    best_model, threshold, _ = fitted[best]
    imp = permutation_importance(best_model, X[test], y[test], scoring="roc_auc",
                                 n_repeats=5, random_state=42, n_jobs=-1)
    importance = pd.DataFrame({
        "Feature": rm.FEATURES, "Label": [rm.FEATURE_LABELS[f] for f in rm.FEATURES],
        "Importance": imp.importances_mean}).sort_values("Importance", ascending=False)
    print("\npermutation importance (drop in ROC-AUC):\n"
          + importance.round(4).to_string(index=False))

    # final models: refit on every labelled semester, then score current students
    known = labelled["NextGPA"].notna()
    bundle = {
        "model_name": best,
        "threshold": threshold,
        "features": rm.FEATURES,
        "risk": CANDIDATES[best]().fit(X, y),
        "gpa": HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_depth=5,
                                             random_state=42).fit(X[known], labelled.loc[known, "NextGPA"]),
        "fail": HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_depth=5,
                                              random_state=42).fit(X[known], labelled.loc[known, "NextFailRate"]),
        "dropout": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)).fit(
            X, labelled["Dropout"]),
        # reference point for explanations: a typical student who was NOT at risk
        "baseline": X[y == 0].median().to_dict(),
        "levers": rm.estimate_levers(snap),
        "trained_on": {"rows": int(len(labelled)), "last_semester": int(last),
                       "at_risk_rate": float(y.mean())},
    }
    config.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, rm.MODEL_FILE)
    (config.MODEL_DIR / "metrics.json").write_text(json.dumps({
        "best_model": best, "threshold": threshold, "target_recall": config.TARGET_RECALL,
        "results": results.drop(columns=["TrainedAt"]).round(4).to_dict("records"),
        "importance": importance.round(5).to_dict("records")}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    with engine.begin() as con:
        results.to_sql("ModelMetrics", con, schema="ml", if_exists="replace", index=False)
        importance.to_sql("FeatureImportance", con, schema="ml", if_exists="replace", index=False)

    scored = rm.score_students(engine, bundle)
    print(f"\nscored {len(scored):,} active students | flagged {scored.IsFlagged.sum():,}")
    print(scored["RiskLevel"].value_counts().reindex(config.RISK_ORDER).to_string())
    print("\nlever associations (within-student):", json.dumps(bundle["levers"], indent=1))
    print("\nexample explanation:")
    ex = scored.sort_values("RiskProbability", ascending=False).iloc[0]
    print(f"  student {ex.StudentKey}: risk {ex.RiskProbability:.0%} -> {ex.MainFactors}")


if __name__ == "__main__":
    main()

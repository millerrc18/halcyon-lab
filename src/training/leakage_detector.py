"""Outcome leakage detector for training data quality assurance.

Tests whether generated commentary inadvertently reveals trade outcomes
by training a classifier to predict win/loss from text alone.
"""

import logging
import sqlite3

logger = logging.getLogger(__name__)


def check_outcome_leakage(db_path: str = "ai_research_desk.sqlite3") -> dict:
    """Test whether generated commentary leaks outcome information.

    Trains a simple classifier (TF-IDF + logistic regression) to predict
    trade outcome (win/loss) from the generated commentary text alone.

    If accuracy > 55%, the pipeline is leaking and prompts need iteration.
    If accuracy <= 55%, the commentary is outcome-independent (good).

    Returns:
        {
            "test_accuracy": 0.53,     # Should be <= 0.55
            "is_leaking": False,
            "n_examples": 200,
            "feature_importance": {     # Which words predict outcomes
                "win_predictors": ["momentum", "clearly", "strong"],
                "loss_predictors": ["however", "risk", "uncertain"],
            },
        }
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_score
        import numpy as np
    except ImportError:
        return {
            "test_accuracy": None,
            "is_leaking": None,
            "n_examples": 0,
            "note": "scikit-learn not installed. Run: pip install scikit-learn",
        }

    # Load examples
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT output_text, source FROM training_examples
            WHERE source IN ('blinded_win', 'blinded_loss', 'outcome_win', 'outcome_loss')
        """).fetchall()

    if len(rows) < 50:
        return {
            "test_accuracy": None,
            "is_leaking": None,
            "n_examples": len(rows),
            "note": "Need at least 50 examples to test for leakage",
        }

    texts = [row["output_text"] for row in rows if row["output_text"]]
    labels = [1 if "win" in row["source"] else 0 for row in rows if row["output_text"]]

    if len(texts) < 50:
        return {
            "test_accuracy": None,
            "is_leaking": None,
            "n_examples": len(texts),
            "note": "Need at least 50 examples with output text to test for leakage",
        }

    vectorizer = TfidfVectorizer(max_features=500, stop_words="english")
    X = vectorizer.fit_transform(texts)

    clf = LogisticRegression(max_iter=1000, random_state=42)
    n_splits = min(5, min(sum(1 for l in labels if l == 1), sum(1 for l in labels if l == 0)))
    if n_splits < 2:
        return {
            "test_accuracy": None,
            "is_leaking": None,
            "n_examples": len(texts),
            "note": "Need at least 2 examples per class for cross-validation",
        }

    scores = cross_val_score(clf, X, labels, cv=n_splits, scoring="accuracy")
    accuracy = float(np.mean(scores))

    # Get feature importance
    clf.fit(X, labels)
    feature_names = vectorizer.get_feature_names_out()
    coefs = clf.coef_[0]
    top_win = [feature_names[i] for i in np.argsort(coefs)[-5:]]
    top_loss = [feature_names[i] for i in np.argsort(coefs)[:5]]

    return {
        "test_accuracy": round(accuracy, 3),
        "is_leaking": accuracy > 0.55,
        "n_examples": len(texts),
        "feature_importance": {
            "win_predictors": list(reversed(top_win)),
            "loss_predictors": list(top_loss),
        },
    }

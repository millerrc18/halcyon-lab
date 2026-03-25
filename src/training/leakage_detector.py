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

    # Mask ticker names and company names to prevent ticker-level correlation
    # from registering as outcome leakage. We want to test whether the
    # COMMENTARY STYLE reveals outcomes, not whether certain tickers won/lost.
    try:
        from src.universe.sp100 import get_sp100_universe
        from src.universe.company_names import COMPANY_NAMES
        tickers = set(t.lower() for t in get_sp100_universe())
        company_words = set()
        for name in COMPANY_NAMES.values():
            for word in name.lower().split():
                if len(word) > 2:  # Skip "of", "the", etc.
                    company_words.add(word)
        # Also mask common ticker-like patterns
        import re
        def mask_text(text):
            masked = text.lower()
            # Replace ticker symbols (standalone uppercase 1-5 letter words)
            for ticker in tickers:
                masked = re.sub(r'\b' + re.escape(ticker) + r'\b', 'TICKER', masked)
            # Replace company name words
            for word in company_words:
                masked = re.sub(r'\b' + re.escape(word) + r'\b', 'COMPANY', masked)
            return masked
        texts = [mask_text(t) for t in texts]
    except Exception:
        pass  # If masking fails, continue with unmasked text

    if len(texts) < 50:
        return {
            "test_accuracy": None,
            "is_leaking": None,
            "n_examples": len(texts),
            "note": "Need at least 50 examples with output text to test for leakage",
        }

    vectorizer = TfidfVectorizer(max_features=100, stop_words="english",
                                   min_df=3, max_df=0.8)
    X = vectorizer.fit_transform(texts)

    # Use strong regularization to prevent overfitting on small datasets
    clf = LogisticRegression(max_iter=1000, random_state=42, C=0.1)
    n_splits = min(5, min(sum(1 for l in labels if l == 1), sum(1 for l in labels if l == 0)))
    if n_splits < 2:
        return {
            "test_accuracy": None,
            "is_leaking": None,
            "n_examples": len(texts),
            "note": "Need at least 2 examples per class for cross-validation",
        }

    # Run multiple random seeds for stability
    all_scores = []
    for seed in [42, 123, 456, 789, 1024]:
        clf_s = LogisticRegression(max_iter=1000, random_state=seed, C=0.1)
        scores = cross_val_score(clf_s, X, labels, cv=n_splits, scoring="accuracy")
        all_scores.extend(scores)
    accuracy = float(np.mean(all_scores))

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

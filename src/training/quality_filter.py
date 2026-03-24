"""LLM-as-Judge quality scoring for training examples."""

import json
import logging
import re
import sqlite3

from src.training.versioning import init_training_tables

logger = logging.getLogger(__name__)

QUALITY_JUDGE_PROMPT = """You are a quality assessor for financial trade commentary training data. Score on 6 dimensions (1-5 each):

1. THESIS CLARITY — is the core trade idea stated clearly and actionably?
2. EVIDENCE QUALITY — are claims grounded in specific data from the input?
3. RISK ASSESSMENT — are risks identified and proportional to the setup?
4. TECHNICAL ACCURACY — are indicators and levels referenced correctly?
5. CALIBRATION — does confidence match the setup quality and outcome?
6. ACTIONABILITY — are entry, exit, and sizing addressed or implied?

Respond with ONLY a JSON object:
{"thesis_clarity": N, "evidence_quality": N, "risk_assessment": N, "technical_accuracy": N, "calibration": N, "actionability": N, "overall": N.N, "issues": "brief note on any problems"}
"""


def score_training_example(input_text: str, output_text: str) -> dict | None:
    """Score a training example using Claude as judge. Returns scores dict or None."""
    from src.training.claude_client import generate_training_example

    prompt = f"""Rate this trade commentary for training data quality.

INPUT (what the model saw):
{input_text[:1500]}

OUTPUT (the commentary to rate):
{output_text[:2000]}

{QUALITY_JUDGE_PROMPT}"""

    response = generate_training_example(
        "You are a quality assessor for financial trade commentary.",
        prompt,
    )

    if not response:
        return None

    # Parse JSON from response
    try:
        json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
        if json_match:
            scores = json.loads(json_match.group())
            # Compute overall if not provided
            if "overall" not in scores:
                dims = ["thesis_clarity", "evidence_quality", "risk_assessment",
                        "technical_accuracy", "calibration", "actionability"]
                values = [scores.get(d, 3) for d in dims]
                scores["overall"] = round(sum(values) / len(values), 1)
            return scores
    except (json.JSONDecodeError, AttributeError):
        pass

    return None


def score_all_unscored(db_path: str = "ai_research_desk.sqlite3") -> dict:
    """Score all training examples without quality_score_auto. Returns summary stats."""
    init_training_tables(db_path)

    # Ensure column exists
    with sqlite3.connect(db_path) as conn:
        try:
            conn.execute("ALTER TABLE training_examples ADD COLUMN quality_score_auto REAL")
        except sqlite3.OperationalError:
            pass

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT example_id, input_text, output_text "
            "FROM training_examples WHERE quality_score_auto IS NULL"
        ).fetchall()

    if not rows:
        return {"scored": 0, "avg_score": 0, "skipped": 0}

    scored = 0
    skipped = 0
    total_score = 0.0

    for row in rows:
        scores = score_training_example(row["input_text"], row["output_text"])
        if scores and "overall" in scores:
            overall = scores["overall"]
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "UPDATE training_examples SET quality_score_auto = ? WHERE example_id = ?",
                    (overall, row["example_id"]),
                )
                conn.commit()
            scored += 1
            total_score += overall
        else:
            skipped += 1

    avg = total_score / scored if scored > 0 else 0

    logger.info("[QUALITY] Scored %d examples (avg: %.2f), skipped %d", scored, avg, skipped)
    return {"scored": scored, "avg_score": round(avg, 2), "skipped": skipped}

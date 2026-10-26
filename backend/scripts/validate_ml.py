"""Validation sweep for the local ML tier.

Trains the candidate pipeline on hand-labeled examples only (rules.py
keyword contracts + curated noisy variants) with stratified cross-validation,
measures how often the correct category clears candidate (score, margin)
gates on held-out rows, and scores a hand-written "must stay in review"
junk corpus to check the same gates reject unfamiliar wording.

Run from backend/:  ./.venv/Scripts/python.exe scripts/validate_ml.py

The printed table is the validation evidence for the default
MIN_SCORE / MIN_MARGIN choice in app.categorizer.ml.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import FeatureUnion, Pipeline

from app.categorizer import ml
from app.categorizer.ml import (
    MIN_EXAMPLES_PER_CATEGORY,
    build_training_examples,
    normalize_description,
)

# Hand-written descriptions that are deliberately NOT any trained merchant:
# unfamiliar stores, generic expenses, nonsense. None may auto-categorize.
JUNK_CORPUS = [
    "JOES CAFE 9921",
    "bright lane laundry",
    "OFFICE RENT MAIN ST 4412",
    "CITY WATER UTILITY BILL",
    "TOTALLY UNHEARD MERCHANT XYZ",
    "green park parking meters",
    "sunset barber shop 7781",
    "happy tails pet grooming 441",
    "quick stop liquors 882",
    "midtown shoe repair 9021",
]


def make_pipeline(c_value: float):
    features = FeatureUnion(
        [
            ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)),
        ]
    )
    return Pipeline([("features", features), ("model", LogisticRegression(max_iter=1000, C=c_value))])


def main() -> None:
    examples = build_training_examples()
    counts: dict[str, int] = {}
    for _, category in examples:
        counts[category] = counts.get(category, 0) + 1
    usable = {c for c, n in counts.items() if n >= MIN_EXAMPLES_PER_CATEGORY}
    usable_examples = [(d, c) for d, c in examples if c in usable]
    texts = [normalize_description(d) for d, _ in usable_examples]
    labels = [c for _, c in usable_examples]
    print(f"labeled examples: {len(usable_examples)} across {len(usable)} categories")

    thresholds = [(0.40, 0.10), (0.50, 0.15), (0.55, 0.15), (0.65, 0.15), (0.70, 0.20)]
    folds = StratifiedKFold(n_splits=4, shuffle=True, random_state=7)

    for c_value in (1.0, 3.0, 10.0, 30.0):
        results: list[tuple[str, str, float, float]] = []
        for train_idx, test_idx in folds.split(texts, labels):
            pipe = make_pipeline(c_value)
            pipe.fit([texts[i] for i in train_idx], [labels[i] for i in train_idx])
            probs = pipe.predict_proba([texts[i] for i in test_idx])
            classes = list(pipe.named_steps["model"].classes_)
            order = probs.argsort(axis=1)[:, ::-1]
            for row, i in enumerate(test_idx):
                top, second = order[row][0], order[row][1]
                results.append(
                    (
                        classes[top],
                        labels[i],
                        float(probs[row][top]),
                        float(probs[row][top] - probs[row][second]),
                    )
                )

        top1 = sum(1 for pred, truth, _, _ in results if pred == truth) / len(results)
        print(f"\nC={c_value}: held-out top-1 accuracy {top1:.2f}")
        rejected_top = [
            s
            for s, _ in sorted(
                ((r[2], r[0]) for r in results if r[0] != r[1]),
                key=lambda pair: -pair[0],
            )[:3]
        ]
        print(f"  highest scores among WRONG held-out predictions: "
              f"{[round(s, 2) for s in rejected_top]}")

        # Junk corpus scored by a model trained on ALL usable examples.
        full = make_pipeline(c_value)
        full.fit(texts, labels)
        junk_scores = []
        for line in JUNK_CORPUS:
            # Score each junk line with this C's model directly.
            cleaned = normalize_description(line)
            proba = full.predict_proba([cleaned])[0] if cleaned else None
            cls = list(full.named_steps["model"].classes_)
            best = proba.max() if proba is not None else 0.0
            junk_scores.append((line, cls[int(proba.argmax())] if proba is not None else "-", round(float(best), 3)))
        print("  junk-corpus top scores:", [j[2] for j in junk_scores])
        worst_junk = max(junk_scores, default=None, key=lambda j: j[2])
        if worst_junk:
            print(f"  junk max score: {worst_junk[2]} ({worst_junk[0]!r} -> {worst_junk[1]})")

        for threshold, margin_gate in thresholds:
            keep = sum(
                1
                for pred, truth, score, margin in results
                if pred == truth and score >= threshold and margin >= margin_gate
            )
            wanted = sum(1 for pred, truth, _, _ in results if pred == truth)
            print(
                f"  gate score>={threshold} margin>={margin_gate}: "
                f"{keep}/{wanted} correct rows auto-categorized"
            )
        print()

if __name__ == "__main__":
    main()

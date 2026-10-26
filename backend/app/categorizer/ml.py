"""Locally trained text classifier for ordinary spending categories.

This is still "own code" under the task's big rule: a small, classical
scikit-learn model (TF-IDF word + character n-grams -> LogisticRegression)
trained at startup on hand-written label contracts from rules.py and
training_data.py. Nothing external decides a category — no LLM, no API.

It never handles transaction *semantics*: transfers, credit-card payments,
fee reversals, income and refund wording are decided by the keyword tiers
in engine.py before this model is consulted, and the model is only asked
about debits (expenses). If scikit-learn is missing, the labeled data is
insufficient, or anything fails, the model switches off and the engine
falls back to its previous keyword-only behavior. An upload can never
crash because of this module.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from .. import categories as cat
from . import rules
from .training_data import CURATED_LABELED_EXAMPLES

logger = logging.getLogger(__name__)

#: Conservative auto-category gates. A suggestion only auto-categorizes a
#: row when the top class scores at least MIN_SCORE and clearly beats the
#: runner-up (margin >= MIN_MARGIN). Override via env vars ML_MIN_SCORE /
#: ML_MIN_MARGIN; treat scores as screening signals, not true probabilities.
MIN_SCORE = float(os.getenv("ML_MIN_SCORE", "0.65"))
MIN_MARGIN = float(os.getenv("ML_MIN_MARGIN", "0.15"))

#: Categories with fewer usable labeled examples than this are excluded from
#: training rather than pretending the model is reliable for them.
MIN_EXAMPLES_PER_CATEGORY = 3

_REF_NOISE = re.compile(r"\d{4,}")  # reference/order/phone numbers
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_MULTI_SPACE = re.compile(r"\s+")


def normalize_description(text: str) -> str:
    """Lowercase, drop reference numbers/punctuation, collapse whitespace.

    Long digit runs (order ids, authorization codes, phone fragments) are
    noise; ALL other digits stay so merchant words like "365" survive.
    Merchant wording itself is never removed.
    """
    lowered = _REF_NOISE.sub(" ", text.lower())
    lowered = _NON_ALNUM.sub(" ", lowered)
    return _MULTI_SPACE.sub(" ", lowered).strip()


@dataclass(frozen=True)
class MLPrediction:
    """Raw model output; the engine applies MIN_SCORE / MIN_MARGIN."""

    category: str
    confidence: float
    margin: float
    runner_up: str


@dataclass
class MLClassifier:
    categories: tuple[str, ...]
    categories_excluded: tuple[str, ...] = ()
    trained_examples: int = 0
    pipeline: object = None


def build_training_examples() -> list[tuple[str, str]]:
    """Hand-written (description, category) pairs from the rule tables.

    Each merchant rule's keyword sequence is itself a human label ("a
    description containing STARBUCKS is Meals & Entertainment"); curated
    noisy variants in training_data.py add realistic wording. Conflicting
    or out-of-domain labels are dropped rather than guessed.
    """
    seen: dict[str, str] = {}
    conflict = "\x00conflict"
    for rule in rules.MERCHANT_RULES:
        key = normalize_description(" ".join(rule.keywords))
        seen.setdefault(key, rule.category)
    for description, category in CURATED_LABELED_EXAMPLES:
        if category not in cat.SPENDING_SET:
            raise ValueError(
                f"Curated example labeled with non-spending category: {description!r}"
            )
        key = normalize_description(description)
        if not key:
            raise ValueError(f"Curated example normalizes to empty: {description!r}")
        if key in seen and seen[key] != category:
            seen[key] = conflict
            logger.warning("Conflicting hand labels for %r; dropping the pair", key)
        else:
            seen.setdefault(key, category)
    return sorted((d, c) for d, c in seen.items() if c != conflict)


def _build_pipeline():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, Pipeline

    features = FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True),
            ),
            (
                "char",
                TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True),
            ),
        ]
    )
    # C=3.0 chosen by scripts/validate_ml.py: at the default C=1.0 the model
    # is so regularized that no held-out row clears 0.65 (0/75 correct), while
    # C=30 pushes wrong held-out predictions to 0.74, through the gate.
    return Pipeline(
        [
            ("features", features),
            ("model", LogisticRegression(max_iter=1000, C=3.0)),
        ]
    )


_classifier: MLClassifier | None = None
_build_attempted = False


def get_classifier() -> MLClassifier | None:
    """Train once per process; return None whenever ML cannot help."""
    global _classifier, _build_attempted
    if _build_attempted:
        return _classifier
    _build_attempted = True
    try:
        examples = build_training_examples()
        counts: dict[str, int] = {}
        for _, category in examples:
            counts[category] = counts.get(category, 0) + 1
        usable = {c for c, n in counts.items() if n >= MIN_EXAMPLES_PER_CATEGORY}
        excluded = tuple(sorted(set(counts) - usable))
        if len(usable) < 2:
            logger.warning(
                "ML tier disabled: only %d spending category/ies have >= %d "
                "labeled examples; falling back to keyword rules",
                len(usable),
                MIN_EXAMPLES_PER_CATEGORY,
            )
            return _classifier
        usable_examples = [(d, c) for d, c in examples if c in usable]
        pipeline = _build_pipeline()
        pipeline.fit(
            [normalize_description(d) for d, _ in usable_examples],
            [c for _, c in usable_examples],
        )
        _classifier = MLClassifier(
            categories=tuple(sorted(usable)),
            categories_excluded=excluded,
            trained_examples=len(usable_examples),
            pipeline=pipeline,
        )
        logger.info(
            "ML tier trained: %d examples across %d categories%s",
            len(usable_examples),
            len(usable),
            f" (excluded: {', '.join(excluded)})" if excluded else "",
        )
    except ImportError:
        logger.warning("scikit-learn is not installed; ML tier disabled, rules only")
        _classifier = None
    except Exception:
        logger.exception("ML training failed; falling back to keyword rules only")
        _classifier = None
    return _classifier


def suggest(description: str) -> MLPrediction | None:
    """Rank categories for a description; None when no model or a failure."""
    model = get_classifier()
    if model is None or not description or not description.strip():
        return None
    try:
        cleaned = normalize_description(description)
        if not cleaned:
            return None
        probabilities = model.pipeline.predict_proba([cleaned])[0]
        classes = list(model.pipeline.named_steps["model"].classes_)
        ranked = sorted(zip(classes, probabilities), key=lambda pair: pair[1], reverse=True)
        (top_category, top_score), (runner_up, runner_score) = ranked[0], ranked[1]
        return MLPrediction(
            category=str(top_category),
            confidence=float(top_score),
            margin=float(top_score - runner_score),
            runner_up=str(runner_up),
        )
    except Exception:
        logger.exception("ML inference failed; treating row as unclassified")
        return None


def reset_classifier() -> None:
    """Test hook: force a rebuild on the next get_classifier() call."""
    global _classifier, _build_attempted
    _classifier = None
    _build_attempted = False

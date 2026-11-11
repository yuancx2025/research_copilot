"""Metric helpers shared by the evaluation suites."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence


def percentile(values: Sequence[float], q: float) -> Optional[float]:
    """Linear-interpolated percentile (q in 0..100); None for no values."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 4)
    rank = (len(ordered) - 1) * q / 100
    low, high = math.floor(rank), math.ceil(rank)
    value = ordered[low] + (ordered[high] - ordered[low]) * (rank - low)
    return round(value, 4)


def _ratio(num: float, den: float) -> Optional[float]:
    return round(num / den, 4) if den else None


def _f1(p: Optional[float], r: Optional[float]) -> Optional[float]:
    if p is None or r is None:
        return None
    return round(2 * p * r / (p + r), 4) if (p + r) else 0.0


@dataclass
class LabelCounts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def scores(self) -> dict:
        p = _ratio(self.tp, self.tp + self.fp)
        r = _ratio(self.tp, self.tp + self.fn)
        f1 = _f1(p, r)
        if f1 is None and self.fp:
            f1 = 0.0  # only ever selected wrongly: count it, or macro F1 would ignore the mistakes
        return {"precision": p, "recall": r, "f1": f1,
                "support": self.tp + self.fn, "tp": self.tp, "fp": self.fp, "fn": self.fn}


@dataclass(frozen=True)
class LabelledPrediction:
    """One multi-label decision.

    ``required`` labels must be predicted (missing one is a false negative).
    ``acceptable`` labels may be predicted without penalty. Anything else
    predicted is a false positive.
    """
    predicted: frozenset
    required: frozenset
    acceptable: frozenset = frozenset()

    @property
    def false_positives(self) -> frozenset:
        return self.predicted - self.required - self.acceptable

    @property
    def false_negatives(self) -> frozenset:
        return self.required - self.predicted

    @property
    def correct(self) -> bool:
        return not self.false_positives and not self.false_negatives


def score_multilabel(items: Iterable[LabelledPrediction], labels: Sequence[str]) -> dict:
    """Per-label and aggregate precision/recall/F1 with acceptable labels ignored."""
    items = list(items)
    counts = {label: LabelCounts() for label in labels}
    for item in items:
        for label in item.predicted & item.required:
            counts.setdefault(label, LabelCounts()).tp += 1
        for label in item.false_positives:
            counts.setdefault(label, LabelCounts()).fp += 1
        for label in item.false_negatives:
            counts.setdefault(label, LabelCounts()).fn += 1

    total = LabelCounts(
        tp=sum(c.tp for c in counts.values()),
        fp=sum(c.fp for c in counts.values()),
        fn=sum(c.fn for c in counts.values()),
    )
    per_label = {label: c.scores() for label, c in counts.items()}
    scored = [s["f1"] for s in per_label.values() if s["f1"] is not None and (s["support"] or s["fp"])]
    micro = total.scores()
    return {
        "micro": {k: micro[k] for k in ("precision", "recall", "f1")},
        "macro_f1": round(sum(scored) / len(scored), 4) if scored else None,
        "case_accuracy": _ratio(sum(1 for i in items if i.correct), len(items)),
        "avg_sources_selected": _ratio(sum(len(i.predicted) for i in items), len(items)),
        "per_label": per_label,
    }

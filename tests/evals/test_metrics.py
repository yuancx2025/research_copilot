import pytest

from research_copilot.evals.metrics import LabelledPrediction, percentile, score_multilabel


def _p(predicted, required, acceptable=()):
    return LabelledPrediction(frozenset(predicted), frozenset(required), frozenset(acceptable))


def test_acceptable_labels_are_not_false_positives():
    item = _p({"arxiv", "web", "local"}, {"arxiv"}, {"local"})
    assert item.false_positives == {"web"}
    assert item.false_negatives == frozenset()
    assert not item.correct
    assert _p({"arxiv", "local"}, {"arxiv"}, {"local"}).correct


def test_micro_and_per_label_scores():
    items = [
        _p({"arxiv"}, {"arxiv"}),                    # tp arxiv
        _p({"arxiv", "youtube"}, {"arxiv", "web"}),  # tp arxiv, fp youtube, fn web
        _p({"web"}, {"web"}, {"local"}),             # tp web
    ]
    scores = score_multilabel(items, ["arxiv", "youtube", "web", "local"])
    assert scores["micro"] == {"precision": 0.75, "recall": 0.75, "f1": 0.75}
    assert scores["per_label"]["arxiv"]["f1"] == 1.0
    assert scores["per_label"]["youtube"]["precision"] == 0.0
    assert scores["per_label"]["web"]["recall"] == 0.5
    # local was never required or predicted, so it does not dilute the macro average
    assert scores["per_label"]["local"]["f1"] is None
    assert scores["macro_f1"] == pytest.approx((1.0 + 0.0 + 0.6667) / 3, abs=1e-3)
    assert scores["case_accuracy"] == pytest.approx(2 / 3, abs=1e-3)


def test_percentile_interpolates_and_handles_empty():
    assert percentile([], 95) is None
    assert percentile([2.0], 95) == 2.0
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile(list(range(1, 101)), 95) == pytest.approx(95.05)

from __future__ import annotations

from hiresense.ingestion.domain.closure_detector import OpenJob, detect_closures


def test_seen_resets_missed_count():
    upd, close = detect_closures(
        seen={"k1"}, open_jobs=[OpenJob("j1", "k1", missed_count=1)], threshold=2,
    )
    assert upd["j1"] == 0 and close == []


def test_missing_increments_below_threshold():
    upd, close = detect_closures(
        seen=set(), open_jobs=[OpenJob("j1", "k1", missed_count=0)], threshold=2,
    )
    assert upd["j1"] == 1 and close == []


def test_missing_at_threshold_closes():
    upd, close = detect_closures(
        seen=set(), open_jobs=[OpenJob("j1", "k1", missed_count=1)], threshold=2,
    )
    assert close == ["j1"]

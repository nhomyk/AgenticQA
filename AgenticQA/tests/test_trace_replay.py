"""Tests for deterministic trace replay."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agenticqa.verification import TraceReplay, Tracer


def _create_trace(tracer: Tracer, with_error: bool = False) -> str:
    trace_id = tracer.new_trace()
    with tracer.span(trace_id, "validation", agent="QA_Assistant"):
        pass

    if with_error:
        try:
            with tracer.span(trace_id, "delegation", agent="SDET_Agent"):
                raise RuntimeError("failure")
        except RuntimeError:
            pass
    else:
        with tracer.span(trace_id, "delegation", agent="SDET_Agent"):
            pass

    return trace_id


def test_export_and_replay_bundle(tmp_path):
    tracer = Tracer(db_path=str(tmp_path / "traces.db"))
    replay = TraceReplay(tracer)

    trace_id = _create_trace(tracer)
    bundle = replay.export_bundle(trace_id)
    result = replay.replay_bundle(bundle)

    assert result.replayable is True
    assert result.steps == 2
    assert result.operation_sequence == ["validation", "delegation"]
    assert result.status_sequence == ["success", "success"]

    tracer.close()


def test_compare_detects_non_deterministic_status(tmp_path):
    tracer = Tracer(db_path=str(tmp_path / "traces.db"))
    replay = TraceReplay(tracer)

    good = replay.export_bundle(_create_trace(tracer, with_error=False))
    bad = replay.export_bundle(_create_trace(tracer, with_error=True))

    diff = replay.compare(good, bad)
    assert diff["deterministic_match"] is False

    tracer.close()

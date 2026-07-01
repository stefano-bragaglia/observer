import signal
import threading
import time
from pathlib import Path

from observer.events import EventType
from observer.observer import Observer

INTERVAL = 0.5
FAST_BOUND = 0.2
MARGIN = 0.05


class RecordingObserver(Observer):
    def __init__(self, folder):
        super().__init__(folder)
        self.events = []

    def notify(self, event, path):
        self.events.append((event, path))


def start_run(observer: Observer, **kwargs) -> threading.Thread:
    errors = []

    def target():
        try:
            observer.run(**kwargs)
        except Exception as exc:  # pragma: no cover - only hit on real failure
            errors.append(exc)

    thread = threading.Thread(target=target, daemon=True)
    thread.errors = errors
    thread.start()
    return thread


def test_stop_from_another_thread_returns_well_under_interval(tmp_path: Path) -> None:
    observer = RecordingObserver(tmp_path)
    thread = start_run(observer, interval=INTERVAL)
    time.sleep(MARGIN)

    started_at = time.monotonic()
    observer.stop()
    thread.join(timeout=1.0)
    elapsed = time.monotonic() - started_at

    assert not thread.is_alive()
    assert elapsed < FAST_BOUND
    assert thread.errors == []


def test_stop_before_run_does_not_raise_and_run_still_works(tmp_path: Path) -> None:
    observer = RecordingObserver(tmp_path)

    observer.stop()

    thread = start_run(observer, interval=0.02)
    time.sleep(0.1)
    (tmp_path / "new.txt").write_bytes(b"new")
    time.sleep(0.1)
    observer.stop()
    thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert thread.errors == []
    assert (EventType.CREATED, "new.txt") in observer.events


def test_stop_called_twice_does_not_raise(tmp_path: Path) -> None:
    observer = RecordingObserver(tmp_path)

    observer.stop()
    observer.stop()


def test_run_on_background_thread_does_not_raise_and_responds_to_stop(
    tmp_path: Path,
) -> None:
    observer = RecordingObserver(tmp_path)

    thread = start_run(observer, interval=0.02)
    time.sleep(0.1)
    (tmp_path / "new.txt").write_bytes(b"new")
    time.sleep(0.1)
    observer.stop()
    thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert thread.errors == []
    assert (EventType.CREATED, "new.txt") in observer.events


def test_registered_signal_handler_calls_stop(tmp_path: Path, monkeypatch) -> None:
    observer = RecordingObserver(tmp_path)
    captured: dict[int, object] = {}

    def fake_signal(signum, handler):
        captured[signum] = handler

    monkeypatch.setattr(signal, "signal", fake_signal)

    thread = start_run(observer, interval=0.02)
    time.sleep(0.1)

    assert signal.SIGTERM in captured
    assert signal.SIGINT in captured

    captured[signal.SIGTERM](signal.SIGTERM, None)

    thread.join(timeout=1.0)
    assert not thread.is_alive()
    assert observer._stop_event.is_set()

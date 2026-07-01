import threading
import time
from pathlib import Path

from observer.events import EventType
from observer.observer import Observer

INTERVAL = 0.02
MARGIN = INTERVAL * 5


class RecordingObserver(Observer):
    def __init__(self, folder):
        super().__init__(folder)
        self.events = []

    def notify(self, event, path):
        self.events.append((event, path))


def start_run(observer: Observer, **kwargs) -> threading.Thread:
    thread = threading.Thread(
        target=observer.run, kwargs={"interval": INTERVAL, **kwargs}, daemon=True
    )
    thread.start()
    return thread


def stop_and_join(observer: Observer, thread: threading.Thread) -> None:
    observer.stop()
    thread.join(timeout=1.0)
    assert not thread.is_alive()


def test_preexisting_file_silent_new_file_fires_created(tmp_path: Path) -> None:
    (tmp_path / "old.txt").write_bytes(b"old")
    observer = RecordingObserver(tmp_path)

    thread = start_run(observer)
    time.sleep(MARGIN)
    (tmp_path / "new.txt").write_bytes(b"new")
    time.sleep(MARGIN)
    stop_and_join(observer, thread)

    assert (EventType.CREATED, "new.txt") in observer.events
    assert not any(path == "old.txt" for _event, path in observer.events)


def test_report_existing_fires_found_for_preexisting_file(tmp_path: Path) -> None:
    (tmp_path / "old.txt").write_bytes(b"old")
    observer = RecordingObserver(tmp_path)

    thread = start_run(observer, report_existing=True)
    time.sleep(MARGIN)
    stop_and_join(observer, thread)

    assert (EventType.FOUND, "old.txt") in observer.events


def test_recursive_true_detects_file_in_subdirectory(tmp_path: Path) -> None:
    observer = RecordingObserver(tmp_path)

    thread = start_run(observer, recursive=True)
    time.sleep(MARGIN)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.txt").write_bytes(b"nested")
    time.sleep(MARGIN)
    stop_and_join(observer, thread)

    assert (EventType.CREATED, "sub/nested.txt") in observer.events


def test_recursive_false_ignores_file_in_subdirectory(tmp_path: Path) -> None:
    observer = RecordingObserver(tmp_path)

    thread = start_run(observer)
    time.sleep(MARGIN)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.txt").write_bytes(b"nested")
    time.sleep(MARGIN)
    stop_and_join(observer, thread)

    assert observer.events == []


def test_include_hidden_true_detects_dotfile(tmp_path: Path) -> None:
    observer = RecordingObserver(tmp_path)

    thread = start_run(observer, include_hidden=True)
    time.sleep(MARGIN)
    (tmp_path / ".hidden").write_bytes(b"hidden")
    time.sleep(MARGIN)
    stop_and_join(observer, thread)

    assert (EventType.CREATED, ".hidden") in observer.events


def test_include_hidden_false_ignores_dotfile(tmp_path: Path) -> None:
    observer = RecordingObserver(tmp_path)

    thread = start_run(observer)
    time.sleep(MARGIN)
    (tmp_path / ".hidden").write_bytes(b"hidden")
    time.sleep(MARGIN)
    stop_and_join(observer, thread)

    assert observer.events == []


def test_loop_performs_multiple_cycles_detecting_created_then_modified(
    tmp_path: Path,
) -> None:
    path = tmp_path / "a.txt"
    observer = RecordingObserver(tmp_path)

    thread = start_run(observer)
    time.sleep(MARGIN)
    path.write_bytes(b"aaaaa")
    time.sleep(MARGIN)
    assert (EventType.CREATED, "a.txt") in observer.events

    path.write_bytes(b"bbbbb")
    time.sleep(MARGIN)
    stop_and_join(observer, thread)

    assert (EventType.MODIFIED, "a.txt") in observer.events


def test_run_called_twice_on_same_instance_seeds_and_polls_again(
    tmp_path: Path,
) -> None:
    observer = RecordingObserver(tmp_path)

    thread = start_run(observer)
    time.sleep(MARGIN)
    stop_and_join(observer, thread)
    observer.events.clear()

    thread = start_run(observer)
    time.sleep(MARGIN)
    (tmp_path / "second.txt").write_bytes(b"second")
    time.sleep(MARGIN)
    stop_and_join(observer, thread)

    assert (EventType.CREATED, "second.txt") in observer.events


def test_own_log_file_is_never_treated_as_a_watched_path(tmp_path: Path) -> None:
    observer = RecordingObserver(tmp_path)

    thread = start_run(observer)
    time.sleep(MARGIN)
    (tmp_path / "a.txt").write_bytes(b"hello")
    time.sleep(MARGIN * 10)
    stop_and_join(observer, thread)

    assert not any(path == "log.txt" for _event, path in observer.events)

import re

import pytest

from observer.events import EventType
from observer.observer import Observer

EVENT_HOOK_MAP = {
    EventType.CREATED: "notify_created",
    EventType.MODIFIED: "notify_modified",
    EventType.DELETED: "notify_deleted",
    EventType.FOUND: "notify_found",
    EventType.ERROR: "notify_error",
}

LOG_LINE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T[\d:.]+ (\S+) (.+)$")


class RecordingObserver(Observer):
    def __init__(self, folder):
        super().__init__(folder)
        self.calls = []

    def notify(self, event, path):
        self.calls.append(("notify", event, path))

    def notify_created(self, path):
        self.calls.append(("notify_created", path))

    def notify_modified(self, path):
        self.calls.append(("notify_modified", path))

    def notify_deleted(self, path):
        self.calls.append(("notify_deleted", path))

    def notify_found(self, path):
        self.calls.append(("notify_found", path))

    def notify_error(self, path):
        self.calls.append(("notify_error", path))


class _UnrecognizedEvent:
    """Duck-types an EventType member (has `.name`) but isn't one."""

    name = "BOGUS"


@pytest.mark.parametrize("event", list(EventType))
def test_notify_writes_log_line_and_dispatches_hooks_in_order(tmp_path, event):
    observer = RecordingObserver(tmp_path)
    path = "a/b.txt"

    observer._notify(event, path)

    hook_name = EVENT_HOOK_MAP[event]
    assert observer.calls == [("notify", event, path), (hook_name, path)]

    log_lines = (tmp_path / "log.txt").read_text().splitlines()
    assert len(log_lines) == 1
    match = LOG_LINE_RE.match(log_lines[0])
    assert match is not None
    assert match.group(1) == event.name
    assert match.group(2) == path


def test_two_notify_calls_append_two_lines_without_truncating(tmp_path):
    observer = RecordingObserver(tmp_path)

    observer._notify(EventType.CREATED, "a.txt")
    observer._notify(EventType.DELETED, "a.txt")

    log_lines = (tmp_path / "log.txt").read_text().splitlines()
    assert len(log_lines) == 2
    assert " CREATED a.txt" in log_lines[0]
    assert " DELETED a.txt" in log_lines[1]


def test_constructing_observer_truncates_preexisting_log(tmp_path):
    log_path = tmp_path / "log.txt"
    log_path.write_text("stale content from a previous run\n")

    Observer(tmp_path)

    assert log_path.read_text() == ""


def test_base_notify_created_still_called_when_only_notify_is_overridden(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(Observer, "notify_created", lambda self, path: calls.append(path))

    class OverrideNotifyOnly(Observer):
        def notify(self, event, path):
            pass

    instance = OverrideNotifyOnly(tmp_path)
    instance._notify(EventType.CREATED, "a.txt")

    assert calls == ["a.txt"]


def test_base_notify_still_called_when_only_notify_created_is_overridden(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(Observer, "notify", lambda self, event, path: calls.append((event, path)))

    class OverrideCreatedOnly(Observer):
        def notify_created(self, path):
            pass

    instance = OverrideCreatedOnly(tmp_path)
    instance._notify(EventType.CREATED, "a.txt")

    assert calls == [(EventType.CREATED, "a.txt")]


def test_unrecognized_event_type_logs_and_calls_notify_before_raising(tmp_path):
    observer = RecordingObserver(tmp_path)
    bad_event = _UnrecognizedEvent()

    with pytest.raises(ValueError):
        observer._notify(bad_event, "a.txt")

    assert observer.calls == [("notify", bad_event, "a.txt")]
    log_lines = (tmp_path / "log.txt").read_text().splitlines()
    assert len(log_lines) == 1
    assert log_lines[0].endswith("BOGUS a.txt")

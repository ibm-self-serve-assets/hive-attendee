from backend import app as backend_app


class _Watcher:
    def __init__(self, clean):
        self.clean = clean


def _state(monkeypatch, status, codes, topics_ready=False):
    s = backend_app.store
    monkeypatch.setattr(s, "connection_status", status)
    monkeypatch.setattr(s, "connection_issues", [{"code": c} for c in codes])
    monkeypatch.setattr(s, "event_topics_ready", topics_ready)


def test_reconnects_when_schemas_were_the_only_problem_and_are_now_fixed(monkeypatch):
    _state(monkeypatch, "failed", ["schema_subjects_missing"])
    assert backend_app._confluent_content_fixed(_Watcher(clean=True))


def test_keeps_the_error_while_schemas_are_still_wrong(monkeypatch):
    _state(monkeypatch, "failed", ["schema_subjects_differ"])
    assert not backend_app._confluent_content_fixed(_Watcher(clean=False))


def test_reconnects_when_topics_were_the_problem_and_now_exist(monkeypatch):
    _state(monkeypatch, "failed", ["confluent_topics_missing"], topics_ready=True)
    assert backend_app._confluent_content_fixed(_Watcher(clean=False))


def test_keeps_the_error_while_topics_are_still_missing(monkeypatch):
    _state(monkeypatch, "failed", ["confluent_topics_missing"], topics_ready=False)
    assert not backend_app._confluent_content_fixed(_Watcher(clean=True))


def test_other_failures_are_never_retried_automatically(monkeypatch):
    _state(monkeypatch, "failed", ["confluent_auth_failed"], topics_ready=True)
    assert not backend_app._confluent_content_fixed(_Watcher(clean=True))
    _state(monkeypatch, "failed", ["schema_subjects_missing", "confluent_auth_failed"])
    assert not backend_app._confluent_content_fixed(_Watcher(clean=True))


def test_nothing_to_do_when_connected_or_connecting(monkeypatch):
    _state(monkeypatch, "connected", [])
    assert not backend_app._confluent_content_fixed(_Watcher(clean=True))
    _state(monkeypatch, "connecting", ["schema_subjects_missing"])
    assert not backend_app._confluent_content_fixed(_Watcher(clean=True))

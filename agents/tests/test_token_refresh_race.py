"""The token-refresh race: a stale token must never clobber a fresh one.

Two processes can both take a 401 and both refresh. The old code did a plain
`set()`, which makes the LAST writer win -- and the last writer is not the newest
token. So a stale token could overwrite a fresh one, and every upload after it
would 401 again until the next refresh. One race, and the channel is quietly
broken for hours.

The fix is a transactional compare-and-swap on `obtained_at`: the newest token
always wins regardless of write order. These tests drive the real
`_save_token_atomic` against a fake Firestore, so they fail if the swap becomes
an unconditional write again.
"""
import pytest


def _mpp():
    return pytest.importorskip("utils.multi_platform_publisher")


class _Snap:
    def __init__(self, data):
        self._d = data
        self.exists = bool(data)

    def to_dict(self):
        return self._d


class _Txn:
    def __init__(self, store):
        self._store = store

    def set(self, ref, data, merge=False):
        self._store.update(data)


class _Ref:
    def __init__(self, store):
        self._store = store

    def get(self, transaction=None):
        return _Snap(self._store)


class _Coll:
    def __init__(self, store):
        self._store = store

    def document(self, key):
        return _Ref(self._store)


class _DB:
    """A one-document fake that actually reflects writes, so a second call sees
    what the first one wrote. Without that, the 'stale must not clobber' case
    cannot be distinguished from 'stale was never tried'."""

    def __init__(self, data):
        self._store = dict(data)

    def collection(self, name):
        return _Coll(self._store)

    def transaction(self):
        return _Txn(self._store)


def _armed(monkeypatch, mpp, initial):
    """Patch the transactional decorator to identity and install the fake db."""
    monkeypatch.setattr("google.cloud.firestore.transactional", lambda f: f)
    monkeypatch.setattr(mpp, "get_firestore_client", lambda: _DB(initial))
    monkeypatch.setattr(mpp, "security_audit", lambda *a, **k: None)


def test_stale_token_does_not_clobber_a_fresh_one(monkeypatch):
    mpp = _mpp()
    _armed(monkeypatch, mpp, {"obtained_at": 100.0, "value": "fresh"})

    assert mpp._save_token_atomic("TIKTOK_ACCESS_TOKEN", "stale", 50.0) is False


def test_fresh_token_wins(monkeypatch):
    mpp = _mpp()
    _armed(monkeypatch, mpp, {"obtained_at": 100.0, "value": "old"})

    assert mpp._save_token_atomic("TIKTOK_ACCESS_TOKEN", "fresh", 200.0) is True


def test_a_stale_token_cannot_clobber_after_a_fresh_one_landed(monkeypatch):
    """The actual race, in order: fresh lands, then the stale writer arrives."""
    mpp = _mpp()
    db = _DB({"obtained_at": 100.0, "value": "old"})
    monkeypatch.setattr("google.cloud.firestore.transactional", lambda f: f)
    monkeypatch.setattr(mpp, "get_firestore_client", lambda: db)
    monkeypatch.setattr(mpp, "security_audit", lambda *a, **k: None)

    assert mpp._save_token_atomic("TIKTOK_ACCESS_TOKEN", "fresh", 200.0) is True
    assert mpp._save_token_atomic("TIKTOK_ACCESS_TOKEN", "stale", 150.0) is False
    assert db._store["value"] == "fresh", (
        f"the stale writer clobbered the fresh token: {db._store}"
    )


def test_first_write_lands_when_nothing_is_stored(monkeypatch):
    """Existing token docs have no obtained_at, so the first write must succeed."""
    mpp = _mpp()
    _armed(monkeypatch, mpp, {})

    assert mpp._save_token_atomic("TIKTOK_ACCESS_TOKEN", "first", 1.0) is True


def test_no_firestore_is_not_a_silent_success(monkeypatch):
    """Returning False here means the caller can tell the write did not happen."""
    mpp = _mpp()
    monkeypatch.setattr(mpp, "get_firestore_client", lambda: None)
    monkeypatch.setattr(mpp, "security_audit", lambda *a, **k: None)

    assert mpp._save_token_atomic("TIKTOK_ACCESS_TOKEN", "x", 1.0) is False


def test_a_failing_write_does_not_raise(monkeypatch):
    """A Firestore outage during a refresh must not kill the upload path."""
    mpp = _mpp()

    def _boom():
        raise RuntimeError("firestore down")

    monkeypatch.setattr(mpp, "get_firestore_client", _boom)
    monkeypatch.setattr(mpp, "security_audit", lambda *a, **k: None)

    assert mpp._save_token_atomic("TIKTOK_ACCESS_TOKEN", "x", 1.0) is False

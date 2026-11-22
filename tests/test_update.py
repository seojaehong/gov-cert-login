import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import version  # noqa: E402

URL = "https://github.com/o/r/releases/download/v9.9.9/GovLogin_setup_9.9.9.exe"


def rel(digest="sha256:ABC", url=URL, name="GovLogin_setup_9.9.9.exe"):
    return {"tag_name": "v9.9.9", "assets": [{"name": "notes.txt"}, {"name": name, "digest": digest, "browser_download_url": url}]}


def test_pick_setup_ok():
    assert version.pick_setup(rel()) == {"ver": "9.9.9", "url": URL, "sha256": "abc"}


def test_pick_setup_refuses_without_digest_or_foreign_url():
    assert version.pick_setup(rel(digest="")) is None
    assert version.pick_setup(rel(url="https://evil.example/x.exe")) is None
    assert version.pick_setup(rel(name="other.exe")) is None


def test_install_update_rejects_hash_mismatch(monkeypatch):
    import launcher
    data = b"setup-bytes"

    class R:
        def read(self):
            return data

    monkeypatch.setattr(launcher.urllib.request, "urlopen", lambda *a, **k: R())
    ran = []
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *a, **k: ran.append(a))
    assert launcher._install_update({"ver": "9.9.9", "url": URL, "sha256": "0" * 64}) is False
    assert ran == []
    ok = launcher._install_update({"ver": "9.9.9", "url": URL, "sha256": hashlib.sha256(data).hexdigest()})
    assert ok is True and ran and "/VERYSILENT" in ran[0][0]

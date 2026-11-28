# -*- coding: utf-8 -*-
"""확장 ↔ 런처 연결(네이티브 메시징) — 실제 크롬·창·레지스트리는 건드리지 않는다."""
import io
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import native_host as nh  # noqa: E402

EXT = "chrome-extension://abcdefghijklmnopabcdefghijklmnop/"
KEYS = [
    {"id": "a1:nhis", "acct": "a1", "acct_label": "우리 사무소", "site": "nhis", "org": "건강보험", "short": "건보 EDI",
     "ready": True, "port": 9338, "profile": "p", "secret_id": "a1:nhis", "cfg": {"cert_cn": "CN=비밀아님"}},
    {"id": "a1:nps", "acct": "a1", "acct_label": "우리 사무소", "site": "nps", "org": "국민연금", "short": "연금 EDI",
     "ready": True, "port": 9337, "profile": "p", "secret_id": "a1:nps", "cfg": {"mng_no": "00000000000"}},
    {"id": "a1:hometax", "acct": "a1", "acct_label": "우리 사무소", "site": "hometax", "org": "국세청", "short": "홈택스",
     "ready": False, "port": 9403, "profile": "p", "secret_id": "a1:hometax", "cfg": {}},
    {"id": "a1:kosha", "acct": "a1", "acct_label": "우리 사무소", "site": "kosha", "org": "안전보건공단", "short": "산업안전포털",
     "ready": True, "port": 9407, "profile": "p", "secret_id": "a1:kosha", "cfg": {}},
]


class Deps:
    def __init__(self, alive=()):
        self.alive, self.spawned = set(alive), []

    def keys(self):
        return KEYS

    def port_alive(self, port):
        return port in self.alive

    def spawn(self, key_id):
        self.spawned.append(key_id)


def frame(obj):
    b = json.dumps(obj).encode("utf-8")
    return struct.pack("<I", len(b)) + b


def test_framing_roundtrip():
    out = io.BytesIO()
    nh.write_msg(out, {"ok": True, "말": "한글"})
    assert nh.read_msg(io.BytesIO(out.getvalue())) == {"ok": True, "말": "한글"}
    assert nh.read_msg(io.BytesIO(b"")) is None  # 크롬이 연결을 끊으면 끝


def test_rejects_unknown_origin():
    d = Deps()
    r = nh.handle({"type": "open", "key": "a1:nhis"}, "chrome-extension://zzzz/", d, allowed=[EXT])
    assert r["ok"] is False and d.spawned == []


def test_ping_lists_only_allowed_ready_sites_without_secrets():
    r = nh.handle({"type": "ping"}, EXT, Deps(alive=[9337]), allowed=[EXT])
    assert r["ok"] is True and r["version"]
    ids = [k["id"] for k in r["keys"]]
    assert ids == ["a1:nhis", "a1:nps"]  # 홈택스(준비 안 됨)·산업안전포털(허용 목록 밖)은 빠진다
    assert [k["open"] for k in r["keys"]] == [False, True]
    blob = json.dumps(r, ensure_ascii=False)
    for secret_ish in ("cert_cn", "CN=", "mng_no", "secret_id", "profile"):
        assert secret_ish not in blob


def test_open_spawns_login_once():
    d = Deps()
    r = nh.handle({"type": "open", "key": "a1:nhis"}, EXT, d, allowed=[EXT])
    assert r == {"ok": True, "state": "starting", "key": "a1:nhis"}
    assert d.spawned == ["a1:nhis"]


def test_open_when_window_alive_does_not_spawn():
    d = Deps(alive=[9338])
    r = nh.handle({"type": "open", "key": "a1:nhis"}, EXT, d, allowed=[EXT])
    assert r["state"] == "open" and d.spawned == []


def test_open_rejects_unknown_or_disallowed_keys():
    d = Deps()
    for key in ("a1:kosha", "a1:hometax", "zz:nhis", "", None, "a1:nhis --restart"):
        r = nh.handle({"type": "open", "key": key}, EXT, d, allowed=[EXT])
        assert r["ok"] is False, key
    assert d.spawned == []


def test_unknown_type_and_password_like_fields_never_echoed():
    d = Deps()
    r = nh.handle({"type": "password", "key": "a1:nhis"}, EXT, d, allowed=[EXT])
    assert r["ok"] is False and d.spawned == []


def test_spawn_command_breaks_away_and_has_no_secret(monkeypatch):
    calls = []
    monkeypatch.setattr(nh.subprocess, "Popen", lambda cmd, **kw: calls.append((cmd, kw)))
    monkeypatch.setattr(nh, "_run_log", lambda k: io.StringIO())
    nh.spawn_login("a1:nhis")
    cmd, kw = calls[0]
    assert cmd[-3:] == ["login", "a1:nhis", "--keep"]
    assert kw["creationflags"] & nh.DETACHED_PROCESS
    assert kw["stdin"] == nh.subprocess.DEVNULL  # 크롬 파이프를 물려주지 않는다


def test_install_manifest_and_registry(tmp_path):
    written = {}
    p = nh.install(str(tmp_path), [EXT], host_cmd=r"C:\x\run_host.cmd", reg_set=lambda k, v: written.update({k: v}))
    m = json.load(open(p, encoding="utf-8"))
    assert m["name"] == nh.HOST_NAME and m["type"] == "stdio"
    assert m["allowed_origins"] == [EXT] and m["path"] == r"C:\x\run_host.cmd"
    assert written == {nh.REG_KEY: p}


def test_install_rejects_wildcard_origin(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        nh.install(str(tmp_path), ["chrome-extension://*/"], host_cmd="x", reg_set=lambda k, v: None)

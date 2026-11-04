# -*- coding: utf-8 -*-
"""런처 설정 화면 — accounts.json 반영·비밀값 저장(가짜 DPAPI, 임시 폴더). 실제 설정·암호 파일은 건드리지 않는다."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import accounts  # noqa: E402
import list_certs  # noqa: E402
import secret_store  # noqa: E402

CERTS = [{"cn": "우리사무소()0001", "issuer": "yessign", "not_after": "2027-01-01", "dir": "x"},
         {"cn": "홍길동()0002", "issuer": "KICA", "not_after": "2027-02-01", "dir": "y"}]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts, "HOME", str(tmp_path))
    monkeypatch.setattr(accounts, "PATH", str(tmp_path / "accounts.json"))
    monkeypatch.setattr(secret_store, "HOME", str(tmp_path))
    monkeypatch.setattr(secret_store, "SECRETS", str(tmp_path / "secrets.json"))
    monkeypatch.setattr(list_certs, "SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.setattr(list_certs, "_OLD", str(tmp_path / "none.json"))
    monkeypatch.setattr(list_certs, "certs", lambda: CERTS)
    # 가짜 DPAPI — 평문이 파일에 그대로 남지 않는지만 본다
    monkeypatch.setattr(secret_store.win32crypt, "CryptProtectData", lambda b, *a: b"ENC" + b[::-1])
    monkeypatch.setattr(secret_store.win32crypt, "CryptUnprotectData", lambda b, *a: ("", b[3:][::-1]))
    import launcher
    launcher._reload()
    return tmp_path, launcher


def form(**kw):
    f = {"id": None, "label": "우리 사무소", "cert_cn": CERTS[0]["cn"],
         "sites": {"comwel": {"mode": "사무대행", "bizno": "1234567890", "account_hint": ""}, "nps": {"mng_no": "123-4567-8901"}, "nhis": {}},
         "secrets": {"cert_pw": "pw!1234", "rrn": "", "sitepw": "edi9"}}
    f.update(kw)
    return f


def test_first_account_saved_and_keys_appear(env):
    tmp, L = env
    aid = L._setup_save(form())
    acct = accounts.load()["accounts"][0]
    assert aid == "a1" and acct["label"] == "우리 사무소"
    assert acct["sites"]["comwel"]["bizno"] == "123-45-67890" and acct["sites"]["nps"]["mng_no"] == "12345678901"
    assert sorted(L.KEYS) == ["a1:comwel", "a1:nhis", "a1:nps"]
    ports = [s["port"] for s in acct["sites"].values()]
    assert len(set(ports)) == 3
    assert secret_store.get(CERTS[0]["cn"]) == "pw!1234" and secret_store.get("site:a1:nps") == "edi9"
    raw = (tmp / "secrets.json").read_text(encoding="utf-8") + (tmp / "accounts.json").read_text(encoding="utf-8")
    assert "pw!1234" not in raw and "edi9" not in raw


def test_view_shows_saved_flags_not_values(env):
    _, L = env
    L._setup_save(form())
    v = L._setup_view()
    a = v["accounts"][0]
    assert a["cert_pw_saved"] and a["sites"]["nps"]["sitepw_saved"]
    assert "pw!1234" not in json.dumps(v, ensure_ascii=False)


def test_edit_keeps_port_and_secret_id(env):
    _, L = env
    data = {"accounts": [{"id": "office", "label": "사무소", "cert_cn": CERTS[0]["cn"],
                          "sites": {"nps": {"mng_no": "11111111111", "port": 9337, "profile": "p-nps", "secret_id": "nps"}}}]}
    accounts.save(data)
    secret_store.put(CERTS[0]["cn"], "old")
    L._setup_save(form(id="office", label="사무소", sites={"nps": {"mng_no": "11111111111"}},
                       secrets={"cert_pw": "", "rrn": "", "sitepw": "newpw"}))
    s = accounts.load()["accounts"][0]["sites"]["nps"]
    assert s["port"] == 9337 and s["profile"] == "p-nps" and s["secret_id"] == "nps"
    assert secret_store.get("site:nps") == "newpw" and secret_store.get(CERTS[0]["cn"]) == "old"


def test_personal_mode_rrn(env):
    _, L = env
    L._setup_save(form(sites={"comwel": {"mode": "personal", "bizno": "", "account_hint": "홍길동"}},
                       secrets={"cert_pw": "x", "rrn": "900101-1234567", "sitepw": ""}))
    s = accounts.load()["accounts"][0]["sites"]["comwel"]
    assert s["login_tab"] == "personal" and s["account_hint"] == "홍길동"
    assert secret_store.get("rrn:a1:comwel") == "9001011234567"


@pytest.mark.parametrize("bad,msg", [
    (dict(label=" "), "계정 이름"),
    (dict(cert_cn="없는인증서"), "인증서"),
    (dict(sites={}), "사이트"),
    (dict(sites={"nps": {"mng_no": "123"}}), "11자리"),
    (dict(sites={"comwel": {"mode": "사무대행", "bizno": "12"}}), "10자리"),
    (dict(secrets={"cert_pw": "", "rrn": "", "sitepw": ""}), "인증서 비밀번호"),
    (dict(sites={"comwel": {"mode": "personal"}}, secrets={"cert_pw": "x", "rrn": "123", "sitepw": ""}), "13자리"),
])
def test_validation(env, bad, msg):
    _, L = env
    with pytest.raises(ValueError, match=msg):
        L._setup_save(form(**bad))
    assert not os.path.exists(accounts.PATH) or not accounts.load()["accounts"]


def test_second_account_and_delete(env):
    _, L = env
    L._setup_save(form())
    L._setup_save(form(label="대리인1", cert_cn=CERTS[1]["cn"], sites={"nhis": {}}))
    accts = accounts.load()["accounts"]
    assert [a["id"] for a in accts] == ["a1", "a2"]
    assert accts[1]["sites"]["nhis"]["port"] not in [s["port"] for s in accts[0]["sites"].values()]
    accounts.remove("a1")
    L._reload()
    assert sorted(L.KEYS) == ["a2:nhis"] and "a1:nps" not in L.STATE


def test_add_cert_dir(env):
    tmp, _ = env
    list_certs.add_dir("E:\\NPKI")
    list_certs.add_dir("E:\\NPKI")
    assert list_certs.extra_dirs() == ["E:\\NPKI"]

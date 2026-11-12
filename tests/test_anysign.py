# -*- coding: utf-8 -*-
"""건보 AnySign4PC 포트 점검 — 설정에서 포트를 읽고, 10531 이 아니면 경고한다(261112 실측 사고)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gov_login  # noqa: E402


def _conf(tmp_path, tls):
    p = tmp_path / "AnySign.conf"
    p.write_text(json.dumps({"no_tls_listen_port": str(tls - 1), "tls_listen_port": str(tls)}), encoding="utf-8")
    return str(p)


def test_port_read_from_conf(tmp_path, monkeypatch):
    monkeypatch.setattr(gov_login, "ANYSIGN_CONF", _conf(tmp_path, 30309))
    assert gov_login._anysign_port() == 30309


def test_port_missing_conf(monkeypatch):
    monkeypatch.setattr(gov_login, "ANYSIGN_CONF", r"C:\없는\경로\AnySign.conf")
    assert gov_login._anysign_port() is None


def test_warns_when_port_overwritten(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gov_login, "ANYSIGN_CONF", _conf(tmp_path, 30309))
    monkeypatch.setattr(gov_login, "ANYSIGN_EXE", __file__)  # 존재하는 파일
    monkeypatch.setattr(gov_login, "_anysign_listening", lambda port: True)
    gov_login._ensure_anysign()
    assert "10531" in capsys.readouterr().out


def test_silent_when_port_ok(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gov_login, "ANYSIGN_CONF", _conf(tmp_path, 10531))
    monkeypatch.setattr(gov_login, "ANYSIGN_EXE", __file__)
    monkeypatch.setattr(gov_login, "_anysign_listening", lambda port: True)
    gov_login._ensure_anysign()
    assert capsys.readouterr().out == ""


class _Page:
    def __init__(self, want):
        self.want = want

    def evaluate(self, js):
        return self.want


def test_version_mismatch_warns(monkeypatch, capsys):
    monkeypatch.setattr(gov_login, "_anysign_installed_version", lambda: "1.1.5.0")
    gov_login._check_anysign_version(_Page("1.1.5.1"))
    assert "1.1.5.0" in capsys.readouterr().out


def test_version_same_silent(monkeypatch, capsys):
    monkeypatch.setattr(gov_login, "_anysign_installed_version", lambda: "1.1.5.1")
    gov_login._check_anysign_version(_Page("1.1.5.1"))
    assert capsys.readouterr().out == ""

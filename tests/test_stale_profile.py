# -*- coding: utf-8 -*-
"""남은 크롬 정리(같은 프로필을 잡은 프로세스 찾기)와 실행 로그 보관 — 실제 프로세스는 건드리지 않는다."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gov_login  # noqa: E402
import launcher  # noqa: E402

PROFILE = r"C:\Users\me\AppData\Local\gov-cert-login-profile-nhis"


def test_finds_only_processes_on_that_profile():
    procs = [
        (11, r'"C:\chrome.exe" --remote-debugging-port=9338 --user-data-dir=C:\Users\me\AppData\Local\gov-cert-login-profile-nhis about:blank'),
        (12, r'"C:\chrome.exe" --type=renderer --user-data-dir="C:\Users\me\AppData\Local\gov-cert-login-profile-nhis" --x'),
        (13, r'"C:\chrome.exe" --user-data-dir=C:\Users\me\AppData\Local\gov-cert-login-profile-nhis1 about:blank'),  # 다른 계정
        (14, r'"C:\chrome.exe"'),                                                                              # 사용자 크롬
        (15, None),
    ]
    assert gov_login._profile_pids(PROFILE, procs) == [11, 12]


def test_profile_match_ignores_case_and_slashes():
    procs = [(21, '--user-data-dir=c:/users/me/appdata/local/GOV-CERT-LOGIN-PROFILE-NHIS --x')]
    assert gov_login._profile_pids(PROFILE, procs) == [21]


def test_run_log_is_timestamped_and_pruned(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "OUT", str(tmp_path))
    for i in range(12):
        (tmp_path / f"run_agent1_nhis_261104-1000{i:02d}.log").write_text("x")
    (tmp_path / "run_agent1_nps_261104-100000.log").write_text("x")
    p = launcher._new_run_log("agent1:nhis")
    open(p, "w").close()                          # _launch 가 이 경로로 연다
    assert os.path.basename(p).startswith("run_agent1_nhis_") and p.endswith(".log")
    left = sorted(f for f in os.listdir(tmp_path) if f.startswith("run_agent1_nhis_"))
    assert len(left) == launcher.KEEP_LOGS        # 새 파일 포함 최근 N개만
    assert os.path.basename(p) in left
    assert (tmp_path / "run_agent1_nps_261104-100000.log").exists()   # 다른 키는 그대로

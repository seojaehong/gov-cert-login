# -*- coding: utf-8 -*-
"""로그 보관 규칙과 버전 일치."""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logkeep  # noqa: E402
import version  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_installer_has_no_own_version():
    """버전은 version.py 한 곳 — installer.iss 에 버전 숫자를 다시 적지 않는다(빌드 때 /DAppVer 로 받는다)."""
    iss = open(os.path.join(ROOT, "build", "installer.iss"), encoding="utf-8").read()
    assert not re.search(r'#define\s+AppVer\s+"\d', iss)
    assert "#error" in iss


def test_is_newer():
    assert version.is_newer("v0.1.10", "0.1.9")
    assert version.is_newer("0.2.0", "0.1.9")
    assert not version.is_newer("v0.1.2", "0.1.2")
    assert not version.is_newer("v0.1.1", "0.1.2")
    assert not version.is_newer("nightly", "0.1.2")


def test_fail_screens_keep_fewer(tmp_path):
    for i in range(5):
        (tmp_path / f"fail_agent1_nhis_261104-10000{i}.png").write_text("x")
    p = logkeep.stamped(str(tmp_path), "fail", "agent1:nhis", "png")
    open(p, "w").close()
    left = [f for f in os.listdir(tmp_path) if f.startswith("fail_agent1_nhis_")]
    assert len(left) == logkeep.KEEP["fail"]


def test_purge_old_only_old_log_files(tmp_path):
    old, new, other = tmp_path / "run_a_1.log", tmp_path / "run_b_1.log", tmp_path / "sessions.json"
    for f in (old, new, other):
        f.write_text("x")
    past = time.time() - 40 * 86400
    os.utime(old, (past, past))
    os.utime(other, (past, past))
    assert logkeep.purge_old(str(tmp_path)) == 1
    assert not old.exists() and new.exists() and other.exists()   # json 등 기록 아닌 파일은 안 지운다

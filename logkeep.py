# -*- coding: utf-8 -*-
"""실행 기록 보관 규칙 — %LOCALAPPDATA%\\gov-cert-login\\logs

- 실행마다 시각을 붙인 새 파일을 만든다. 덮어쓰면 실패한 판의 원인이 다음 실행에 지워진다(261104).
- 같은 종류·같은 키는 최근 N개만 남긴다 — 실행 로그 10개, 실패 화면 3개(화면에 업무 내용이 담길 수 있어 적게).
- 런처를 켤 때 30일 지난 기록은 지운다.
- 로그에는 비밀번호·주민번호를 쓰지 않는다(쓰는 쪽 책임 — gov_login 은 결과·알림 문구만 남긴다).
"""
import os
import time

KEEP = {"run": 10, "fail": 3}
MAX_DAYS = 30


def stamped(folder, kind, key, ext):
    """<kind>_<key>_<yymmdd-HHMMSS>.<ext> 경로를 돌려주고, 같은 kind·key 의 옛 파일은 KEEP-1 개만 남긴다."""
    os.makedirs(folder, exist_ok=True)
    stem = f"{kind}_{key.replace(':', '_')}_"
    old = sorted(f for f in os.listdir(folder)
                 if f.startswith(stem) and f.endswith("." + ext) and f[len(stem):len(stem) + 1].isdigit())
    keep = KEEP.get(kind, 10)
    for f in old[:max(0, len(old) - (keep - 1))]:
        try:
            os.remove(os.path.join(folder, f))
        except OSError:
            pass
    return os.path.join(folder, stem + time.strftime("%y%m%d-%H%M%S") + "." + ext)


def purge_old(folder, days=MAX_DAYS, now=None):
    """days 일 지난 기록 파일(.log/.png/.txt)을 지운다. 지운 개수."""
    if not os.path.isdir(folder):
        return 0
    cut = (now or time.time()) - days * 86400
    n = 0
    for f in os.listdir(folder):
        p = os.path.join(folder, f)
        if f.rsplit(".", 1)[-1] in ("log", "png", "txt") and os.path.isfile(p) and os.path.getmtime(p) < cut:
            try:
                os.remove(p)
                n += 1
            except OSError:
                pass
    return n

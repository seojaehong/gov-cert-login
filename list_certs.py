"""PC(하드디스크)의 공동인증서 목록 — 이름·발급자·만료일만 (비밀키는 읽지 않는다)."""
import glob
import os
import sys

from cryptography import x509

import json

DEFAULT = os.path.join(os.environ["USERPROFILE"], "AppData", "LocalLow", "NPKI")
# 추가 NPKI 폴더(USB·OneDrive 사본 등) — 런처 설정 화면이 settings.json 에 적는다. 예전 config.json 도 읽는다
SETTINGS = os.path.join(os.environ["LOCALAPPDATA"], "gov-cert-login", "settings.json")
_OLD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def extra_dirs():
    out = []
    for p in (_OLD, SETTINGS):
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                out += [d for d in json.load(f).get("npki_dirs", []) if d not in out]
    return out


def add_dir(path):
    d = {}
    if os.path.exists(SETTINGS):
        with open(SETTINGS, encoding="utf-8") as f:
            d = json.load(f)
    if path not in d.setdefault("npki_dirs", []):
        d["npki_dirs"].append(path)
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def certs():
    out = []
    for root in [DEFAULT, *extra_dirs()]:
        # NPKI 폴더를 골랐든 그 안의 기관·USER 폴더를 골랐든 찾는다
        pats = ["*/USER/*/signCert.der", "USER/*/signCert.der", "*/signCert.der", "signCert.der"]
        for p in sorted({q for pat in pats for q in glob.glob(os.path.join(root, *pat.split("/")))}):
            c = x509.load_der_x509_certificate(open(p, "rb").read())
            cn = c.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
            parts = os.path.normpath(p).split(os.sep)
            issuer = parts[parts.index("USER") - 1] if "USER" in parts[1:] else parts[-2]
            if any(o["dir"] == os.path.dirname(p) for o in out):
                continue
            out.append({"cn": cn, "issuer": issuer, "not_after": c.not_valid_after_utc.date().isoformat(),
                        "dir": os.path.dirname(p)})
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # 런처(pythonw)가 import 할 때는 stdout 이 없다
    for i, c in enumerate(certs()):
        print(i, c["cn"], c["issuer"], c["not_after"])

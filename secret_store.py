"""비밀값 저장소(DPAPI) — 이 PC·이 윈도우 계정에서만 풀린다.

저장 이름: 인증서 비밀번호 = 인증서 CN · 주민번호 = "rrn:<secret_id>" · 연금 사업장 비밀번호 = "site:<secret_id>".
런처 설정 화면과 명령줄(gov_login.py store …)이 같은 함수를 쓴다. 값은 화면·로그·파일 어디에도 평문으로 남기지 않는다.
"""
import base64
import json
import os

import win32crypt

HOME = os.path.join(os.environ["LOCALAPPDATA"], "gov-cert-login")
SECRETS = os.path.join(HOME, "secrets.json")
ENTROPY = b"gov-cert-login/v1"
DESC = {"rrn:": "gov-cert-login-rrn", "site:": "gov-cert-login-site"}


def _load():
    if not os.path.exists(SECRETS):
        return {}
    with open(SECRETS, encoding="utf-8") as f:
        return json.load(f)


def put(name, value):
    desc = next((v for p, v in DESC.items() if name.startswith(p)), "gov-cert-login")
    blob = win32crypt.CryptProtectData(value.encode("utf-8"), desc, ENTROPY, None, None, 0)
    os.makedirs(HOME, exist_ok=True)
    d = _load()
    d[name] = base64.b64encode(blob).decode()
    tmp = SECRETS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, SECRETS)


def get(name):
    d = _load()
    if name not in d:
        return None
    return win32crypt.CryptUnprotectData(base64.b64decode(d[name]), ENTROPY, None, None, 0)[1].decode("utf-8")


def has(name):
    return name in _load()

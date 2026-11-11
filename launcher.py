"""공단 로그인 — 키보드형 데스크톱 프로그램(pywebview 창 + launcher.html).

키 = 계정 × 사이트(accounts.json). 키를 누르면 그 키 전용 크롬 프로필·포트로 gov_login.py 를 띄운다.
키마다 프로필이 따로라 서로 로그인을 끊지 않는다. 여러 키를 한꺼번에 누르면(키 조합·「모두 열기」) 차례로 연다.
상태 = 포트 생존 + login_state.py(화면의 「로그아웃」 등 글자). 6초마다 갱신하고 sessions.json 에 기록한다.
실행: pythonw launcher.py   (이미 떠 있으면 새로 띄우지 않는다)
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

import webview

import accounts
import list_certs
import logkeep
import secret_store
from version import __version__

FROZEN = getattr(sys, "frozen", False)  # 설치본(PyInstaller exe)
HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))  # launcher.html 등 동봉 파일
PY = os.path.join(os.path.dirname(sys.executable), "python.exe")  # pythonw 로 떠도 자식은 python.exe
NOWIN = subprocess.CREATE_NO_WINDOW
OUT = accounts.LOGS
SCRIPTS = ("gov_login", "login_state")  # 설치본에서는 exe 가 「--run 이름」으로 이것들을 대신 실행한다


def _cmd(script, *args):
    """보조 스크립트 실행 명령 — 개발본은 python 파일, 설치본은 자기 exe 에 --run."""
    if FROZEN:
        return [sys.executable, "--run", script, *args]
    return [PY, os.path.join(HERE, script + ".py"), *args]

KEYS, STATE = {}, {}
PROCS, LOG = {}, []
LOCK = threading.RLock()  # _poll 이 잡은 채 _set→_log 가 다시 잡는다


def _reload():
    """accounts.json 을 다시 읽어 키를 맞춘다(설정 저장 뒤). 남은 키의 상태는 그대로 둔다."""
    with LOCK:
        new = {k["id"]: k for k in accounts.keys()}
        KEYS.clear()
        KEYS.update(new)
        for k in list(STATE):
            if k not in KEYS:
                del STATE[k]
        for k in KEYS:
            STATE.setdefault(k, {"state": "off", "note": "꺼짐", "since": None})


_reload()


def _now():
    return time.strftime("%H:%M")


def _name(k):
    return f"{KEYS[k]['org']} {KEYS[k]['acct_label']}"


def _log(msg):
    with LOCK:
        LOG.insert(0, {"t": _now(), "msg": msg})
        del LOG[30:]


def _alive(port):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1).read()
        return True
    except Exception:  # noqa: BLE001
        return False


def _set(k, state, note):
    old = STATE[k]["state"]
    if old != state:
        if state == "on":
            _log(f"{_name(k)} 로그인됨")
        elif old == "on":
            _log(f"{_name(k)} 로그인이 풀렸습니다")
    STATE[k] = {"state": state, "note": note, "since": STATE[k]["since"] if old == state else _now()}


def _write_sessions():
    data = {k: {"port": v["port"], "site": v["site"], "account": v["acct"], "state": STATE[k]["state"]} for k, v in KEYS.items()}
    tmp = accounts.SESSIONS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"updated": time.strftime("%Y-%m-%dT%H:%M:%S"), "keys": data}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, accounts.SESSIONS)


def _poll():
    while True:
        with LOCK:
            ready = [k for k in KEYS if KEYS[k]["ready"]]
            ports_of = {k: KEYS[k]["port"] for k in ready}
        alive = {k: _alive(ports_of[k]) for k in ready}
        logged = {}
        ports = [str(ports_of[k]) for k in ready if alive[k]]
        if ports:
            try:
                out = subprocess.run(_cmd("login_state", *ports), capture_output=True, text=True,
                                     encoding="utf-8", timeout=40, creationflags=NOWIN).stdout
                for line in out.splitlines():
                    p, _, rest = line.partition(" ")
                    logged[p] = "로그인됨" in rest
            except Exception:  # noqa: BLE001
                pass
        with LOCK:
            for k in ready:
                if k not in KEYS:  # 그 사이 설정에서 지운 키
                    continue
                running = k in PROCS and PROCS[k].poll() is None
                if not alive[k]:
                    _set(k, "busy", "창 여는 중") if running else _set(k, "off", "꺼짐")
                elif logged.get(str(ports_of[k])):
                    _set(k, "on", "로그인됨")
                else:
                    _set(k, "busy", "암호 입력 대기" if running else "창 열림 · 로그인 전")
            try:
                _write_sessions()
            except OSError:
                pass
        time.sleep(6)


def _setup_view():
    """설정 화면에 보낼 값 — 비밀값은 「저장됨」 여부만."""
    cs = list_certs.certs()
    accts = []
    for a in accounts.load()["accounts"]:
        sites = {}
        for sid, sc in a.get("sites", {}).items():
            sec = sc.get("secret_id", f"{a['id']}:{sid}")
            v = {}
            if sid == "comwel":
                v = {"mode": "personal" if sc.get("login_tab") == "personal" else sc.get("kind", "사무대행"),
                     "bizno": sc.get("bizno", ""), "account_hint": sc.get("account_hint", ""),
                     "rrn_saved": secret_store.has("rrn:" + sec)}
            elif sid == "nps":
                v = {"mng_no": sc.get("mng_no", ""), "sitepw_saved": secret_store.has("site:" + sec)}
            sites[sid] = v
        accts.append({"id": a["id"], "label": a.get("label", a["id"]), "cert_cn": a.get("cert_cn"),
                      "cert_pw_saved": bool(a.get("cert_cn")) and secret_store.has(a["cert_cn"]), "sites": sites})
    return {"certs": [{"cn": c["cn"], "issuer": c["issuer"], "not_after": c["not_after"], "pw_saved": secret_store.has(c["cn"])}
                      for c in cs],
            "dirs": list_certs.extra_dirs(), "accounts": accts,
            "sites": [{"id": s[0], "org": s[1], "short": s[2], "ready": s[4]} for s in accounts.SITES]}


def _setup_save(form):
    """설정 저장 — 계정 정보는 accounts.json, 비밀값은 DPAPI(secret_store). 비밀값은 어디에도 출력하지 않는다."""
    secrets = form.pop("secrets", {}) or {}
    cert_cns = [c["cn"] for c in list_certs.certs()]
    pw = secrets.get("cert_pw") or ""
    if not pw and not secret_store.has(form.get("cert_cn") or ""):
        raise ValueError("인증서 비밀번호를 입력해 주세요.")
    rrn = "".join(ch for ch in str(secrets.get("rrn") or "") if ch.isdigit())
    if secrets.get("rrn") and len(rrn) != 13:
        raise ValueError("주민등록번호는 13자리입니다.")
    aid = accounts.upsert(form, cert_cns)
    if pw:
        secret_store.put(form["cert_cn"], pw)
    sec = {k["site"]: k["secret_id"] for k in accounts.keys() if k["acct"] == aid}
    if rrn and "comwel" in sec:
        secret_store.put("rrn:" + sec["comwel"], rrn)
    if secrets.get("sitepw") and "nps" in sec:
        secret_store.put("site:" + sec["nps"], secrets["sitepw"])
    _reload()
    _log(f"{form['label']} 계정 설정을 저장했습니다")
    return aid


KEEP_LOGS = logkeep.KEEP["run"]  # 키마다 실행 로그를 최근 몇 개 남기나


def _new_run_log(k):
    """실행마다 시각을 붙인 새 로그 파일 경로(보관 규칙은 logkeep.py)."""
    return logkeep.stamped(OUT, "run", k, "log")


def _launch(k):
    v = KEYS[k]
    if not v["ready"]:
        return f"{v['org']} 로그인은 준비 중입니다."
    if _alive(v["port"]):
        return "이미 창이 열려 있습니다."
    log = open(_new_run_log(k), "w", encoding="utf-8")
    PROCS[k] = subprocess.Popen(_cmd("gov_login", "login", k, "--keep"), cwd=OUT,
                                stdout=log, stderr=subprocess.STDOUT, creationflags=NOWIN)
    with LOCK:
        _set(k, "busy", "창 여는 중")
    _log(f"{_name(k)} 창을 엽니다")
    return "창을 엽니다."


class Api:
    def state(self):
        with LOCK:
            cols = [s for s in accounts.SITES if any(v["site"] == s[0] for v in KEYS.values())]
            rows = []
            for a in accounts.load()["accounts"]:
                rows.append({"id": a["id"], "label": a.get("label", a["id"]),
                             "cells": [f"{a['id']}:{s[0]}" if f"{a['id']}:{s[0]}" in KEYS else None for s in cols]})
            keys = {k: dict(STATE[k], org=v["org"], short=v["short"], emo=v["emo"], acct=v["acct_label"], ready=v["ready"])
                    for k, v in KEYS.items()}
            return {"cols": [{"site": s[0], "org": s[1]} for s in cols], "rows": rows, "keys": keys, "log": LOG[:12],
                    "needs_setup": not rows}

    def launch(self, k):
        return _launch(k) if k in KEYS else "알 수 없는 키입니다."

    def launch_many(self, ks):
        """키 조합·「모두 열기」 — 보안프로그램끼리 부딪치지 않게 3초 간격으로 차례로 연다."""
        todo = [k for k in ks if k in KEYS and KEYS[k]["ready"] and not _alive(KEYS[k]["port"])]

        def run():
            for i, k in enumerate(todo):
                if i:
                    time.sleep(3)
                _launch(k)
        threading.Thread(target=run, daemon=True).start()
        return f"{len(todo)}개 창을 차례로 엽니다." if todo else "열 창이 없습니다(이미 열렸거나 준비 중)."

    # ── 설정 화면 ──
    def setup_get(self):
        return _setup_view()

    def setup_save(self, form):
        try:
            _setup_save(dict(form))
            return {"ok": True, "msg": "저장했습니다. 키를 눌러 로그인해 보세요.", "view": _setup_view()}
        except ValueError as e:
            return {"ok": False, "msg": str(e)}

    def setup_delete(self, acct_id):
        accounts.remove(acct_id)
        _reload()
        _log("계정 하나를 지웠습니다")
        return _setup_view()

    def add_cert_dir(self):
        """인증서가 USB·다른 폴더에 있을 때 — 폴더를 골라 settings.json 에 기억한다."""
        r = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
        if r:
            list_certs.add_dir(r[0] if isinstance(r, (list, tuple)) else r)
        return _setup_view()

    def minimize(self):
        webview.windows[0].minimize()

    def close(self):
        webview.windows[0].destroy()


_MUTEX = None  # 프로세스가 살아 있는 동안 쥐고 있는다(종료되면 OS 가 자동으로 푼다)


def _single_instance():
    """두 번째 실행 방지 — 포트가 아니라 이름 있는 뮤텍스로 판정한다.

    예전에는 127.0.0.1:8765 를 bind 해서 막았는데, 다른 개발 서버가 그 포트를 쓰면
    런처가 아무 말 없이 꺼졌다(261111). 이미 떠 있으면 그 창을 앞으로 가져오고,
    창을 못 찾으면 안내창을 띄운다."""
    global _MUTEX
    import ctypes
    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    k32.CreateMutexW.restype = ctypes.c_void_p
    _MUTEX = k32.CreateMutexW(None, False, "Local\\gov-cert-login-launcher")
    if k32.GetLastError() != 183:  # ERROR_ALREADY_EXISTS 가 아니면 첫 실행
        return True
    found = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def _each(hwnd, _):
        n = u32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value.startswith("공단 로그인"):
                found.append(hwnd)
                return False
        return True

    u32.EnumWindows(proc(_each), 0)
    if found:
        u32.ShowWindow(ctypes.c_void_p(found[0]), 9)  # SW_RESTORE
        u32.SetForegroundWindow(ctypes.c_void_p(found[0]))
    else:
        u32.MessageBoxW(None, "공단 로그인이 이미 실행 중인데 창을 찾지 못했습니다.\n"
                        "작업 관리자에서 남은 「공단 로그인」(pythonw) 을 끝낸 뒤 다시 실행해 주세요.",
                        "공단 로그인", 0x40)
    return False


def _run_script(name, args):
    """설치본 전용 — exe --run gov_login login … 처럼 동봉 스크립트를 그 자리에서 실행한다."""
    import runpy
    if name not in SCRIPTS:
        sys.exit(f"알 수 없는 실행 이름: {name}")
    sys.argv = [name + ".py", *args]
    runpy.run_module(name, run_name="__main__")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--run":
        _run_script(sys.argv[2], sys.argv[3:])
        sys.exit(0)
    if not _single_instance():
        sys.exit(0)
    logkeep.purge_old(OUT)  # 30일 지난 실행 기록 정리
    _log(f"공단 로그인 {__version__} 시작")
    threading.Thread(target=_poll, daemon=True).start()
    webview.create_window(f"공단 로그인 {__version__}",os.path.join(HERE, "launcher.html"), js_api=Api(),
                          width=1120, height=700, min_size=(760, 560), frameless=True, easy_drag=False,
                          background_color="#E9EBEF")
    webview.start()

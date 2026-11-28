# -*- coding: utf-8 -*-
"""확장 ↔ 런처 연결(크롬 네이티브 메시징 호스트).

확장이 「로그인 창 열기」를 누르면 크롬이 이 프로그램을 띄우고 표준 입출력으로 JSON 한 통을 주고받는다.
이 프로그램은 런처 키(accounts.json)를 고르고 gov_login 을 그 키 전용 창으로 띄울 뿐이다.
  · 암호·인증서 정보는 확장으로 보내지 않는다(암호는 gov_login 이 이 PC 의 DPAPI 저장소에서 직접 꺼낸다)
  · 확장이 보낸 값은 키 id 하나뿐이고, accounts.json 에 있는 키와 글자까지 같아야 한다
  · 부를 수 있는 확장은 설치 때 적은 확장 id(allowed_origins)뿐이다 — 크롬이 먼저 막고, 여기서 한 번 더 본다

설치·해제: python native_host.py install <확장id…> / uninstall   (설치본은 런처 설치 때 함께 등록한다)
"""
import json
import os
import struct
import subprocess
import sys

import accounts
import logkeep
from version import __version__

HOST_NAME = "com.govcertlogin.launcher"
REG_KEY = r"Software\Google\Chrome\NativeMessagingHosts" + "\\" + HOST_NAME
ALLOWED_SITES = ("comwel", "nps", "nhis")  # 확장에서 열 수 있는 사이트 — 4대보험 3곳(261128)
NATIVE_DIR = os.path.join(accounts.HOME, "native")
MANIFEST = os.path.join(NATIVE_DIR, HOST_NAME + ".json")
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000  # 크롬은 호스트를 작업 개체에 넣고, 연결이 끊기면 함께 끝낸다 → 로그인 창은 빠져나와야 산다
MAX_MSG = 64 * 1024
FROZEN = getattr(sys, "frozen", False)
HERE = os.path.dirname(os.path.abspath(__file__))


# ── 크롬 메시지 틀: 4바이트 길이(리틀엔디언) + UTF-8 JSON ──

def read_msg(stream):
    head = stream.read(4)
    if len(head) < 4:
        return None
    n = struct.unpack("<I", head)[0]
    if n > MAX_MSG:
        raise ValueError("메시지가 너무 큽니다")
    return json.loads(stream.read(n).decode("utf-8"))


def write_msg(stream, obj):
    b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    stream.write(struct.pack("<I", len(b)) + b)
    stream.flush()


# ── 판정(순수 함수) ──

def _visible(keys):
    return [k for k in keys if k["ready"] and k["site"] in ALLOWED_SITES]


def handle(msg, origin, deps, allowed):
    """msg 하나 → 응답 하나. deps = keys()·port_alive(port)·spawn(key_id) 를 가진 객체."""
    if origin not in allowed:
        return {"ok": False, "error": "허용되지 않은 확장입니다"}
    t = (msg or {}).get("type")
    keys = _visible(deps.keys())
    if t == "ping":
        return {"ok": True, "version": __version__,
                "keys": [{"id": k["id"], "site": k["site"], "org": k["org"], "label": k["acct_label"],
                          "open": bool(deps.port_alive(k["port"]))} for k in keys]}
    if t == "open":
        kid = msg.get("key")
        k = next((x for x in keys if x["id"] == kid), None)
        if k is None:
            return {"ok": False, "error": "열 수 없는 키입니다"}
        if deps.port_alive(k["port"]):
            return {"ok": True, "state": "open", "key": kid}
        deps.spawn(kid)
        return {"ok": True, "state": "starting", "key": kid}
    return {"ok": False, "error": "알 수 없는 요청입니다"}


# ── 실제 동작 ──

def _gov_login_cmd(*args):
    if FROZEN:  # 설치본 exe 가 「--run gov_login」으로 동봉 스크립트를 돌린다(launcher._run_script)
        return [sys.executable, "--run", "gov_login", *args]
    py = os.path.join(os.path.dirname(sys.executable), "python.exe")
    return [py, os.path.join(HERE, "gov_login.py"), *args]


def _run_log(key_id):
    return open(logkeep.stamped(accounts.LOGS, "run", key_id, "log"), "w", encoding="utf-8")


def spawn_login(key_id):
    log = _run_log(key_id)
    base = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    kw = dict(cwd=accounts.LOGS, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, close_fds=True)
    try:
        subprocess.Popen(_gov_login_cmd("login", key_id, "--keep"), creationflags=base | CREATE_BREAKAWAY_FROM_JOB, **kw)
    except OSError:  # 작업 개체가 빠져나가기를 막으면 그냥 띄운다
        subprocess.Popen(_gov_login_cmd("login", key_id, "--keep"), creationflags=base, **kw)


def _port_alive(port):
    import urllib.request
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2).read()
        return True
    except Exception:  # noqa: BLE001
        return False


class RealDeps:
    keys = staticmethod(accounts.keys)
    port_alive = staticmethod(_port_alive)
    spawn = staticmethod(spawn_login)


def _allowed_from_manifest():
    try:
        with open(MANIFEST, encoding="utf-8") as f:
            return list(json.load(f).get("allowed_origins") or [])
    except Exception:  # noqa: BLE001
        return []


def serve(argv, stdin, stdout):
    origin = argv[1] if len(argv) > 1 else ""
    os.makedirs(accounts.LOGS, exist_ok=True)
    msg = read_msg(stdin)
    if msg is None:
        return
    try:
        resp = handle(msg, origin, RealDeps, _allowed_from_manifest())
    except Exception as e:  # noqa: BLE001
        resp = {"ok": False, "error": type(e).__name__}
    write_msg(stdout, resp)


# ── 설치·해제 ──

def _reg_set(key, value):
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as h:
        winreg.SetValueEx(h, "", 0, winreg.REG_SZ, value)


def _reg_del(key):
    import winreg
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
    except FileNotFoundError:
        pass


def _write_host_cmd(folder):
    """크롬은 윈도우에서 exe·cmd 만 띄운다 → 개발본은 python 을 부르는 cmd 를 만든다."""
    path = os.path.join(folder, "run_host.cmd")
    if FROZEN:
        line = f'@"{sys.executable}" --run native_host %*\r\n'
    else:
        py = os.path.join(os.path.dirname(sys.executable), "python.exe")
        line = f'@"{py}" "{os.path.join(HERE, "native_host.py")}" %*\r\n'
    # cmd.exe 는 배치 파일을 콘솔(OEM) 코드 페이지로 읽는다 — 한글 사용자 이름(경로)도 그 코드 페이지로 쓴다.
    # 그 코드 페이지에 없는 글자면 짧은 경로(8.3)로 바꿔 쓴다. 둘 다 안 되면 등록을 멈추고 알린다(조용히 빠지지 않게).
    text = "@echo off\r\n" + line
    try:
        data = text.encode("oem" if sys.platform == "win32" else "utf-8")
    except UnicodeEncodeError:
        data = _short_paths(text).encode("ascii")
    with open(path, "wb") as f:
        f.write(data)
    return path


def _short_paths(text):
    import ctypes
    out = text
    for p in {sys.executable, os.path.join(HERE, "native_host.py")}:
        buf = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.kernel32.GetShortPathNameW(p, buf, len(buf)):
            out = out.replace(p, buf.value)
    return out


def install(folder, origins, host_cmd=None, reg_set=_reg_set):
    origins = list(origins)
    for o in origins:
        if not (o.startswith("chrome-extension://") and o.endswith("/") and "*" not in o and len(o) > 21):
            raise ValueError(f"확장 주소 형식이 아닙니다: {o}")
    os.makedirs(folder, exist_ok=True)
    host_cmd = host_cmd or _write_host_cmd(folder)
    path = os.path.join(folder, HOST_NAME + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"name": HOST_NAME, "description": "공단 로그인 — 확장에서 로그인 창 열기",
                   "path": host_cmd, "type": "stdio", "allowed_origins": origins}, f, ensure_ascii=False, indent=1)
    reg_set(REG_KEY, path)
    return path


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "install":
        ids = sys.argv[2:]
        if not ids:
            sys.exit("확장 id 를 적어 주세요: python native_host.py install <확장id>")
        print(install(NATIVE_DIR, [f"chrome-extension://{i}/" for i in ids]))
    elif len(sys.argv) >= 2 and sys.argv[1] == "uninstall":
        _reg_del(REG_KEY)
        print("등록을 지웠습니다")
    else:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        serve(sys.argv, sys.stdin.buffer, sys.stdout.buffer)

"""계정·키 설정 — %LOCALAPPDATA%/gov-cert-login/accounts.json (사무소마다 다르고 저장소에 올리지 않는다).

키 = 계정 × 사이트. 키 id 는 "계정id:사이트" (예 "agent1:nps").
대리인 계정이 하나인 사무소는 키 3개(토탈·연금·건보), 둘이면 6개가 된다.

accounts.json 형식:
{
  "accounts": [
    {"id": "main", "label": "우리 사무소", "cert_cn": "인증서 CN",
     "sites": {
        "comwel": {"kind": "사무대행", "bizno": "000-00-00000", "account_hint": "계정명 일부"},
        "nps":    {"mng_no": "00000000000"},
        "nhis":   {},
        "hometax": {}
     }}
  ]
}
사이트 설정에 port·profile·secret_id 를 주면 그 값을 쓴다(기존 창·저장 암호 이어 쓰기). 없으면 자동으로 정한다.
"""
import json
import os

HOME = os.path.join(os.environ["LOCALAPPDATA"], "gov-cert-login")
PATH = os.path.join(HOME, "accounts.json")
LOGS = os.path.join(HOME, "logs")  # 실행 기록·실패 화면 — 설치 폴더는 쓰기 금지일 수 있어 여기로
SESSIONS = os.path.join(HOME, "sessions.json")  # 런처가 기록 — 작업 엔진(insconn 등)이 어느 포트에 붙을지 여기서 읽는다

# 사이트 표: (id, 기관, 키에 적을 이름, 이모티콘, 로그인 구현 여부)
SITES = [
    ("comwel", "근로복지공단", "토탈서비스", "💼", True),
    ("nps", "국민연금", "연금 EDI", "🏦", True),
    ("nhis", "건강보험", "건보 EDI", "🏥", True),
    ("hometax", "국세청", "홈택스", "🧾", False),
    ("hsfms", "효성에프엠에스", "효성CMS", "💳", True),
    ("work24", "고용노동부", "고용24", "👶", True),
    ("labor", "노동포털", "민원", "📋", True),  # 취업규칙 신고·노사협의회 규정 제출(261122)
    ("kosha", "안전보건공단", "산업안전포털", "🦺", True),  # 사업자 공동인증서(KSign 창) — KRAS 위험성평가(261124)
]
SITE = {s[0]: s for s in SITES}


def load():
    if not os.path.exists(PATH):
        return {"accounts": []}
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)


def keys():
    """키 목록(계정 순서 → 사이트 표 순서)."""
    out = []
    for ai, a in enumerate(load()["accounts"]):
        for si, (sid, org, short, emo, ready) in enumerate(SITES):
            if sid not in a.get("sites", {}):
                continue
            sc = dict(a["sites"][sid])
            kid = f"{a['id']}:{sid}"
            sc.setdefault("cert_cn", a.get("cert_cn"))
            out.append({
                "id": kid, "acct": a["id"], "acct_label": a.get("label", a["id"]), "site": sid,
                "org": org, "short": short, "emo": emo, "ready": ready,
                "port": int(sc.pop("port", 9400 + ai * 10 + si)),
                "profile": os.path.join(os.environ["LOCALAPPDATA"],
                                        sc.pop("profile", f"gov-cert-login-profile-{a['id']}-{sid}")),
                "secret_id": sc.pop("secret_id", kid),
                "cfg": sc,
            })
    return out


def save(data):
    os.makedirs(HOME, exist_ok=True)
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, PATH)


COMWEL_KINDS = ("사무대행", "사업장", "의료기관")
WORK24_KINDS = ("사무대행기관", "일반 사업자")  # 고용24 기업회원 유형 중 로그인 구현된 것(대리인·훈련기관은 아직)


def _digits(s):
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def upsert(form, cert_cns):
    """설정 화면 입력(비밀값 제외) → accounts.json 에 반영하고 계정 id 를 돌려준다.
    form = {"id"(있으면 수정), "label", "cert_cn", "sites": {"comwel": {"mode", "bizno", "account_hint"}, "nps": {"mng_no"}, "nhis": {}, "hometax": {}}}
    기존 사이트 설정의 port·profile·secret_id 등은 그대로 둔다(열린 창·저장 암호를 이어 쓴다). 잘못된 값이면 ValueError."""
    label = str(form.get("label") or "").strip()
    if not label:
        raise ValueError("계정 이름을 적어 주세요.")
    if form.get("cert_cn") not in cert_cns:
        raise ValueError("인증서를 골라 주세요.")
    sites_in = form.get("sites") or {}
    if not sites_in:
        raise ValueError("쓸 사이트를 하나 이상 골라 주세요.")
    data = load()
    acct = next((a for a in data["accounts"] if a["id"] == form.get("id")), None)
    if acct is None:
        n = 1
        while any(a["id"] == f"a{n}" for a in data["accounts"]):
            n += 1
        acct = {"id": f"a{n}", "sites": {}}
        data["accounts"].append(acct)
    acct["label"], acct["cert_cn"] = label, form["cert_cn"]
    old = acct.get("sites", {})
    new = {}
    for sid in (s[0] for s in SITES):
        if sid not in sites_in:
            continue
        f, sc = sites_in[sid] or {}, dict(old.get(sid, {}))
        if sid == "comwel":
            mode = f.get("mode") or "사무대행"
            if mode == "personal":
                sc["login_tab"] = "personal"
            elif mode in COMWEL_KINDS:
                sc.pop("login_tab", None)
                sc["kind"] = mode
                b = _digits(f.get("bizno"))
                if len(b) != 10:
                    raise ValueError("토탈서비스 사업자등록번호는 10자리입니다.")
                sc["bizno"] = f"{b[:3]}-{b[3:5]}-{b[5:]}"
            else:
                raise ValueError("토탈서비스 로그인 방식을 골라 주세요.")
            hint = str(f.get("account_hint") or "").strip()
            if hint:
                sc["account_hint"] = hint
            else:
                sc.pop("account_hint", None)
        elif sid in ("hsfms", "labor", "kosha"):
            b = _digits(f.get("bizno"))
            if len(b) != 10:
                raise ValueError(f"{SITE[sid][1]} 사업자등록번호는 10자리입니다.")
            sc["bizno"] = f"{b[:3]}-{b[3:5]}-{b[5:]}"
        elif sid == "work24":
            kind = f.get("kind") or "사무대행기관"
            if kind not in WORK24_KINDS:
                raise ValueError("고용24 기업회원 유형을 골라 주세요.")
            sc["kind"] = kind
            if kind == "사무대행기관":
                i, b = _digits(f.get("isoa_no")), _digits(f.get("bplc_no"))
                if len(i) != 10:
                    raise ValueError("고용24 사무대행기관번호는 10자리입니다.")
                if b and len(b) != 11:
                    raise ValueError("고용24 대상 사업장관리번호는 11자리입니다.")
                sc["isoa_no"] = i
                if b:
                    sc["bplc_no"] = b
                else:
                    sc.pop("bplc_no", None)
            else:
                sc.pop("isoa_no", None)
                sc.pop("bplc_no", None)
        elif sid == "nps":
            m = _digits(f.get("mng_no"))
            if len(m) != 11:
                raise ValueError("국민연금 사업장관리번호는 11자리입니다.")
            sc["mng_no"] = m
        new[sid] = sc
    acct["sites"] = new
    # 새 키는 포트를 고정해 둔다 — 계정을 지우거나 순서가 바뀌어도 다른 키의 창·포트가 흔들리지 않게
    used = {int(s["port"]) for a in data["accounts"] for s in a["sites"].values() if "port" in s}
    p = 9400
    for sc in new.values():
        if "port" not in sc:
            while p in used:
                p += 1
            sc["port"] = p
            used.add(p)
    save(data)
    return acct["id"]


def remove(acct_id):
    data = load()
    data["accounts"] = [a for a in data["accounts"] if a["id"] != acct_id]
    save(data)


def key(kid):
    for k in keys():
        if k["id"] == kid:
            return k
    raise SystemExit(f"accounts.json 에 없는 키입니다: {kid}")

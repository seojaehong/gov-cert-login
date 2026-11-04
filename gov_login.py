"""공단 사이트 공동인증서 자동 로그인 (1단계: 근로복지공단 토탈서비스).

비밀번호는 이 PC·이 윈도우 계정에서만 풀리게(DPAPI) 암호화해 저장한다.
화면·로그·파일 어디에도 평문으로 남기지 않는다.

  python gov_login.py certs                 # PC 인증서 목록(번호)
  python gov_login.py store <인증서번호>     # 비밀번호 1회 등록(입력 숨김)
  python gov_login.py login comwel [--cert N] [--keep]
        → 로그인 성공 시 브라우저를 열어 둔 채 대기(--keep) 또는 세션 저장 후 종료
"""
import argparse
import base64
import getpass
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

import accounts
import secret_store
from list_certs import certs

if sys.stdout:  # 설치본(창 없는 exe)에서 출력처가 없을 수 있다
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if sys.stderr:
    sys.stderr.reconfigure(encoding="utf-8")


def _logs():
    os.makedirs(accounts.LOGS, exist_ok=True)
    return accounts.LOGS



# ── 비밀번호 저장소 (DPAPI, secret_store.py) ──────────────────────────
def store(cert_idx):
    cs = certs()
    c = cs[cert_idx]
    print(f"인증서: {c['cn']} (만료 {c['not_after']})")
    if sys.stdin.isatty():
        p1 = getpass.getpass("인증서 비밀번호: ")
        p2 = getpass.getpass("한 번 더: ")
    else:  # 터미널 입력이 없는 곳(Claude Code `!` 등) → 별표로 가리는 작은 창
        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        p1 = simpledialog.askstring("gov-cert-login", f"{c['cn']}\n인증서 비밀번호", show="*", parent=root) or ""
        p2 = simpledialog.askstring("gov-cert-login", "한 번 더", show="*", parent=root) or ""
        root.destroy()
    if not p1 or p1 != p2:
        sys.exit("두 입력이 다릅니다. 저장하지 않았습니다.")
    secret_store.put(c["cn"], p1)
    print("저장했습니다(이 PC 계정에서만 풀립니다).")


def store_rrn(site):
    """개인 탭 로그인용 주민등록번호를 DPAPI 로 저장한다. 사용자가 PowerShell 에서 직접 실행한다."""
    import getpass as _gp
    p1 = "".join(ch for ch in _gp.getpass(f"[{site}] 주민등록번호(13자리, 화면에 안 보임): ") if ch.isdigit())
    p2 = "".join(ch for ch in _gp.getpass("한 번 더: ") if ch.isdigit())
    if len(p1) != 13 or p1 != p2:
        sys.exit("13자리가 아니거나 두 입력이 다릅니다. 저장하지 않았습니다.")
    secret_store.put("rrn:" + site, p1)
    print("저장했습니다(이 PC 계정에서만 풀립니다).")


def store_sitepw(site):
    """국민연금 EDI 「사업장 비밀번호」(인증서 비밀번호와 별개)를 DPAPI 로 저장. 사용자가 PowerShell 에서 직접 실행."""
    import getpass as _gp
    p1 = _gp.getpass(f"[{site}] EDI 사업장 비밀번호(화면에 안 보임): ")
    p2 = _gp.getpass("한 번 더: ")
    if not p1 or p1 != p2:
        sys.exit("두 입력이 다릅니다. 저장하지 않았습니다.")
    secret_store.put("site:" + site, p1)
    print("저장했습니다(이 PC 계정에서만 풀립니다).")


def _sitepw(site):
    return secret_store.get("site:" + str(site))


def _rrn(site):
    return secret_store.get("rrn:" + str(site))


def _secret(cn):
    v = secret_store.get(cn)
    if v is None:
        sys.exit(f"인증서 비밀번호가 등록되지 않았습니다 — 런처의 「설정」에서 입력하세요  ({cn})")
    return v


# ── 사이트별 로그인 ──────────────────────────────────────────────────


def _pick_cert(site_cfg, idx):
    cs = certs()
    if idx is not None:
        return cs[idx]
    want = site_cfg.get("cert_cn")
    for c in cs:
        if want and c["cn"] == want:
            return c
    sys.exit(f"config.json 의 cert_cn 과 맞는 인증서가 없습니다. --cert 번호로 지정하세요. 목록: python gov_login.py certs")


DROP_JS = r"""
(items) => {
  const dt = new DataTransfer();
  for (const it of items) {
    const bin = Uint8Array.from(atob(it.b64), c => c.charCodeAt(0));
    dt.items.add(new File([bin], it.name, {type: 'application/octet-stream'}));
  }
  // certselect.js setPFXDragAndDrop: dragenter 는 부모, drop 은 #xwup_drag_zone 이 받는다(261103 소스 확인)
  const zone = document.querySelector('#xwup_drag_zone');
  if (!zone) return ['no #xwup_drag_zone'];
  const ev = t => new DragEvent(t, {bubbles: true, cancelable: true, dataTransfer: dt});
  zone.parentNode.parentNode.dispatchEvent(ev('dragenter'));
  zone.dispatchEvent(ev('dragover'));
  zone.dispatchEvent(ev('drop'));
  return ['#xwup_drag_zone'];
}
"""


def _type_pw(page, sel, pw, fr=None):
    """AnySign 암호칸은 fill(값만 대입)을 무시해 「인증서 암호를 입력하십시오」가 난다(261103 실측 3회) → 키 입력으로 넣는다.
    fr = 인증서 창이 iframe 안에 있을 때(국민연금 KSBiz). 키 입력은 페이지 키보드로 보낸다."""
    t = fr or page
    try:
        t.click(sel, timeout=5000)
    except Exception:  # noqa: BLE001 — 건보 PC 경로: 암호칸 위를 투명 층이 덮어 클릭이 막힌다(261103 실측) → 초점만 준다
        t.focus(sel)
    t.fill(sel, "")
    page.keyboard.type(pw, delay=40)
    time.sleep(0.5)


def _click_ok(page):
    """xwup 확인 버튼 — 투명 층에 막히면 MouseEvent 로 직접 누른다."""
    try:
        page.click("#xwup_OkButton", timeout=5000)
    except Exception:  # noqa: BLE001
        page.evaluate("""() => { const b = document.querySelector('#xwup_OkButton');
          ['mousedown','mouseup','click'].forEach(t => b.dispatchEvent(new MouseEvent(t, {bubbles: true, cancelable: true, view: window}))); }""")


def _fill_xwup(page, cert, pw):
    """AnySign 웹 인증서 창(xwup).

    ① 브라우저 저장소 목록에 그 인증서가 있으면 → 행 선택 → 암호(#xwup_certselect_lite_input1) → 확인
    ② 없으면 → signCert.der+signPri.key 를 #xwup_drag_zone 에 끌어놓기 → 뜨는 암호창
       (#xwup_inputpasswd_tek_input1, 「브라우저에 저장」 기본 체크) 에 암호 → #xwup_ok.
       이때 브라우저 저장소에 저장되므로 다음부터는 ① 로 간다.
    """
    try:
        page.wait_for_selector("#xwup_OkButton", state="visible", timeout=45000)
    except Exception:
        page.screenshot(path=os.path.join(_logs(), "xwup_fail.png"))
        raise
    time.sleep(2)
    row = page.locator("#xwup_cert_table tbody tr").filter(has_text=cert["cn"][:10])
    if row.count():
        row.first.click()
        if pw is None:
            print("[dry] 브라우저 저장소에 인증서 있음 → 목록 선택 경로")
            return
        # 암호칸은 경로마다 다르다 — 브라우저 저장소=lite, PC(AnySign4PC 하드디스크)=tek(261103 건보 실측). 보이는 칸을 쓴다
        sel = page.evaluate("""() => { const e = [...document.querySelectorAll('input.xwup-pw-box[type=password]')]
          .find(x => x.getBoundingClientRect().width > 0); return e ? '#' + e.id : '#xwup_certselect_lite_input1'; }""")
        if _keypad_only(page, sel):
            _wait_user_keypad(page)
            return
        _type_pw(page, sel, pw)
        _click_ok(page)
        return
    _drop_and_pw(page, cert, pw)


def _keypad_only(page, sel):
    """건보 EDI 는 암호칸이 readonly·disabled 인 보안 키패드 전용이다(261103 실측) — 자동 입력하지 않는다."""
    return page.evaluate("s => { const e = document.querySelector(s); return !!e && (e.readOnly || e.disabled); }", sel)


def _wait_user_keypad(page, sec=300):
    print("▶ 보안 키패드입니다. 화면 키패드로 인증서 비밀번호를 직접 눌러 확인해 주세요(최대 5분 기다립니다).", flush=True)
    for _ in range(sec // 2):
        time.sleep(2)
        if not page.locator("#xwup_OkButton, #xwup_ok").first.is_visible():
            return


def _drop_and_pw(page, cert, pw):
    files = [os.path.join(cert["dir"], "signCert.der"), os.path.join(cert["dir"], "signPri.key")]
    fin = page.locator("input[type=file]")
    done = False
    for i in range(fin.count()):
        try:
            fin.nth(i).set_input_files(files)
            done = True
            break
        except Exception:  # noqa: BLE001
            continue
    if not done:  # 파일 input 이 없다(261103 실측) → 끌어놓기(drop) 이벤트로 파일 전달
        payload = [{"name": os.path.basename(f), "b64": base64.b64encode(open(f, "rb").read()).decode()} for f in files]
        res = page.evaluate(DROP_JS, payload)
        done = "drop"
        print("[drop]", res)
    page.wait_for_selector("#xwup_inputpasswd_tek_input1", state="visible", timeout=15000)
    if pw is not None:
        if _keypad_only(page, "#xwup_inputpasswd_tek_input1"):
            _wait_user_keypad(page)
            return
        _type_pw(page, "#xwup_inputpasswd_tek_input1", pw)
        page.click("#xwup_ok")
        return
    if pw is None:  # 시험(--dry): 암호 입력 전까지만
        rows = page.locator("#xwup_cert_table").inner_text()
        print("[dry] 파일입력:", "input" if done else "chooser", "| 목록:", " ".join(rows.split())[:200])
        print("[dry] 보이는 암호칸·버튼:", page.evaluate(r"""() => [...document.querySelectorAll('input[type=password], [id^=xwup] button, [id^=xwup] input[type=checkbox]')]
            .filter(e => e.offsetParent !== null).map(e => e.id + ':' + (e.innerText || e.type || '').trim().slice(0, 12))"""))
        print("[dry] 암호창 요소:", page.evaluate(r"""() => {
            let d = document.getElementById('xwup_inputpasswd_tek_input1');
            for (let i = 0; i < 8 && d; i++) { d = d.parentElement; if (d.querySelectorAll('button').length) break; }
            return d ? [d.id + '.' + d.className, ...[...d.querySelectorAll('button, input')].filter(e => e.offsetParent !== null)
                .map(e => e.tagName + '#' + e.id + '.' + e.className + ':' + (e.innerText || e.value || e.type || '').trim().slice(0, 14))] : [];
        }"""))
        return
    _type_pw(page, "#xwup_certselect_lite_input1", pw)
    _click_ok(page)


def _unmodal(page):
    """로그인 직후 「보험사무대행기관 정보 확인」·공지 레이어(_modal)가 클릭을 가로챈다(261103 실측)."""
    page.evaluate("""() => {
      document.querySelectorAll('[id$=samuInfoPopup_close], .w2popup_window [id$=_close], .w2window [id$=_close]')
        .forEach(e => { if (e.offsetParent) ['mousedown','mouseup','click'].forEach(t => e.dispatchEvent(new MouseEvent(t, {bubbles: true}))); });
      const m = document.getElementById('_modal'); if (m) m.style.display = 'none';
    }""")
    time.sleep(1.5)


def _comwel_member(page):
    """헤더의 로그인 계정명(로그아웃 상태면 빈 문자열)."""
    return page.evaluate("""() => { const e = document.getElementById('mf_wfm_header_txt_memberName');
      return e && e.offsetParent ? e.innerText.trim() : ''; }""")


def login_comwel(page, site_cfg, cert, pw):
    page.goto("https://total.comwel.or.kr/", wait_until="domcontentloaded", timeout=60000)
    time.sleep(6)
    hint = site_cfg.get("account_hint")
    who = _comwel_member(page)
    if who:
        if not hint or re.search(hint, who):
            return True
        print("다른 계정으로 로그인돼 있어 로그아웃합니다:", who)
        _unmodal(page)
        page.evaluate("""() => { const a = document.getElementById('mf_wfm_header_btn_logout');
          ['mouseover','mousedown','mouseup','click'].forEach(t => a.dispatchEvent(new MouseEvent(t, {bubbles: true, cancelable: true, view: window}))); }""")
        time.sleep(6)
        page.goto("https://total.comwel.or.kr/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(6)
        if _comwel_member(page):
            raise SystemExit("로그아웃이 되지 않았습니다: " + _comwel_member(page))
    _unmodal(page)
    page.evaluate("""() => { const a = document.getElementById('mf_wfm_header_btn_login');
      ['mouseover','mousedown','mouseup','click'].forEach(t => a.dispatchEvent(new MouseEvent(t, {bubbles: true, cancelable: true, view: window}))); }""")
    time.sleep(6)
    if site_cfg.get("login_tab") == "personal":
        # 개인 탭 → 사무대행 「대표자/소속직원」 → 주민번호는 사용자가 직접 입력(도구는 입력하지 않는다)
        page.click("#mf_wfm_content_tabControl1_tab_tabs1_tabHTML")
        time.sleep(2)
        page.click("label[for=mf_wfm_content_u_group_fg3_input_0]")
        page.click("label[for=mf_wfm_content_chkAgreeRgno1_input_0]")
        page.focus("#mf_wfm_content_rgno1_1")
        rrn = _rrn(site_cfg.get("_site"))
        if rrn:  # 사용자가 store-rrn 으로 저장해 둔 값(DPAPI) — 화면·로그에 찍지 않는다
            page.keyboard.type(rrn[:6], delay=40)
            page.focus("#mf_wfm_content_rgno1_2")
            page.keyboard.type(rrn[6:], delay=40)
            rrn = None
        else:
            print("▶ 브라우저의 주민등록번호 칸에 직접 입력해 주세요(최대 5분 기다립니다).", flush=True)
        for _ in range(150):
            time.sleep(2)
            if len(page.input_value("#mf_wfm_content_rgno1_1")) == 6 and len(page.input_value("#mf_wfm_content_rgno1_2")) == 7:
                break
        else:
            raise SystemExit("주민등록번호 입력을 기다리다 시간이 지났습니다")
        time.sleep(1)
        page.locator("a.boxes").filter(has_text="[개인] 공동인증서").first.click()
        _fill_xwup(page, cert, pw)
        for _ in range(30):
            time.sleep(2)
            who = _comwel_member(page)
            if who:
                print("로그인 계정:", who)
                return not hint or bool(re.search(hint, who))
        return False
    page.click("#mf_wfm_content_tabControl1_tab_tabs2_tabHTML")          # 사업자 탭
    time.sleep(2)
    kind = {"사업장": 0, "사무대행": 1, "의료기관": 2}[site_cfg.get("kind", "사무대행")]
    page.click(f"label[for=mf_wfm_content_u_group_fg_input_{kind}]")
    a, b, c = site_cfg["bizno"].split("-")
    page.fill("#mf_wfm_content_drno1_1", a)
    page.fill("#mf_wfm_content_drno1_2", b)
    page.fill("#mf_wfm_content_drno1_3", c)
    page.locator("a.boxes").filter(has_text="[사업자] 공동인증서").first.click()
    _fill_xwup(page, cert, pw)
    if pw is None:
        time.sleep(5)
        return False
    for _ in range(30):
        time.sleep(2)
        who = _comwel_member(page)
        if who:
            print("로그인 계정:", who)
            return not hint or bool(re.search(hint, who))
    return False


def _has(fr, eid):
    try:
        return fr.evaluate("id => !!document.getElementById(id)", eid)
    except Exception:  # noqa: BLE001
        return False


def _ksbiz_frame(page, timeout=30):
    for _ in range(timeout):
        for fr in page.frames:
            if _has(fr, 'certpwd'):
                return fr
        time.sleep(1)
    page.screenshot(path=os.path.join(_logs(), "ksbiz_fail.png"))
    sys.exit("KSBiz 인증서 창을 찾지 못했습니다: " + " ".join(f.url[-30:] + "=" + str(_has(f, "certpwd")) + "/" + str(f.is_detached()) for f in page.frames))


def _fill_ksbiz(page, fr, cert, pw):
    """라온시큐어 KSBiz 인증서 창(국민연금 EDI, 261103 실측).

    ① 브라우저 저장소 목록에 있으면 → 행 선택 → #certpwd → 확인
    ② 없으면 → 「인증서 찾기」(#searchSign) → 알림 「열기」 → 파일선택 signCert.der+signPri.key
       → 암호창 #pop_cert (「브라우저에 저장」 #save_sign 기본 체크) → 그 창의 확인
    """
    time.sleep(2)
    row = fr.locator("tr").filter(has_text=cert["cn"][:10])
    if not row.count():
        fs = [os.path.join(cert["dir"], "signCert.der"), os.path.join(cert["dir"], "signPri.key")]
        fr.locator("#searchSign").click()
        time.sleep(1.5)
        with page.expect_file_chooser(timeout=10000) as fc:
            fr.get_by_text("열기", exact=True).first.click()
        fc.value.set_files(fs)
        fr.wait_for_selector("#pop_cert", state="visible", timeout=15000)
        if pw is None:
            print("[dry] 파일 넣기 → 암호창(#pop_cert)까지 확인")
            return
        _type_pw(page, "#pop_cert", pw, fr)
        fr.locator("#pop_cert").locator("xpath=ancestor::*[.//a[contains(@class,'btn_org')]][1]").locator("a.btn_org").first.click()
        time.sleep(3)
        if not fr.locator("#certpwd").is_visible():  # 저장과 함께 바로 서명·로그인된 경우
            return
        row = fr.locator("tr").filter(has_text=cert["cn"][:10])
    if row.count():
        row.first.click()
    if pw is None:
        print("[dry] 브라우저 저장소에 인증서 있음 → 목록 선택 경로")
        return
    _type_pw(page, "#certpwd", pw, fr)
    fr.locator("#certpwd").locator("xpath=ancestor::*[.//a[contains(@class,'btn_org')]][1]").locator("a.btn_org").first.click()


def login_nps(page, site_cfg, cert, pw):
    page.goto("https://edi.nps.or.kr/", wait_until="domcontentloaded", timeout=60000)
    time.sleep(8)
    page.fill("#txtBplcMngNo", site_cfg["mng_no"])
    page.locator("button.managment-number-button").first.click()
    time.sleep(3)
    page.get_by_text("전체동의", exact=True).first.click()      # 로그인마다 뜨는 이용약관 동의(사용자가 매번 누르던 것)
    time.sleep(1)
    page.get_by_text("공동인증", exact=True).first.click()
    _fill_ksbiz(page, _ksbiz_frame(page), cert, pw)
    if pw is None:
        time.sleep(5)
        return False
    # 인증서 다음에 「비밀번호 확인」(EDI 사업장 비밀번호) 창이 뜬다(261103 실측, #pwdPassword)
    try:
        page.wait_for_selector("#pwdPassword", state="visible", timeout=20000)
        sp = _sitepw(site_cfg["_site"])  # 사업장 비밀번호는 계정마다 다르다(secret_id 별 저장)
        if sp:
            _type_pw(page, "#pwdPassword", sp)
            sp = None
            page.locator("#pwdPassword").locator("xpath=ancestor::*[.//button[normalize-space()='확인'] or .//a[normalize-space()='확인']][1]") \
                .locator("button:has-text('확인'), a:has-text('확인')").first.click()
        else:
            print("▶ 사업장 비밀번호(EDI)를 화면에 직접 넣고 확인을 눌러 주세요 — 저장하려면 store-sitepw nps", flush=True)
    except Exception:  # noqa: BLE001 — 창이 안 뜨는 계정이면 그냥 진행
        pass
    for _ in range(30):
        time.sleep(2)
        if "로그아웃" in page.inner_text("body")[:5000]:
            return True
    return False


def login_nhis(page, site_cfg, cert, pw):
    """건보 EDI — 「브라우저인증서 로그인」(img 두 번째, enableAnySignLite(true)) → 키보드보안 권유 confirm 취소
    → 토탈과 같은 AnySign xwup 창(261103 실측)."""
    page.goto("https://edi.nhis.or.kr/", wait_until="domcontentloaded", timeout=60000)
    time.sleep(10)
    # 새 프로필에서는 첫 클릭이 무시되는 일이 있다(261103) → 창이 뜰 때까지 최대 3회
    # 261103 — 기본은 PC 경로(AnySign4PC, img 첫 번째). 크롬 「로컬 네트워크 접근 차단」을 launch 인자로 풀어야
    # 데몬(wss://localhost:10531)에 붙는다(안 풀면 설치돼 있어도 「설치하라」만 반복). GOV_NHIS_MODE=browser 면 옛 경로.
    pc = os.environ.get("GOV_NHIS_MODE", "pc") == "pc"
    xw = False
    for _ in range(3):
        btn = page.locator("img[alt='공동인증서 로그인']")
        (btn.nth(0 if pc else 1) if btn.count() > 1 else page.get_by_text("브라우저인증서 로그인").first).click()
        try:
            page.wait_for_selector("#xwup_OkButton", state="visible", timeout=15000)
            xw = True
            break
        except Exception:
            if pc:
                break  # PC 경로는 브라우저 창이 아니라 별도 인증서 창이 뜬다
            time.sleep(3)
    if not xw:
        print("▶ PC 인증서 창이 떴으면 인증서를 고르고 암호를 입력해 주세요(최대 5분).")
        for _ in range(150):
            time.sleep(2)
            if any(k in "".join(f.evaluate("() => document.body ? document.body.innerText.slice(0, 4000) : ''") for f in page.frames if not f.is_detached()) for k in ("로그아웃", "신규문서", "단위사업장 기호")):
                return True
        return False
    _fill_xwup(page, cert, pw)
    if pw is None:
        time.sleep(5)
        return False
    for _ in range(30):
        time.sleep(2)
        if any(k in "".join(f.evaluate("() => document.body ? document.body.innerText.slice(0, 4000) : ''") for f in page.frames if not f.is_detached()) for k in ("로그아웃", "신규문서", "단위사업장 기호")):
            return True
    return False


SITES = {"comwel": login_comwel, "nps": login_nps, "nhis": login_nhis}


def _port_alive(port):
    import urllib.request
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2).read()
        return True
    except Exception:  # noqa: BLE001
        return False


def _resolve(target):
    """target = accounts.json 키 id("계정:사이트") → (사이트, 사이트설정, 프로필, 포트, 파일 꼬리표)."""
    import accounts
    k = accounts.key(target)
    if not k["ready"]:
        raise SystemExit(f"{k['org']} 로그인은 아직 지원하지 않습니다.")
    cfg = dict(k["cfg"], _site=k["secret_id"])  # _site = 저장 암호·주민번호를 찾는 이름
    return k["site"], cfg, k["profile"], str(k["port"]), target.replace(":", "_")


def login(target, cert_idx, keep, dry=False):
    site, site_cfg, profile, port, tag = _resolve(target)
    cert = _pick_cert(site_cfg, cert_idx)
    pw = None if dry else _secret(cert["cn"])
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(profile, channel="chrome", headless=False,
                                                   viewport={"width": 1400, "height": 900},
                                                   args=["--remote-debugging-port=" + port]  # 로그인 뒤 다른 스크립트가 connect_over_cdp 로 붙는다
                                                   + (["--disable-features=LocalNetworkAccessChecks"] if site == "nhis" else []))  # 건보 보안모듈 데몬 접속 허용(261103)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        msgs = []
        # 「키보드보안 설치·적용」 권유 확인창은 취소(설치·다운로드로 빠지지 않게), 나머지는 확인
        page.on("dialog", lambda d: (msgs.append(d.message[:200]),
                                     d.dismiss() if (d.type == "confirm" and "키보드보안" in d.message) else d.accept()))
        try:
            ok = SITES[site](page, site_cfg, cert, pw)
        except BaseException as e:  # noqa: BLE001 — 예외여도 창을 남기고 사유를 파일로 남긴다
            ok = False
            msgs.append("예외: " + type(e).__name__ + " " + str(e)[:300])
            try:
                page.screenshot(path=os.path.join(_logs(), f"fail_{tag}.png"))
            except Exception:  # noqa: BLE001
                pass
        pw = None
        with open(os.path.join(_logs(), f"last_{tag}.txt"), "w", encoding="utf-8") as f:
            f.write(("로그인 성공" if ok else "로그인 실패") + " | " + " / ".join(msgs[-4:]) + "\n")
        print("로그인 성공" if ok else "로그인 실패", "| 알림:", msgs[-3:])
        if keep:  # 실패해도 창을 남겨 사용자가 직접 마무리할 수 있게
            print("브라우저를 열어 둡니다. 끝내려면 창을 닫으세요.")
            closed = []
            ctx.on("close", lambda _c: closed.append(1))
            # 창이 닫혀도 ctx.pages 가 안 비는 경우가 있어(프로세스가 남는다, 261104 실측 10개) 포트 응답도 본다
            try:
                while ctx.pages and not closed and _port_alive(port):
                    time.sleep(3)
            except Exception:  # noqa: BLE001
                pass
        ctx.close()
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("certs")
    s = sub.add_parser("store")
    s.add_argument("idx", type=int)
    r = sub.add_parser("store-rrn")
    r.add_argument("site", help="저장 이름(accounts.json 의 secret_id)")
    sp_ = sub.add_parser("store-sitepw")
    sp_.add_argument("site", help="저장 이름(accounts.json 의 secret_id)")
    lg = sub.add_parser("login")
    lg.add_argument("site", help="키 id — 계정id:사이트 (accounts.json)")
    lg.add_argument("--cert", type=int)
    lg.add_argument("--keep", action="store_true")
    lg.add_argument("--dry", action="store_true", help="암호 입력 직전까지만")
    a = ap.parse_args()
    if a.cmd == "certs":
        for i, c in enumerate(certs()):
            print(i, c["cn"], c["issuer"], c["not_after"])
    elif a.cmd == "store-sitepw":
        store_sitepw(a.site)
    elif a.cmd == "store-rrn":
        store_rrn(a.site)
    elif a.cmd == "store":
        store(a.idx)
    else:
        sys.exit(0 if login(a.site, a.cert, a.keep, a.dry) else 1)

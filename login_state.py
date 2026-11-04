"""포트별 로그인 상태 한 줄 출력. python login_state.py 9337 9338"""
import sys

from playwright.sync_api import sync_playwright

if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")
with sync_playwright() as p:
    for port in sys.argv[1:]:
        try:
            br = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=4000)
        except Exception:  # noqa: BLE001
            print(port, "창없음")
            continue
        pages = [pg for c in br.contexts for pg in c.pages if pg.url.startswith("http")]
        st = []
        for pg in pages:
            try:
                t = " ".join(f.evaluate("() => document.body ? document.body.innerText.slice(0, 6000) : ''") for f in pg.frames)
            except Exception:  # noqa: BLE001
                t = ""
            st.append(("로그인됨" if any(k in t for k in ("로그아웃", "신규문서", "단위사업장 기호")) else "미로그인") + " " + pg.url[:50])
        print(port, " | ".join(st) or "페이지없음")
        br.close()

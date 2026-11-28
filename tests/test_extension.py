"""연결 확장(extension/) 정적 시험 — 권한 하나·외부 호출은 조회 확장(gov4) 하나만·전달하는 요청은 ping/open 뿐."""
import json
import re
from pathlib import Path

EXT = Path(__file__).resolve().parents[1] / "extension"
GOV4_ID = "nhlbkdfkpdogfddbkhppbenflbcdkagn"  # insurance-connector extension/gov4 manifest key 의 id


def _m():
    return json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))


def test_manifest_one_permission_and_only_gov4_may_call():
    m = _m()
    assert m["permissions"] == ["nativeMessaging"]
    assert "host_permissions" not in m
    assert m["externally_connectable"] == {"ids": [GOV4_ID]}  # 웹 페이지(matches)는 부를 수 없다
    assert m["background"] == {"service_worker": "background.js"}


def test_background_checks_sender_and_relays_only_ping_open():
    s = (EXT / "background.js").read_text(encoding="utf-8")
    assert "onMessageExternal" in s and "onConnectExternal" not in s
    assert re.search(r"sender\.id\s*!==\s*GOV4", s)
    assert f"'{GOV4_ID}'" in s
    # 받은 메시지를 그대로 넘기지 않는다 — 새 객체로 다시 만든다
    assert re.search(r"\{\s*type:\s*'ping'\s*\}", s)
    assert re.search(r"\{\s*type:\s*'open',\s*key\s*\}", s)
    assert "sendNativeMessage(HOST, msg" not in s
    assert not re.search(r"chrome\.storage|localStorage|console\.(log|info|debug)|fetch\(", s)

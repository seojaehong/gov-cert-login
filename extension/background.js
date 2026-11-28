// 조회 확장(gov4) 측면 패널의 「로그인 창 열기」를 받아 「공단 로그인」 프로그램에 넘긴다.
// 부를 수 있는 것은 manifest externally_connectable 의 gov4 하나뿐이고, 여기서도 보낸 확장 id 를 다시 본다.
// 넘기는 요청은 ping(키 목록)·open(키 id) 둘뿐이며, 받은 메시지를 그대로 넘기지 않고 새로 만든다.
const HOST = 'com.govcertlogin.launcher';
const GOV4 = 'nhlbkdfkpdogfddbkhppbenflbcdkagn';

function ask(req) {
  return new Promise((resolve) => {
    chrome.runtime.sendNativeMessage(HOST, req, (resp) => {
      if (chrome.runtime.lastError) resolve({ ok: false, error: chrome.runtime.lastError.message });
      else resolve(resp || { ok: false, error: '응답 없음' });
    });
  });
}

chrome.runtime.onMessageExternal.addListener((msg, sender, reply) => {
  if (sender.id !== GOV4) return false;
  let req = null;
  if (msg?.type === 'ping') req = { type: 'ping' };
  else if (msg?.type === 'open' && typeof msg.key === 'string' && msg.key.length < 64) {
    const key = msg.key;
    req = { type: 'open', key };
  }
  if (!req) { reply({ ok: false, error: '지원하지 않는 요청입니다' }); return false; }
  ask(req).then(reply);
  return true; // 비동기 응답
});

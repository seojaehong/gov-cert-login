// 「공단 로그인」 프로그램(네이티브 호스트)에 키 목록을 묻고, 누른 키의 창을 열게 한다.
// 보내는 값 = 요청 종류와 키 id 뿐. 암호·인증서 정보는 오가지 않는다.
const HOST = 'com.govcertlogin.launcher';
const list = document.getElementById('list');
const msg = document.getElementById('msg');

function ask(req) {
  return new Promise((resolve) => {
    chrome.runtime.sendNativeMessage(HOST, req, (resp) => {
      if (chrome.runtime.lastError) resolve({ ok: false, error: chrome.runtime.lastError.message });
      else resolve(resp || { ok: false, error: '응답 없음' });
    });
  });
}

function row(k) {
  const d = document.createElement('div');
  d.className = 'row';
  const t = document.createElement('div');
  t.textContent = k.org;
  const s = document.createElement('small');
  s.textContent = k.label;
  t.appendChild(s);
  const b = document.createElement('button');
  b.textContent = k.open ? '열려 있음' : '창 열기';
  b.disabled = k.open;
  b.addEventListener('click', async () => {
    b.disabled = true;
    msg.textContent = '창을 여는 중…';
    const r = await ask({ type: 'open', key: k.id });
    msg.textContent = r.ok ? (r.state === 'open' ? '이미 열려 있습니다.' : '로그인 창을 엽니다. 잠시 기다려 주세요.') : ('열지 못했습니다: ' + r.error);
    if (!r.ok) b.disabled = false;
  });
  d.append(t, b);
  return d;
}

(async () => {
  const r = await ask({ type: 'ping' });
  if (!r.ok) {
    msg.textContent = '「공단 로그인」 프로그램에 연결하지 못했습니다. 프로그램이 설치돼 있는지 확인해 주세요.';
    return;
  }
  list.replaceChildren(...r.keys.map(row));
  msg.textContent = r.keys.length ? '' : '「공단 로그인」 설정에 토탈·국민연금·건강보험 계정이 없습니다.';
})();

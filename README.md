# 공단 로그인 (gov-cert-login)

근로복지공단 토탈서비스·국민연금 EDI·건강보험 EDI에 **공동인증서로 로그인하는 윈도우 프로그램**입니다.
키 하나를 누르면 그 계정 전용 크롬 창이 열리고 로그인까지 진행합니다. 홈택스는 준비 중입니다.

- **키 = 계정 × 사이트.** 보험사무 계정이 여러 개여도 키마다 크롬 프로필이 따로라 서로 로그인을 끊지 않습니다.
- **한꺼번에 열기.** 「전체 열기」, 계정별 「모두 열기」, 숫자 키를 잇달아 누르는 조합(예 `1` `4`, `0` = 전체).
- **상태 표시.** 6초마다 각 창의 로그인 여부를 확인해 키에 불을 켭니다.

## 설치

1. [Releases](../../releases)에서 `GovLogin_setup_<버전>.exe`를 받아 실행합니다. 관리자 권한은 필요 없습니다.
2. 바탕화면의 「공단 로그인」을 엽니다. 처음이면 설정 화면이 뜹니다.
3. 계정 이름 → 인증서 고르기 → 인증서 비밀번호 → 쓸 사이트 체크 → 저장.

코드 서명 전이라 처음 실행할 때 「Windows의 PC 보호」 창이 뜰 수 있습니다. 「추가 정보 → 실행」을 누르세요.

### 필요한 것

- Windows 10/11 64비트, **구글 크롬**(로그인 창은 PC에 깔린 크롬으로 엽니다)
- 하드디스크(`NPKI`) 또는 USB에 있는 **공동인증서**. 다른 폴더에 있으면 설정의 「인증서 폴더 지정」
- 각 사이트가 요구하는 보안프로그램(예: 건강보험 EDI의 AnySign4PC). 사이트 안내대로 미리 설치해 두세요.

## 비밀번호는 어디에 저장되나

- 인증서 비밀번호, (토탈서비스 개인 탭을 쓸 때) 주민등록번호, 국민연금 EDI 사업장 비밀번호는
  **이 PC·이 윈도우 계정에서만 풀리는 윈도우 보안 저장소(DPAPI)**로 암호화해 `%LOCALAPPDATA%\gov-cert-login\secrets.json`에 둡니다.
- 서버로 보내지 않고, 화면·로그에 평문으로 남기지 않습니다. 설정 화면은 「저장됨」 여부만 보여 줍니다.
- 코드: [`secret_store.py`](secret_store.py)

## 하지 않는 것

- **보안 키패드·키보드보안 프로그램을 우회하지 않습니다.** 키패드 입력만 받는 화면이면 사용자가 직접 입력할 때까지 기다립니다.
- 신고·제출은 하지 않습니다. 로그인 창을 열어 두는 것까지입니다.
- 본인(또는 사무소)의 인증서로 본인 계정에 로그인하는 용도입니다.

## 실행 기록(로그)

`%LOCALAPPDATA%\gov-cert-login\logs`에 남습니다. 창이 안 뜨거나 로그인이 안 되면 여기부터 봅니다.

| 파일 | 내용 | 보관 |
|---|---|---|
| `run_<키>_<날짜-시각>.log` | 실행 한 번의 전체 기록. 첫 줄에 버전·포트 | 키마다 최근 10개 |
| `fail_<키>_<날짜-시각>.png` | 로그인 실패 때 화면 | 키마다 최근 3개(화면에 업무 내용이 담길 수 있음) |
| `last_<키>.txt` | 마지막 결과 한 줄(시각·성공/실패·알림) | 덮어씀 |

- 런처를 켤 때 30일 지난 기록은 지웁니다.
- 비밀번호·주민번호는 기록하지 않습니다.
- 창을 닫았는데 그 계정 크롬이 뒤에 남아 있으면, 다음에 열 때 그 계정 크롬만 정리하고 엽니다. 다른 계정 창과 평소 쓰는 크롬은 건드리지 않습니다.

## 다른 프로그램이 로그인된 창을 쓰려면

런처는 `%LOCALAPPDATA%\gov-cert-login\sessions.json`에 키별 크롬 디버깅 포트와 상태를 적습니다.
Playwright 등에서 `connect_over_cdp("http://127.0.0.1:<포트>")`로 붙어 조회할 수 있습니다.

## 건강보험 EDI에서 「AnySign for PC 설치가 필요」가 반복될 때

설치돼 있어도 다음 세 가지 때문에 이 알림이 뜹니다. 런처 실행 기록에 「⚠」로 시작하는 줄이 있으면 그 원인입니다.

1. **포트 설정이 바뀜** — 건보는 AnySign 데몬 포트 10531만 봅니다. 다른 기관 사이트의 AnySign 설치가 설정을 30308 등으로 바꾸면 실패합니다.
2. **크롬의 로컬 네트워크 접근 차단** — 크롬 156부터 사이트가 PC의 보안프로그램에 붙는 것을 막습니다.
3. **버전 차이** — 설치본과 사이트 요구 버전이 다르면 계속 설치하라고 합니다. 트레이의 AnySign을 끈 뒤 새로 설치하세요.

1·2는 관리자 PowerShell에서 한 번 실행하면 막힙니다(평소 쓰는 크롬에도 적용).

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_anysign_guard.ps1            # 설치
powershell -ExecutionPolicy Bypass -File tools\install_anysign_guard.ps1 -Uninstall # 제거
```

- 작업 스케줄러에 「gov-cert-login AnySign 포트 지킴이」를 SYSTEM 권한으로 등록합니다(로그온 때 + 10분마다). 포트가 바뀌어 있으면 10530·10531로 되돌리고, 기록을 `%ProgramData%\gov-cert-login\anysign_guard.log`에 남깁니다.
- 크롬 정책 `LocalNetworkAccessAllowedForUrls`에 공단 주소(nhis·nps·comwel·4insure)를 넣습니다. 크롬에 「조직에서 관리」 표시가 생깁니다.

## 개발

```powershell
pip install -r requirements.txt pytest
python -m pytest tests -q
pythonw launcher.py          # 런처 실행
# 설치 파일: PyInstaller → Inno Setup
python -m PyInstaller --noconfirm --distpath build/dist --workpath build/work build/govlogin.spec
ISCC /DAppVer=$(python -c "import version; print(version.__version__)") build\installer.iss   # → build\out\GovLogin_setup_<버전>.exe
```

### 새 판 내는 순서

1. 코드 수정 → `python -m pytest tests -q`
2. `version.py` 의 `__version__` 을 올린다 — **버전은 여기 한 곳뿐**입니다(installer.iss 에는 적지 않습니다).
3. `main` 에 push → `v<버전>` 태그를 push 하면 GitHub Actions가 시험·빌드 후 Releases에 setup.exe를 올립니다.
   태그와 `version.py` 가 다르면 빌드가 멈춥니다.
4. 런처는 시작할 때 최신 릴리스를 확인해, 더 새 판이 있으면 위쪽에 「새 버전」 단추를 띄웁니다.

로컬 빌드는 설치본을 직접 시험할 때만 합니다.

## 주의

공단 사이트 화면이 바뀌면 자동 로그인이 멈출 수 있습니다. 이 프로그램은 각 기관과 관계없는 개인 도구이며,
MIT 라이선스대로 어떤 보증도 하지 않습니다.

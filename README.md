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

## 다른 프로그램이 로그인된 창을 쓰려면

런처는 `%LOCALAPPDATA%\gov-cert-login\sessions.json`에 키별 크롬 디버깅 포트와 상태를 적습니다.
Playwright 등에서 `connect_over_cdp("http://127.0.0.1:<포트>")`로 붙어 조회할 수 있습니다.

## 개발

```powershell
pip install -r requirements.txt pytest
python -m pytest tests -q
pythonw launcher.py          # 런처 실행
# 설치 파일: PyInstaller → Inno Setup
python -m PyInstaller --noconfirm --distpath build/dist --workpath build/work build/govlogin.spec
ISCC build\installer.iss     # → build\out\GovLogin_setup_<버전>.exe
```

`v*` 태그를 올리면 GitHub Actions가 시험·빌드 후 Releases에 setup.exe를 올립니다.

## 주의

공단 사이트 화면이 바뀌면 자동 로그인이 멈출 수 있습니다. 이 프로그램은 각 기관과 관계없는 개인 도구이며,
MIT 라이선스대로 어떤 보증도 하지 않습니다.

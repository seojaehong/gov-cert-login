# PyInstaller 설정 — 폴더형(onedir). exe 하나로 합치지 않는다(백신 오탐·느린 시작).
#   빌드:  python -m PyInstaller --noconfirm --distpath build/dist --workpath build/work build/govlogin.spec
# 결과:   build/dist/GovLogin/GovLogin.exe  → Inno Setup(build/installer.iss)이 setup.exe 로 감싼다
# 크롬은 넣지 않는다 — PC에 깔린 크롬(channel="chrome")을 쓴다. playwright 는 드라이버(node)만 들어간다.
from PyInstaller.utils.hooks import collect_all

ROOT = SPECPATH + "/.."
pw_datas, pw_bins, pw_hidden = collect_all("playwright")

a = Analysis(
    [ROOT + "/launcher.py"],
    pathex=[ROOT],
    datas=[(ROOT + "/launcher.html", "."), (ROOT + "/launcher.ico", ".")] + pw_datas,
    binaries=pw_bins,
    hiddenimports=["gov_login", "login_state", "accounts", "list_certs", "secret_store", "win32crypt"] + pw_hidden,
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "PIL", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="GovLogin", icon=ROOT + "/launcher.ico",
          console=False, version=None)
coll = COLLECT(exe, a.binaries, a.datas, name="GovLogin")

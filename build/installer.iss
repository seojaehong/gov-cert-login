; 공단 로그인 설치 파일 — Inno Setup 6
;   빌드: ISCC build\installer.iss   (먼저 PyInstaller 로 build\dist\GovLogin 을 만든다)
;   결과: build\out\GovLogin_setup_<버전>.exe
; 사용자 권한으로 설치한다(관리자 불필요) — %LOCALAPPDATA%\Programs\GovLogin
; 계정 설정·저장 암호는 %LOCALAPPDATA%\gov-cert-login 에 있어 재설치·업데이트·제거해도 남는다.

#ifndef AppVer
  #define AppVer "0.1.0"
#endif

[Setup]
AppId={{A86A9AE9-E83E-42CD-87B7-186C6DAE0751}
AppName=공단 로그인
AppVersion={#AppVer}
AppPublisher=gov-cert-login
DefaultDirName={localappdata}\Programs\GovLogin
DefaultGroupName=공단 로그인
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=out
OutputBaseFilename=GovLogin_setup_{#AppVer}
SetupIconFile=..\launcher.ico
UninstallDisplayIcon={app}\GovLogin.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 아이콘 만들기"; Flags: checkedonce

[Files]
Source: "dist\GovLogin\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\공단 로그인"; Filename: "{app}\GovLogin.exe"
Name: "{group}\공단 로그인 제거"; Filename: "{uninstallexe}"
Name: "{userdesktop}\공단 로그인"; Filename: "{app}\GovLogin.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\GovLogin.exe"; Description: "공단 로그인 실행"; Flags: nowait postinstall skipifsilent

[Code]
// 크롬이 없으면 안내만 한다(설치는 계속). 로그인 창은 PC에 깔린 크롬을 쓴다.
function ChromeInstalled(): Boolean;
begin
  Result := FileExists(ExpandConstant('{pf}\Google\Chrome\Application\chrome.exe'))
    or FileExists(ExpandConstant('{pf32}\Google\Chrome\Application\chrome.exe'))
    or FileExists(ExpandConstant('{localappdata}\Google\Chrome\Application\chrome.exe'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (not ChromeInstalled()) then
    MsgBox('구글 크롬이 보이지 않습니다. 공단 로그인 창은 크롬으로 열리니 크롬을 먼저 설치해 주세요.', mbInformation, MB_OK);
end;

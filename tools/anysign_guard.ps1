# AnySign4PC 포트 지킴이 — 작업 스케줄러가 SYSTEM 권한으로 로그온 때와 10분마다 실행한다.
# 건보 EDI 는 데몬 직접 포트 10531(wss)만 본다. 다른 기관 사이트의 AnySign 설치가 설정을 30308·30309 등으로
# 덮어쓰면 건보는 「AnySign for PC 설치가 필요」로 실패한다(261112 실측). 바뀌어 있으면 되돌리고 데몬을 내린다
# (데몬은 다음 접속 때 새 포트로 다시 뜬다).
param(
    [string]$Conf = 'C:\Program Files (x86)\SoftForum\XecureWeb\AnySign\config\AnySign.conf',
    [string]$LogDir = (Join-Path $env:ProgramData 'gov-cert-login')
)
$ErrorActionPreference = 'Stop'
$conf = $Conf
$logDir = $LogDir
$log = Join-Path $logDir 'anysign_guard.log'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-GuardLog($msg) {
    Add-Content -Path $log -Value ("{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg) -Encoding UTF8
}

if (-not (Test-Path -LiteralPath $conf)) { exit 0 }
$text = [IO.File]::ReadAllText($conf)
$fixed = $text -replace '("no_tls_listen_port"\s*:\s*)"\d+"', '$1"10530"' -replace '("tls_listen_port"\s*:\s*)"\d+"', '$1"10531"'
if ($fixed -eq $text) { exit 0 }

$old = ([regex]::Matches($text, '"(no_tls_listen_port|tls_listen_port)"\s*:\s*"(\d+)"') | ForEach-Object { $_.Groups[2].Value }) -join '/'
Copy-Item -LiteralPath $conf -Destination (Join-Path $logDir ("AnySign.conf.{0}.bak" -f (Get-Date -Format 'yyMMdd-HHmmss')))
[IO.File]::WriteAllText($conf, $fixed, (New-Object Text.UTF8Encoding($false)))
Get-Process -Name AnySign4PC -ErrorAction SilentlyContinue | Stop-Process -Force
Write-GuardLog "포트 $old -> 10530/10531 로 되돌림, 데몬 재시작 대기"

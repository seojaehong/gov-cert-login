# 공단 보안프로그램 재발 방지 설치 — 관리자 PowerShell 에서 한 번 실행한다.
#   ① AnySign4PC 포트 지킴이(anysign_guard.ps1)를 Program Files 에 두고, 작업 스케줄러에 SYSTEM 작업으로 등록
#      (로그온 때 + 10분마다). 스크립트를 사용자 쓰기 가능한 곳에 두면 권한 상승 통로가 되므로 Program Files 에 둔다.
#   ② 크롬 정책 LocalNetworkAccessAllowedForUrls — 공단 사이트가 내 PC 보안프로그램(localhost)에 붙도록 허용.
#      크롬 156+ 의 로컬 네트워크 접근 차단 때문에 평소 크롬에서도 「설치가 필요」가 반복됐다(261103 실측).
#   제거: -Uninstall
param([switch]$Uninstall)
$ErrorActionPreference = 'Stop'
$dir = Join-Path $env:ProgramFiles 'gov-cert-login-guard'
$task = 'gov-cert-login AnySign 포트 지킴이'
$pol = 'HKLM:\SOFTWARE\Policies\Google\Chrome\LocalNetworkAccessAllowedForUrls'
$urls = @('https://[*.]nhis.or.kr', 'https://[*.]nps.or.kr', 'https://[*.]comwel.or.kr', 'https://[*.]4insure.or.kr')

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $dir -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $pol -ErrorAction SilentlyContinue
    'removed'
    exit 0
}

New-Item -ItemType Directory -Force -Path $dir | Out-Null
Copy-Item -Force (Join-Path $PSScriptRoot 'anysign_guard.ps1') (Join-Path $dir 'anysign_guard.ps1')

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument ("-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"{0}`"" -f (Join-Path $dir 'anysign_guard.ps1'))
$t1 = New-ScheduledTaskTrigger -AtLogOn
$t2 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 10)
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
Register-ScheduledTask -TaskName $task -Action $action -Trigger $t1, $t2 -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $task

New-Item -Force -Path $pol | Out-Null
$i = 1
foreach ($u in $urls) { New-ItemProperty -Force -Path $pol -Name "$i" -Value $u -PropertyType String | Out-Null; $i++ }
'installed'

# Decision 71: the PC signs in by itself after a reboot (Windows auto-logon) so Docker Desktop and TulporGo start
# without anyone at the desk; this script then locks the screen at once. It locks only when auto-logon is on AND the PC
# booted less than 5 minutes ago, so a normal manual sign-in is never locked.
#   Task Scheduler: "TulporGo lock after auto-logon", at log on of this user.
#   Check without locking: powershell -File lock-after-autologon.ps1 -DryRun
param(
    [switch]$DryRun,
    [Nullable[bool]]$AssumeAutoLogon,          # tests only
    [Nullable[double]]$AssumeUptimeMinutes     # tests only
)

$winlogon = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
$auto = if ($null -ne $AssumeAutoLogon) { $AssumeAutoLogon } else {
    (Get-ItemProperty $winlogon -Name AutoAdminLogon -ErrorAction SilentlyContinue).AutoAdminLogon -eq '1'
}
$uptime = if ($null -ne $AssumeUptimeMinutes) { $AssumeUptimeMinutes } else {
    ((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalMinutes
}
$lock = $auto -and $uptime -lt 5

if ($DryRun) {
    "autologon=$auto uptime_min=$([math]::Round($uptime, 1)) lock=$lock"
    return
}
if ($lock) {
    rundll32.exe user32.dll,LockWorkStation
}

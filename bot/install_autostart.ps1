# Register the TulporGo «tez orada» stub as a per-user logon task (no console window, restarts on failure).
# Approved by Saidakbar aka 2026-11-10 ("Ha, qo'y"). Remove with:  Unregister-ScheduledTask -TaskName "TulporGo coming-soon bot" -Confirm:$false
$name = "TulporGo coming-soon bot"
$bot  = Join-Path $PSScriptRoot "coming_soon.py"
$action   = New-ScheduledTaskAction -Execute "C:\Python314\pythonw.exe" -Argument "`"$bot`"" -WorkingDirectory $PSScriptRoot
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
            -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
            -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings `
    -Description "TulporGo: @tulporgobot 'tez orada' javobi (D:\Linux\coding\taxi-bot\bot\coming_soon.py)" -Force | Out-Null
Start-ScheduledTask -TaskName $name
Get-ScheduledTask -TaskName $name | Select-Object TaskName, State

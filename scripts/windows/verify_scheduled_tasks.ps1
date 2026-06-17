param(
    [string]$PythonExe = "",
    [string]$TaskPrefix = "trader-obsidian",
    [switch]$DryRunInbox,
    [switch]$Notify,
    [int]$WaitSeconds = 60,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$RegisterScript = Join-Path $PSScriptRoot "register_scheduled_tasks.ps1"
$LogDir = Join-Path $ProjectRoot "logs\scheduler"

if (-not $PythonExe) {
    $venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $PythonExe = $venvPython
    }
    else {
        $PythonExe = "python"
    }
}

$registerArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$RegisterScript`"",
    "-PythonExe", "`"$PythonExe`"",
    "-TaskPrefix", $TaskPrefix
)
if ($DryRunInbox) {
    $registerArgs += "-DryRunInbox"
}
if ($Notify) {
    $registerArgs += "-Notify"
}
if ($Force) {
    $registerArgs += "-Force"
}

Write-Host "==> Register scheduled tasks"
& powershell.exe @registerArgs
if ($LASTEXITCODE -ne 0) {
    throw "Task registration failed"
}

$taskNames = @(
    "$TaskPrefix-inbox",
    "$TaskPrefix-review",
    "$TaskPrefix-dashboard"
)

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

function Wait-TaskCompletion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TaskName,
        [Parameter(Mandatory = $true)]
        [datetime]$TriggeredAt,
        [Parameter(Mandatory = $true)]
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $task = Get-ScheduledTask -TaskName $TaskName
        $info = Get-ScheduledTaskInfo -TaskName $TaskName
        $hasCurrentRun = $info.LastRunTime -ge $TriggeredAt.AddSeconds(-2)
        if ($hasCurrentRun -and $task.State -ne "Running") {
            return $info
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    return Get-ScheduledTaskInfo -TaskName $TaskName
}

foreach ($taskName in $taskNames) {
    Write-Host ""
    Write-Host "==> Trigger $taskName"
    $before = Get-ChildItem -Path $LogDir -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
    $triggeredAt = Get-Date
    Start-ScheduledTask -TaskName $taskName

    $info = Wait-TaskCompletion -TaskName $taskName -TriggeredAt $triggeredAt -TimeoutSeconds $WaitSeconds
    Write-Host "LastRunTime : $($info.LastRunTime)"
    Write-Host "LastTaskResult : $($info.LastTaskResult)"

    $after = Get-ChildItem -Path $LogDir -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
    $newLogs = @()
    if ($after) {
        $beforePaths = @($before | ForEach-Object { $_.FullName })
        $newLogs = $after | Where-Object { $_.FullName -notin $beforePaths } | Select-Object -First 3
    }

    if ($newLogs.Count -eq 0) {
        Write-Host "No new log files detected in $LogDir"
    }
    else {
        foreach ($log in $newLogs) {
            Write-Host "Log: $($log.FullName)"
        }
    }

    if ($info.LastTaskResult -ne 0) {
        throw "$taskName failed with LastTaskResult=$($info.LastTaskResult)"
    }
}

Write-Host ""
Write-Host "Scheduled task verification completed."

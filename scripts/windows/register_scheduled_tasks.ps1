param(
    [string]$PythonExe = "python",
    [string]$TaskPrefix = "trader-obsidian",
    [switch]$DryRunInbox,
    [switch]$Notify,
    [string]$InboxInterval = "PT30M",
    [string]$ReviewTime = "09:00",
    [string]$DashboardTime = "08:00",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Runner = Join-Path $PSScriptRoot "run_scheduled_task.ps1"

function New-RunnerAction {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TaskName
    )

    $runnerArgs = @(
        "-NoProfile",
        "-WindowStyle", "Hidden",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$Runner`"",
        "-Task", $TaskName,
        "-PythonExe", "`"$PythonExe`""
    )

    if ($TaskName -eq "inbox" -and $DryRunInbox) {
        $runnerArgs += "-DryRun"
    }
    if ($Notify) {
        $runnerArgs += "-Notify"
    }

    New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument ($runnerArgs -join " ") `
        -WorkingDirectory $ProjectRoot
}

function Register-TraderTask {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ShortName,
        [Parameter(Mandatory = $true)]
        [Microsoft.Management.Infrastructure.CimInstance]$Trigger,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    $taskName = "$TaskPrefix-$ShortName"
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing -and -not $Force) {
        throw "Scheduled task '$taskName' already exists. Re-run with -Force to replace it."
    }
    if ($existing) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }

    $action = New-RunnerAction -TaskName $ShortName
    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2)

    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $Trigger `
        -Settings $settings `
        -Description $Description | Out-Null

    Write-Host "Registered $taskName"
}

function Convert-IsoDurationToTimeSpan {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    if ($Value -match "^PT(\d+)M$") {
        return New-TimeSpan -Minutes ([int]$Matches[1])
    }
    if ($Value -match "^PT(\d+)H$") {
        return New-TimeSpan -Hours ([int]$Matches[1])
    }
    if ($Value -match "^P(\d+)D$") {
        return New-TimeSpan -Days ([int]$Matches[1])
    }

    try {
        return [TimeSpan]::Parse($Value)
    }
    catch {
        throw "Unsupported interval '$Value'. Use PT30M, PT1H, P1D, or a TimeSpan value."
    }
}

$inboxTrigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).Date `
    -RepetitionInterval (Convert-IsoDurationToTimeSpan -Value $InboxInterval) `
    -RepetitionDuration (New-TimeSpan -Days 1)

Register-TraderTask `
    -ShortName "inbox" `
    -Trigger $inboxTrigger `
    -Description "Scan trader-obsidian Inbox on a repeating interval."

Register-TraderTask `
    -ShortName "review" `
    -Trigger (New-ScheduledTaskTrigger -Daily -At $ReviewTime) `
    -Description "Run trader-obsidian scheduled backtest review."

Register-TraderTask `
    -ShortName "dashboard" `
    -Trigger (New-ScheduledTaskTrigger -Daily -At $DashboardTime) `
    -Description "Update trader-obsidian Obsidian dashboard."

Write-Host ""
Write-Host "Done. Check with:"
Write-Host "  Get-ScheduledTask -TaskName '$TaskPrefix-*'"

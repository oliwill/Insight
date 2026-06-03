param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("inbox", "review", "dashboard", "all")]
    [string]$Task,

    [string]$PythonExe = "python",
    [switch]$DryRun,
    [switch]$Notify,
    [int]$ReviewDaysAfter = 30,
    [int]$ReviewLookback = 90
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$LogDir = Join-Path $ProjectRoot "logs\scheduler"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Invoke-TraderTask {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $logPath = Join-Path $LogDir "$Name-$timestamp.log"

    Push-Location $ProjectRoot
    try {
        "[$(Get-Date -Format s)] START $Name" | Tee-Object -FilePath $logPath
        "& $PythonExe $($Arguments -join ' ')" | Tee-Object -FilePath $logPath -Append

        & $PythonExe @Arguments 2>&1 | Tee-Object -FilePath $logPath -Append
        $exitCode = $LASTEXITCODE

        "[$(Get-Date -Format s)] END $Name exit=$exitCode" | Tee-Object -FilePath $logPath -Append
        if ($exitCode -ne 0) {
            throw "$Name failed with exit code $exitCode. See $logPath"
        }
    }
    finally {
        Pop-Location
    }
}

function Get-InboxArgs {
    $args = @("scripts\scan_inbox.py", "--json")
    if ($DryRun) { $args += "--dry-run" }
    if ($Notify) { $args += "--notify" }
    return $args
}

function Get-ReviewArgs {
    $args = @(
        "scripts\run_review.py",
        "--days-after", "$ReviewDaysAfter",
        "--lookback", "$ReviewLookback",
        "--json"
    )
    if ($Notify) { $args += "--notify" }
    return $args
}

function Get-DashboardArgs {
    $args = @("scripts\update_dashboard.py", "--json")
    if ($Notify) { $args += "--notify" }
    return $args
}

switch ($Task) {
    "inbox" {
        Invoke-TraderTask -Name "inbox" -Arguments (Get-InboxArgs)
    }
    "review" {
        Invoke-TraderTask -Name "review" -Arguments (Get-ReviewArgs)
    }
    "dashboard" {
        Invoke-TraderTask -Name "dashboard" -Arguments (Get-DashboardArgs)
    }
    "all" {
        Invoke-TraderTask -Name "inbox" -Arguments (Get-InboxArgs)
        Invoke-TraderTask -Name "review" -Arguments (Get-ReviewArgs)
        Invoke-TraderTask -Name "dashboard" -Arguments (Get-DashboardArgs)
    }
}

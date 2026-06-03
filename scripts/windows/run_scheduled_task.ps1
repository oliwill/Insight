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
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $false
}

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

        $stdoutPath = Join-Path $LogDir "$Name-$timestamp.stdout.log"
        $stderrPath = Join-Path $LogDir "$Name-$timestamp.stderr.log"
        $process = Start-Process `
            -FilePath $PythonExe `
            -ArgumentList $Arguments `
            -WorkingDirectory $ProjectRoot `
            -WindowStyle Hidden `
            -Wait `
            -PassThru `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath

        if (Test-Path $stdoutPath) {
            Get-Content -Path $stdoutPath | Tee-Object -FilePath $logPath -Append
            Remove-Item -LiteralPath $stdoutPath -Force
        }
        if (Test-Path $stderrPath) {
            Get-Content -Path $stderrPath | Tee-Object -FilePath $logPath -Append
            Remove-Item -LiteralPath $stderrPath -Force
        }

        $exitCode = $process.ExitCode

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

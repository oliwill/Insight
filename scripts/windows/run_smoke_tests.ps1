param(
    [string]$PythonExe = "",
    [switch]$SkipPytest,
    [switch]$SkipRuntimeChecks
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

function Resolve-PythonCommand {
    if ($PythonExe) {
        return [PSCustomObject]@{ Command = $PythonExe; PrefixArgs = @() }
    }

    $venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return [PSCustomObject]@{ Command = $venvPython; PrefixArgs = @() }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return [PSCustomObject]@{ Command = $python.Source; PrefixArgs = @() }
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return [PSCustomObject]@{ Command = $py.Source; PrefixArgs = @("-3") }
    }

    throw "No Python interpreter found. Create .venv or pass -PythonExe C:\path\to\python.exe"
}

function Invoke-PythonStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host "==> $Name"
    Write-Host "    $($Python.Command) $($Python.PrefixArgs -join ' ') $($Arguments -join ' ')"

    & $Python.Command @($Python.PrefixArgs + $Arguments)
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "$Name failed with exit code $exitCode"
    }
}

$Python = Resolve-PythonCommand

Push-Location $ProjectRoot
try {
    Invoke-PythonStep `
        -Name "Syntax compile: entry points" `
        -Arguments @(
            "-m", "py_compile",
            "config.py",
            "run_analysis.py",
            "scripts\analyze_stock.py",
            "trader_mcp.py",
            "notification.py",
            "telegram_bot.py",
            "inbox_watcher.py",
            "scheduler.py"
        )

    Invoke-PythonStep `
        -Name "Syntax compile: core modules" `
        -Arguments @(
            "-m", "py_compile",
            "data\analysis_pipeline.py",
            "data\manager.py",
            "data\earnings.py",
            "data\liquidity.py",
            "data\options.py",
            "data\correlation.py",
            "data\etf.py",
            "data\search.py",
            "analyzer\research_score.py",
            "analyzer\timing_engine.py",
            "analyzer\report_generator.py",
            "input\evidence.py",
            "memory\manager.py",
            "backtest\runner.py",
            "scripts\run_review.py",
            "scripts\scan_inbox.py",
            "scripts\update_dashboard.py"
        )

    if (-not $SkipPytest) {
        & $Python.Command @($Python.PrefixArgs + @("-m", "pytest", "--version")) | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "pytest is not installed. Run: $($Python.Command) $($Python.PrefixArgs -join ' ') -m pip install -r requirements.txt -r requirements-dev.txt"
        }

        Invoke-PythonStep `
            -Name "Regression tests" `
            -Arguments @(
                "-m", "pytest",
                "tests\test_yahoo_symbol.py",
                "tests\test_section_write.py",
                "tests\test_report_generator.py",
                "tests\test_backtest_review.py",
                "tests\test_dashboard_update.py",
                "tests\test_automation_entrypoints.py",
                "tests\test_scheduler.py",
                "tests\test_m3_boundaries.py"
            )
    }
    else {
        Write-Host ""
        Write-Host "==> Regression tests skipped by -SkipPytest"
    }

    if (-not $SkipRuntimeChecks) {
        Invoke-PythonStep `
            -Name "Config visibility" `
            -Arguments @("-c", "from config import Config; print(Config.get_wiki_dir())")

        Invoke-PythonStep `
            -Name "Inbox dry-run scan" `
            -Arguments @("scripts\scan_inbox.py", "--dry-run", "--json")

        Invoke-PythonStep `
            -Name "Review ticker discovery" `
            -Arguments @("scripts\run_review.py", "--list-tickers", "--json")
    }
    else {
        Write-Host ""
        Write-Host "==> Runtime checks skipped by -SkipRuntimeChecks"
    }

    Write-Host ""
    Write-Host "Smoke tests completed."
}
finally {
    Pop-Location
}

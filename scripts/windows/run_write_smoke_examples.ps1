param(
    [string]$PythonExe = "",
    [string[]]$Tickers = @("HIMS.US", "03986.HK"),
    [switch]$RequireChart
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
    foreach ($ticker in $Tickers) {
        Invoke-PythonStep `
            -Name "Write smoke example: $ticker" `
            -Arguments @("scripts\analyze_stock.py", $ticker)

        $verifyArgs = @("scripts\verify_write_smoke.py", $ticker)
        if ($RequireChart) {
            $verifyArgs += "--require-chart"
        }
        Invoke-PythonStep `
            -Name "Verify write smoke example: $ticker" `
            -Arguments $verifyArgs
    }

    Write-Host ""
    Write-Host "Write smoke examples completed."
}
finally {
    Pop-Location
}

param(
    [string]$PythonPath = "",
    [string]$OutputDir = "",
    [switch]$KeepBuildFiles
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BuildVenv = Join-Path $RepoRoot ".venv-build"
$Work = Join-Path $RepoRoot ".tmp\pyinstaller"
if (-not $OutputDir) { $OutputDir = Join-Path $RepoRoot "dist" }

function Invoke-Native {
    param([string]$FilePath, [string[]]$Arguments = @(), [switch]$Quiet)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        if ($Quiet) { & $FilePath @Arguments *> $null }
        else { & $FilePath @Arguments 2>&1 | ForEach-Object { Write-Host "  $_" } }
        return $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
}

if ($PythonPath) { $BuildPython = $PythonPath }
else {
    if (-not (Test-Path (Join-Path $BuildVenv "Scripts\python.exe"))) {
        Write-Host "Creating build environment..."
        if ((Invoke-Native "py" @("-3", "-m", "venv", $BuildVenv) -Quiet) -ne 0) { throw "Could not create the build environment." }
    }
    $BuildPython = Join-Path $BuildVenv "Scripts\python.exe"
}
if ((Invoke-Native $BuildPython @("-c", "import PyInstaller") -Quiet) -ne 0) {
    Write-Host "Installing PyInstaller into the build environment..."
    if ((Invoke-Native $BuildPython @("-m", "pip", "install", "--quiet", "pyinstaller") -Quiet) -ne 0) { throw "Could not install PyInstaller." }
}
$arguments = @(
    "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
    "--name", "Locdata Repacker", "--distpath", $OutputDir, "--workpath", $Work,
    "--specpath", $Work, "--paths", (Join-Path $RepoRoot "src"),
    "--hidden-import", "locdata_repacker.gui", "--hidden-import", "locdata_repacker.cli",
    "--hidden-import", "locdata_repacker.format", (Join-Path $RepoRoot "run_repacker.py")
)
if ((Invoke-Native $BuildPython $arguments) -ne 0) { throw "PyInstaller build failed." }
$exe = Join-Path $OutputDir "Locdata Repacker.exe"
if (-not (Test-Path -LiteralPath $exe)) { throw "Build produced no executable." }
if (-not $KeepBuildFiles -and (Test-Path -LiteralPath (Join-Path $RepoRoot ".tmp"))) { Remove-Item -LiteralPath (Join-Path $RepoRoot ".tmp") -Recurse -Force }
Write-Host ("Built {0} ({1:N1} MB)" -f $exe, ((Get-Item $exe).Length / 1MB))


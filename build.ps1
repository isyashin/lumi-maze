$scriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
$projectDir = $scriptDir
$venvPath = Join-Path -Path $projectDir -ChildPath '.venv'

# Create virtual environment if it doesn't exist
if (-not (Test-Path -Path $venvPath)) {
    & python -m venv $venvPath
}

# Activate virtual environment
$activateScript = Join-Path -Path $venvPath -ChildPath 'Scripts\activate.ps1'
. $activateScript

# Install requirements
$requirementsBuildPath = Join-Path -Path $projectDir -ChildPath 'requirements-build.txt'
& pip install -r $requirementsBuildPath

# Run PyInstaller
$runGamePath = Join-Path -Path $projectDir -ChildPath 'run_game.py'
$pyinstallerArgs = @(
    '--noconfirm',
    '--onedir',
    '--windowed',
    '--name', 'LumiMaze',
    '--paths', 'src',
    '--collect-all', 'ursina',
    $runGamePath
)
& pyinstaller $pyinstallerArgs

# Check exit code
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

# Print path to the resulting executable
$exePath = Join-Path -Path $projectDir -ChildPath 'dist\LumiMaze\LumiMaze.exe'
Write-Output "Build successful. Executable path: $exePath"
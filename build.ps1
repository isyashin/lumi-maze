$scriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
$projectDir = $scriptDir

Push-Location -Path $projectDir
try {
    $venvPath = Join-Path -Path $projectDir -ChildPath '.venv'
    $venvPython = Join-Path -Path $venvPath -ChildPath 'Scripts\python.exe'

    if (-not (Test-Path -Path $venvPython)) {
        & py -3.13 -m venv $venvPath
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to create venv with Python 3.13 (exit $LASTEXITCODE)"
            exit $LASTEXITCODE
        }
    }

    $requirementsBuildPath = Join-Path -Path $projectDir -ChildPath 'requirements-build.txt'

    & $venvPython -c "import ursina, PIL, PyInstaller, pytest"
    $importExit = $LASTEXITCODE
    if ($importExit -ne 0) {
        & $venvPython -m pip install -r $requirementsBuildPath
        if ($LASTEXITCODE -ne 0) {
            Write-Error "pip install failed (exit $LASTEXITCODE)"
            exit $LASTEXITCODE
        }
    }

    $runGamePath = Join-Path -Path $projectDir -ChildPath 'run_game.py'
    $pyinstallerArgs = @(
        '--noconfirm',
        '--onedir',
        '--windowed',
        '--name', 'LumiMaze',
        '--paths', 'src',
        '--collect-all', 'ursina',
        '--collect-all', 'panda3d',
        $runGamePath
    )

    & $venvPython -m PyInstaller $pyinstallerArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Error "PyInstaller failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }

    $exePath = Join-Path -Path $projectDir -ChildPath 'dist\LumiMaze\LumiMaze.exe'
    if (Test-Path -Path $exePath) {
        $absPath = (Resolve-Path -Path $exePath).Path
        Write-Output "Build successful. Executable path: $absPath"
    } else {
        Write-Error "Executable not found at $exePath"
        exit 1
    }
} finally {
    Pop-Location
}

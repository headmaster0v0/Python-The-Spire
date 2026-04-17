$ErrorActionPreference = "Stop"

$JAVA_HOME = "C:\Program Files\Java\jdk-1.8"
$JAVAC = "$JAVA_HOME\bin\javac.exe"
$JAR = "$JAVA_HOME\bin\jar.exe"

$STS_HOME = "D:\steam\steamapps\common\SlayTheSpire"
$WORKSHOP = "D:\steam\steamapps\workshop\content\646570"

$DESKTOP_JAR = "$STS_HOME\desktop-1.0.jar"
$MTS_JAR = "$WORKSHOP\1605060445\ModTheSpire.jar"
$BASEMOD_JAR = "$WORKSHOP\1605833019\BaseMod.jar"
$STSLIB_JAR = "$WORKSHOP\1609158507\StSLib.jar"

$SRC_DIR = Join-Path $PSScriptRoot "src\main\java"
$BUILD_DIR = Join-Path $PSScriptRoot "build\classes"
$OUTPUT_JAR = Join-Path $PSScriptRoot "build\DataRecorder-0.1.0.jar"

Write-Host "=== Building DataRecorder Mod ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "Creating build directory..."
if (-not (Test-Path $BUILD_DIR)) {
    New-Item -ItemType Directory -Path $BUILD_DIR -Force | Out-Null
}

Write-Host ""
Write-Host "Compiling Java sources..."
Write-Host "  - desktop-1.0.jar"
Write-Host "  - ModTheSpire.jar"
Write-Host "  - BaseMod.jar"
Write-Host "  - StSLib.jar"

$CP = "$DESKTOP_JAR;$MTS_JAR;$BASEMOD_JAR;$STSLIB_JAR"

$sourceFiles = Get-ChildItem -Path $SRC_DIR -Filter "*.java" -Recurse | ForEach-Object { $_.FullName }

Write-Host "Found $($sourceFiles.Count) source files"

$sourceListFile = Join-Path $env:TEMP "datarecorder_sources.txt"
$quotedSourceFiles = $sourceFiles | ForEach-Object { "`"$($_ -replace '\\', '/')`"" }

[System.IO.File]::WriteAllLines($sourceListFile, $quotedSourceFiles, (New-Object System.Text.UTF8Encoding($false)))

$process = New-Object System.Diagnostics.Process
$process.StartInfo.FileName = $JAVAC
$process.StartInfo.Arguments = "-encoding UTF-8 -source 1.8 -target 1.8 -cp `"$CP`" -d `"$BUILD_DIR`" `"@$sourceListFile`""
$process.StartInfo.UseShellExecute = $false
$process.StartInfo.RedirectStandardOutput = $true
$process.StartInfo.RedirectStandardError = $true
$process.StartInfo.WorkingDirectory = $PSScriptRoot

Write-Host "Running javac..."
$process.Start() | Out-Null
$stdout = $process.StandardOutput.ReadToEnd()
$stderr = $process.StandardError.ReadToEnd()
$process.WaitForExit()

if ($process.ExitCode -ne 0) {
    Write-Host ""
    Write-Host "=== Compilation FAILED ===" -ForegroundColor Red
    Write-Host $stdout
    Write-Host $stderr
    Remove-Item $sourceListFile -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "Compilation successful"

Write-Host ""
Write-Host "Creating JAR file..."

$manifestFile = Join-Path $PSScriptRoot "manifest.txt"
$tempDir = Join-Path $PSScriptRoot "build\temp"
$tempManifestDir = Join-Path $tempDir "META-INF"

if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempManifestDir -Force | Out-Null
Copy-Item (Join-Path $PSScriptRoot "ModTheSpire.json") $tempDir -Force
Copy-Item "$BUILD_DIR\*" $tempDir -Recurse -Force

$jarProcess = New-Object System.Diagnostics.Process
$jarProcess.StartInfo.FileName = $JAR
$jarProcess.StartInfo.Arguments = "cfm `"$OUTPUT_JAR`" `"$manifestFile`" -C `"$tempDir`" ."
$jarProcess.StartInfo.UseShellExecute = $false
$jarProcess.StartInfo.RedirectStandardOutput = $true
$jarProcess.StartInfo.RedirectStandardError = $true
$jarProcess.StartInfo.WorkingDirectory = $PSScriptRoot

$jarProcess.Start() | Out-Null
$jarStdout = $jarProcess.StandardOutput.ReadToEnd()
$jarStderr = $jarProcess.StandardError.ReadToEnd()
$jarProcess.WaitForExit()

if ($jarProcess.ExitCode -ne 0) {
    Write-Host ""
    Write-Host "=== JAR creation FAILED ===" -ForegroundColor Red
    Write-Host $jarStdout
    Write-Host $jarStderr
    Remove-Item $sourceListFile -ErrorAction SilentlyContinue
    Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    exit 1
}

Remove-Item $sourceListFile -ErrorAction SilentlyContinue
Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "=== Build SUCCESS ===" -ForegroundColor Green
Write-Host "Output: $OUTPUT_JAR"
Write-Host ""
Write-Host "To install, copy the JAR to your mods folder:"
Write-Host "  Copy-Item `"$OUTPUT_JAR`" `"$STS_HOME\mods\`"" -ForegroundColor Yellow
Write-Host ""

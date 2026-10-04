# Uninstall a release installed by install.ps1. User data and Pixi are kept.
# Usage: .\scripts\uninstall.ps1
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
    throw "LOCALAPPDATA must be set."
}

$DataRoot = Join-Path $env:LOCALAPPDATA "Meta-Coder"
$AppRoot = Join-Path $DataRoot "app"
$BinDir = Join-Path $DataRoot "bin"
$Launcher = Join-Path $BinDir "meta-coder.cmd"

if (Test-Path -LiteralPath $Launcher -PathType Leaf) {
    $Content = Get-Content -LiteralPath $Launcher -Raw
    if ($Content -and $Content.Contains("pixi run --manifest-path `"$AppRoot\")) {
        Remove-Item -LiteralPath $Launcher -Force
    } else {
        Write-Host "Keeping launcher not recognized as this release installation: $Launcher"
    }
}
if (Test-Path -LiteralPath $AppRoot) {
    Remove-Item -LiteralPath $AppRoot -Recurse -Force
}

# Remove only the installer's directory, preserving all other PATH entries.
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($null -ne $UserPath) {
    $NewPath = (($UserPath -split ";" | Where-Object {
        $_.Trim().Trim('"').TrimEnd('\', '/') -ine $BinDir
    }) -join ";")
    if ($NewPath -cne $UserPath) {
        [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
        Write-Host "Removed $BinDir from your user PATH. Open a new terminal for it to take effect."
    }
}
$env:Path = (($env:Path -split ";" | Where-Object {
    $_.Trim().Trim('"').TrimEnd('\', '/') -ine $BinDir
}) -join ";")

Write-Host "MetaCoder release installation removed."
Write-Host "Projects, settings, saved API keys, and Pixi have been preserved."
Write-Host "User data location: $DataRoot (or your META_CODER_HOME override)."

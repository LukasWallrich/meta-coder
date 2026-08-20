# MetaCoder installer (Windows) — todo.md step 20 / plan.md "A1. Shape,
# install, and local-only security". Mirrors install.sh's logic; see that
# file for the full rationale on each step. Downloads a versioned release
# bundle, installs its locked Pixi environment, and puts a `meta-coder`
# launcher on the current user's PATH (no admin rights required).
#
# Usage:
#   irm <release-base-url>/install.ps1 | iex
# Configuration (environment variables):
#   META_CODER_RELEASE_BASE_URL  Where release bundles + latest.txt live.
#                                 REQUIRED — see the error below for why this
#                                 has no built-in default yet.
#   META_CODER_VERSION           Install this exact version instead of latest.

$ErrorActionPreference = "Stop"

$AppName = "MetaCoder"
$DataDirName = "Meta-Coder"

# --- 1. Where do bundles come from? ---------------------------------------
$BaseUrl = $env:META_CODER_RELEASE_BASE_URL
if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
    Write-Error @"
META_CODER_RELEASE_BASE_URL is not set.
This installer has no release feed configured yet — set it to wherever
release bundles are published (see scripts/build_release.sh) and re-run, e.g.:
  `$env:META_CODER_RELEASE_BASE_URL = "https://github.com/<org>/<repo>/releases/latest/download"
  irm <that-url>/install.ps1 | iex
"@
    exit 1
}
$BaseUrl = $BaseUrl.TrimEnd("/")

# --- 2. Which version? ------------------------------------------------------
$Version = $env:META_CODER_VERSION
if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = (Invoke-WebRequest -UseBasicParsing "$BaseUrl/latest.txt").Content.Trim()
}
if ([string]::IsNullOrWhiteSpace($Version)) {
    Write-Error "Resolved an empty version string."
    exit 1
}
Write-Host "Installing $AppName $Version..."

# --- 3. Where does it go? (mirrors meta_coder/paths.py's app_data_dir) ----
$DataRoot = Join-Path $env:LOCALAPPDATA $DataDirName
$AppRoot = Join-Path $DataRoot "app"
$InstallDir = Join-Path $AppRoot $Version
$BinDir = Join-Path $DataRoot "bin"
$Launcher = Join-Path $BinDir "meta-coder.cmd"

# --- 4. Download + extract --------------------------------------------------
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$TmpTarball = Join-Path $env:TEMP "meta-coder-$Version.tar.gz"
Invoke-WebRequest -UseBasicParsing "$BaseUrl/meta-coder-$Version.tar.gz" -OutFile $TmpTarball
# tar.exe ships built in since Windows 10 1803 — no separate archive tool needed.
tar -xzf $TmpTarball -C $InstallDir --strip-components=1
Remove-Item $TmpTarball -Force

# --- 5. Bootstrap Pixi if this machine doesn't have it yet -----------------
if (-not (Get-Command pixi -ErrorAction SilentlyContinue)) {
    Write-Host "Pixi not found — installing it (see https://pixi.sh)..."
    Invoke-Expression (Invoke-WebRequest -UseBasicParsing "https://pixi.sh/install.ps1").Content
    $env:Path = "$env:LOCALAPPDATA\pixi\bin;$env:Path"
}
if (-not (Get-Command pixi -ErrorAction SilentlyContinue)) {
    Write-Error "Pixi installation did not put 'pixi' on PATH. Open a new terminal and re-run."
    exit 1
}

# --- 6. Materialize the locked environment ----------------------------------
# --locked (not --frozen) so a bundle whose pixi.lock doesn't actually match
# its own manifest fails loudly here rather than silently resolving fresh.
pixi install --manifest-path (Join-Path $InstallDir "pyproject.toml") --locked

# --- 7. Launcher shim --------------------------------------------------------
$ManifestPath = Join-Path $InstallDir "pyproject.toml"
Set-Content -Path $Launcher -Value "@echo off`r`npixi run --manifest-path `"$ManifestPath`" start %*"

# --- 8. Drop stale versions — "re-running the installer updates in place" --
Get-ChildItem -Path $AppRoot -Directory | Where-Object { $_.Name -ne $Version } | Remove-Item -Recurse -Force

# --- 9. Make sure $BinDir is on this user's PATH ----------------------------
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not ($UserPath -split ";" -contains $BinDir)) {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$BinDir", "User")
    Write-Host "Added $BinDir to your user PATH — open a new terminal for it to take effect."
}

Write-Host ""
Write-Host "$AppName $Version installed."
Write-Host "Run it with: meta-coder"

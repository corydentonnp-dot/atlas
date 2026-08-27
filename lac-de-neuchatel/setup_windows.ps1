<#
    setup_windows.ps1 -- get this machine ready to cut.

    From the lac-de-neuchatel folder:

        powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1

    It will:
      1. find Python
      2. repair the terrain mesh if that has not been done
      3. install the CAM script into Fusion's Scripts folder
      4. install the FusionBridge add-in into Fusion's AddIns folder
      5. run preflight.py

    Safe to run more than once. Existing files are replaced, except the
    bridge token, which is preserved so you do not have to re-pair the CLI.
#>

$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $MyInvocation.MyCommand.Path

function Say($text)  { Write-Host $text }
function Good($text) { Write-Host "  ok    $text" -ForegroundColor Green }
function Warn($text) { Write-Host "  warn  $text" -ForegroundColor Yellow }
function Bad($text)  { Write-Host "  FAIL  $text" -ForegroundColor Red }

Say ""
Say "Lac de Neuchatel -- setup"
Say "project: $project"
Say ""

# --- 1. python ---------------------------------------------------------------
Say "python"
$python = $null
foreach ($candidate in @("python", "python3", "py")) {
    try {
        $version = & $candidate --version 2>&1
        if ($LASTEXITCODE -eq 0) { $python = $candidate; Good "$candidate -- $version"; break }
    } catch { }
}
if (-not $python) {
    Bad "no Python found on PATH"
    Say ""
    Say "Install Python 3 from https://python.org/downloads and tick"
    Say "'Add python.exe to PATH' during setup, then run this again."
    exit 1
}

# --- 2. mesh repair ----------------------------------------------------------
Say ""
Say "terrain mesh"
$broken = Join-Path $project "cam\01-terrain.stl"
$fixed  = Join-Path $project "cam\01-terrain-FIXED.stl"

if (-not (Test-Path $broken)) {
    Bad "cam\01-terrain.stl is missing -- restore it from the repository"
    exit 1
}
if (Test-Path $fixed) {
    Good "repaired mesh already present"
} else {
    Say "  repairing (the supplied mesh has no usable surface)..."
    & $python (Join-Path $project "repair_terrain_stl.py") $broken $fixed
    if ($LASTEXITCODE -ne 0) { Bad "mesh repair failed"; exit 1 }
    Good "repaired mesh written"
}

# --- 3 & 4. install into Fusion ---------------------------------------------
Say ""
Say "fusion"
$api = Join-Path $env:APPDATA "Autodesk\Autodesk Fusion 360\API"
if (-not (Test-Path $api)) {
    Warn "Fusion's API folder does not exist yet:"
    Say  "        $api"
    Say  "        Install Fusion 360 and launch it once, then run this again."
    Say  "        Everything else above is done."
    exit 1
}
Good "found Fusion API folder"

# CAM script
$scriptDir = Join-Path $api "Scripts\LacDeNeuchatel_CAM"
New-Item -ItemType Directory -Force -Path $scriptDir | Out-Null
Copy-Item (Join-Path $project "LacDeNeuchatel_CAM.py") $scriptDir -Force
Good "CAM script installed"

# Bridge add-in. Keep any existing token so the CLI stays paired.
$addinDir = Join-Path $api "AddIns\FusionBridge"
$tokenPath = Join-Path $addinDir "bridge-token.txt"
$savedToken = $null
if (Test-Path $tokenPath) { $savedToken = Get-Content $tokenPath -Raw }

New-Item -ItemType Directory -Force -Path $addinDir | Out-Null
Copy-Item (Join-Path $project "bridge\FusionBridge\*") $addinDir -Recurse -Force

if ($savedToken) {
    Set-Content -Path $tokenPath -Value $savedToken -NoNewline
    Good "FusionBridge add-in updated (existing token kept)"
} else {
    Good "FusionBridge add-in installed"
}

# --- 5. preflight ------------------------------------------------------------
Say ""
& $python (Join-Path $project "preflight.py")

Say ""
Say "Next, in Fusion:"
Say "  1. open or create a design document"
Say "  2. Utilities > Add-Ins > Add-Ins tab > FusionBridge > Run"
Say "     (tick 'Run on Startup' to skip this next time)"
Say "  3. back here:  cd bridge ; $python fusion_cli.py ping"
Say ""

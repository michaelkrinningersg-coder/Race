<#
.SYNOPSIS
    Lokaler Build fuer das Repo michaelkrinningersg-coder/Race (Python/PySide6).

.DESCRIPTION
    Holt den Branch von GitHub, richtet ein venv ein, installiert die
    Abhaengigkeiten, laesst die Testsuite laufen und baut die .exe mit
    PyInstaller. Optional Upload als GitHub-Release-Asset (benoetigt "gh").

.PARAMETER Branch
    Branch, der gebaut werden soll. Default: claude/admiring-hawking-2fme35

.PARAMETER NoPull     Kein fetch/pull - baut exakt den lokalen Stand.
.PARAMETER Reset      Setzt den Branch hart auf origin/<Branch> (lokale Aenderungen weg).
.PARAMETER SkipTests  Testsuite ueberspringen.
.PARAMETER Clean      venv, build/ und dist/ vorher loeschen.
.PARAMETER Force      Baut auch bei nicht sauberem Arbeitsverzeichnis.
.PARAMETER Run        Startet die fertige .exe nach dem Build.
.PARAMETER Publish    Laedt die .exe als GitHub-Release-Asset hoch.
.PARAMETER Tag        Tag fuer das Release. Default: build-<branch>-<yyyyMMdd-HHmm>.
.PARAMETER Entry      Einstiegsskript. Ohne Angabe wird automatisch gesucht.
.PARAMETER AppName    Name der erzeugten EXE. Default: Race

.EXAMPLE
    .\build.ps1
.EXAMPLE
    .\build.ps1 -Clean -Run
.EXAMPLE
    .\build.ps1 -Publish -Tag v0.3.0

.NOTES
    Nach dem Download einmal:  Unblock-File .\build.ps1
    Oder dauerhaft ueber:      powershell -ExecutionPolicy Bypass -File .\build.ps1
#>

[CmdletBinding()]
param(
    [string]$Branch = "claude/admiring-hawking-2fme35",
    [switch]$NoPull,
    [switch]$Reset,
    [switch]$SkipTests,
    [switch]$Clean,
    [switch]$Force,
    [switch]$Run,
    [switch]$Publish,
    [string]$Tag = "",
    [string]$Entry = "",
    [string]$AppName = "Race"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ExpectedRepo = "michaelkrinningersg-coder/Race"
$RepoUrl      = "https://github.com/$ExpectedRepo.git"

# ---------------------------------------------------------------- Hilfsfunktionen

function Write-Step { param([string]$Text)
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}
function Write-Info { param([string]$Text)
    Write-Host "    $Text" -ForegroundColor DarkGray
}

# Argumente werden bewusst als ARRAY uebergeben (zweiter Positionsparameter),
# nicht als lose Tokens. Sonst versucht PowerShell, Dinge wie "-e" oder "-v"
# an die automatischen Parameter der Funktion zu binden (-ErrorAction, ...)
# und bricht mit "Parametername ist nicht eindeutig" ab.
#
#   richtig: Invoke-Native git @("fetch","origin")
#   falsch : Invoke-Native git fetch origin

function Invoke-Native {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)][string]$File,
        [Parameter(Position = 1)][string[]]$Arguments = @()
    )
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"   # git/gh schreiben Status auf stderr
    try {
        & $File @Arguments
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    if ($code -ne 0) {
        throw "'$File $($Arguments -join ' ')' fehlgeschlagen (Exit-Code $code)."
    }
}

function Invoke-Probe {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)][string]$File,
        [Parameter(Position = 1)][string[]]$Arguments = @()
    )
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out  = & $File @Arguments 2>$null
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    $text = if ($null -eq $out) { "" } else { ($out | Out-String).Trim() }
    return [pscustomobject]@{ Code = $code; Text = $text }
}

function Test-Command { param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

$startTime = Get-Date

# ---------------------------------------------------------------- Voraussetzungen

Write-Step "Voraussetzungen pruefen"

foreach ($cmd in @("git", "python")) {
    if (-not (Test-Command $cmd)) { throw "'$cmd' ist nicht im PATH." }
}
Write-Info "git    : $((Invoke-Probe git @('--version')).Text)"
Write-Info "python : $((Invoke-Probe python @('--version')).Text)"

if ($Publish -and -not (Test-Command "gh")) {
    throw "-Publish benoetigt die GitHub CLI 'gh' (winget install GitHub.cli), danach einmalig 'gh auth login'."
}

# ---------------------------------------------------------------- Repo-Wurzel

$probe = Invoke-Probe git @("-C", $PSScriptRoot, "rev-parse", "--show-toplevel")
if ($probe.Code -ne 0 -or [string]::IsNullOrWhiteSpace($probe.Text)) {
    Write-Host ""
    Write-Host "In '$PSScriptRoot' liegt kein Git-Repository." -ForegroundColor Red
    Write-Host "Das Skript gehoert in die Wurzel des geklonten Race-Repos (dort, wo .git liegt)." -ForegroundColor Red
    Write-Host ""
    Write-Host "Falls noch nicht geklont:" -ForegroundColor Yellow
    Write-Host "    git clone $RepoUrl" -ForegroundColor Yellow
    throw "Kein Git-Repository gefunden."
}
$repoRoot = $probe.Text
Set-Location $repoRoot
Write-Info "Repo   : $repoRoot"

$origin = (Invoke-Probe git @("remote", "get-url", "origin")).Text
if ($origin -and $origin -notmatch "Race(\.git)?/?$") {
    Write-Warning "origin ist '$origin' - erwartet wurde $ExpectedRepo."
}

# ---------------------------------------------------------------- Git-Stand herstellen

Write-Step "Git-Stand herstellen"

# --untracked-files=no: neue, nicht versionierte Dateien (build.ps1, .venv, dist)
# stoeren weder Checkout noch Pull und gelten hier nicht als "unsauber".
$dirty = (Invoke-Probe git @("status", "--porcelain", "--untracked-files=no")).Text
if ($dirty -and -not ($Force -or $Reset)) {
    Write-Host $dirty
    throw "Arbeitsverzeichnis nicht sauber. Erst committen/stashen, oder -Force (lokalen Stand bauen) bzw. -Reset (verwerfen)."
}

if (-not $NoPull) {
    Invoke-Native git @("fetch", "origin", "--prune", "--tags")
}

if ($dirty -and $Force) {
    Write-Warning "Arbeitsverzeichnis nicht sauber - es wird der lokale Stand gebaut, kein Branch-Wechsel."
} else {
    $hasLocal  = ((Invoke-Probe git @("rev-parse", "--verify", "--quiet", "refs/heads/$Branch")).Code -eq 0)
    $hasRemote = ((Invoke-Probe git @("rev-parse", "--verify", "--quiet", "refs/remotes/origin/$Branch")).Code -eq 0)

    if ($hasLocal) {
        Invoke-Native git @("checkout", $Branch)
    } elseif ($hasRemote) {
        Write-Info "lokaler Branch fehlt - wird von origin/$Branch angelegt"
        Invoke-Native git @("checkout", "-b", $Branch, "--track", "origin/$Branch")
    } else {
        throw "Branch '$Branch' gibt es weder lokal noch auf origin. Mit -Branch <name> korrigieren."
    }

    if ($Reset -and $hasRemote) {
        Write-Warning "Reset auf origin/$Branch - lokale Aenderungen werden verworfen."
        Invoke-Native git @("reset", "--hard", "origin/$Branch")
        Invoke-Native git @("clean", "-fd")
    } elseif (-not $NoPull) {
        if ((Invoke-Probe git @("rev-parse", "--abbrev-ref", "$Branch@{upstream}")).Code -eq 0) {
            $pull = Invoke-Probe git @("pull", "--ff-only")
            if ($pull.Code -ne 0) {
                throw "git pull --ff-only fehlgeschlagen - der Branch wurde vermutlich force-gepusht. Noch einmal mit -Reset ausfuehren."
            }
            if ($pull.Text) { Write-Info $pull.Text }
        } else {
            Write-Warning "Branch '$Branch' hat keinen Upstream - Pull uebersprungen."
        }
    }
}

$currentBranch = (Invoke-Probe git @("rev-parse", "--abbrev-ref", "HEAD")).Text
$commit        = (Invoke-Probe git @("rev-parse", "HEAD")).Text
$commitShort   = (Invoke-Probe git @("rev-parse", "--short", "HEAD")).Text
$commitSubject = (Invoke-Probe git @("log", "-1", "--pretty=%s")).Text
Write-Info "Branch : $currentBranch"
Write-Info "Commit : $commitShort  $commitSubject"

# ---------------------------------------------------------------- Aufraeumen

if ($Clean) {
    Write-Step "Aufraeumen"
    foreach ($dir in @(".venv", "build", "dist")) {
        if (Test-Path $dir) {
            Remove-Item $dir -Recurse -Force
            Write-Info "geloescht: $dir"
        }
    }
}

# ---------------------------------------------------------------- venv + Abhaengigkeiten

Write-Step "Virtuelle Umgebung vorbereiten"

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Invoke-Native python @("-m", "venv", ".venv")
    Write-Info "venv neu angelegt"
} else {
    Write-Info "venv vorhanden"
}

Invoke-Native $venvPython @("-m", "pip", "install", "--upgrade", "pip", "--quiet")

$installed = $false
foreach ($req in @("requirements.txt", "requirements-dev.txt")) {
    if (Test-Path $req) {
        Write-Info "installiere $req"
        Invoke-Native $venvPython @("-m", "pip", "install", "-r", $req, "--quiet")
        $installed = $true
    }
}
if (-not $installed -and (Test-Path "pyproject.toml")) {
    Write-Info "installiere Projekt aus pyproject.toml"
    if ((Invoke-Probe $venvPython @("-m", "pip", "install", "-e", ".[dev]", "--quiet")).Code -ne 0) {
        Invoke-Native $venvPython @("-m", "pip", "install", "-e", ".", "--quiet")
    }
    $installed = $true
}
if (-not $installed) {
    Write-Warning "Weder requirements.txt noch pyproject.toml gefunden - installiere nur PySide6 und pytest."
    Invoke-Native $venvPython @("-m", "pip", "install", "PySide6", "pytest", "--quiet")
}

Invoke-Native $venvPython @("-m", "pip", "install", "pyinstaller", "--quiet")

# ---------------------------------------------------------------- Tests

if (-not $SkipTests) {
    Write-Step "Testsuite"
    $env:QT_QPA_PLATFORM = "offscreen"   # Qt soll beim Testen keine Fenster oeffnen
    try {
        Invoke-Native $venvPython @("-m", "pytest", "-q")
    } finally {
        Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    }
} else {
    Write-Warning "Tests uebersprungen (-SkipTests)."
}

# ---------------------------------------------------------------- Build

Write-Step "PyInstaller-Build"

$specFile = "$AppName.spec"
$useSpec  = Test-Path $specFile

if (-not $useSpec -and -not $Entry) {
    $candidates = @(
        "main.py", "run.py", "app.py",
        "src\main.py",
        "race\__main__.py", "race\main.py",
        "src\race\__main__.py", "src\race\main.py"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $Entry = $c; break }
    }
    if (-not $Entry) {
        throw "Kein Einstiegsskript gefunden. Bitte mit -Entry <pfad\zur\datei.py> angeben."
    }
}

$piArgs = @("-m", "PyInstaller", "--noconfirm")
if ($Clean) { $piArgs += "--clean" }

if ($useSpec) {
    Write-Info "verwende $specFile"
    $piArgs += $specFile
} else {
    Write-Info "Einstiegsskript: $Entry"
    $piArgs += @("--onefile", "--windowed", "--name", $AppName)
    foreach ($d in @("assets", "data", "resources")) {
        if (Test-Path $d) { $piArgs += @("--add-data", "$d;$d") }
    }
    foreach ($ico in @("assets\icon.ico", "icon.ico")) {
        if (Test-Path $ico) { $piArgs += @("--icon", $ico); break }
    }
    $piArgs += $Entry
}

Invoke-Native $venvPython $piArgs

$exePath = Join-Path $repoRoot "dist\$AppName.exe"
if (-not (Test-Path $exePath)) {
    throw "Erwartete Datei nicht gefunden: $exePath"
}
$sizeMb = [math]::Round((Get-Item $exePath).Length / 1MB, 1)

$infoPath = Join-Path $repoRoot "dist\build-info.txt"
@(
    "App       : $AppName"
    "Repo      : $ExpectedRepo"
    "Branch    : $currentBranch"
    "Commit    : $commit"
    "Betreff   : $commitSubject"
    "Gebaut am : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    "Rechner   : $env:COMPUTERNAME"
    "Python    : $((Invoke-Probe $venvPython @('--version')).Text)"
) | Set-Content -Path $infoPath -Encoding UTF8

Write-Info "Artefakt: $exePath ($sizeMb MB)"

# ---------------------------------------------------------------- Optional: GitHub-Release

if ($Publish) {
    Write-Step "Upload zu GitHub"

    if (-not $Tag) {
        $safeBranch = $currentBranch -replace "[^a-zA-Z0-9\.\-]", "-"
        $Tag = "build-$safeBranch-$(Get-Date -Format 'yyyyMMdd-HHmm')"
    }

    if ((Invoke-Probe gh @("release", "view", $Tag)).Code -eq 0) {
        Write-Info "Release '$Tag' existiert - Assets werden ersetzt"
        Invoke-Native gh @("release", "upload", $Tag, $exePath, $infoPath, "--clobber")
    } else {
        Write-Info "Release '$Tag' wird angelegt"
        Invoke-Native gh @(
            "release", "create", $Tag, $exePath, $infoPath,
            "--title", "$AppName $Tag",
            "--notes", "Lokaler Build von $currentBranch ($commitShort): $commitSubject",
            "--target", $commit
        )
    }
}

# ---------------------------------------------------------------- Abschluss

$duration = (Get-Date) - $startTime
Write-Host ""
Write-Host "Fertig in $([math]::Round($duration.TotalSeconds)) s - $AppName ($currentBranch @ $commitShort)" -ForegroundColor Green
Write-Host "EXE: $exePath" -ForegroundColor Green

if ($Run) {
    Write-Step "Starte $AppName"
    Start-Process -FilePath $exePath -WorkingDirectory (Split-Path $exePath)
}

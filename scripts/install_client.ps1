$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RootDir

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv n'est pas installe. Installez-le depuis https://docs.astral.sh/uv/ puis relancez ce script."
}

Write-Host "Installation de Lead Generator dans $RootDir"
uv sync --project plugins/leadgenerator --frozen
if ($LASTEXITCODE -ne 0) { throw "L'installation Python a echoue." }

uv run --project plugins/leadgenerator leadgenerator-migrate-profiles
if ($LASTEXITCODE -ne 0) { throw "La migration des profils prives a echoue." }

uv run --project plugins/leadgenerator playwright install chromium
if ($LASTEXITCODE -ne 0) { throw "L'installation de Chromium a echoue." }

if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    throw "Codex n'est pas installe. Installez-le depuis https://developers.openai.com/codex/ puis relancez ce script."
}
$CodexBin = (Get-Command codex).Source
& $CodexBin login status *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Connexion ChatGPT requise pour utiliser le modele OpenAI."
    & $CodexBin login --device-auth
    if ($LASTEXITCODE -ne 0) { throw "La connexion ChatGPT a echoue." }
}

$MarketplaceName = "leadgenerator-local"
$PluginName = "leadgenerator@$MarketplaceName"
$PluginManifest = Get-Content -LiteralPath (Join-Path $RootDir "plugins/leadgenerator/.codex-plugin/plugin.json") -Raw | ConvertFrom-Json
$PluginVersion = $PluginManifest.version
$CodexHomeDir = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
$CacheRoot = Join-Path $CodexHomeDir "plugins/cache/$MarketplaceName/leadgenerator"
$InstalledPluginRoot = Join-Path $CacheRoot $PluginVersion
$RunningOnWindows = [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT
$PreviousCacheVersions = @()
if (Test-Path -LiteralPath $CacheRoot -PathType Container) {
    $PreviousCacheVersions = @(
        Get-ChildItem -LiteralPath $CacheRoot -Force |
            Where-Object { $_.Name -match '^\d+\.\d+\.\d+([+-][A-Za-z0-9._-]+)?$' } |
            ForEach-Object { $_.Name }
    )
}

# Older installers copied the generic Lead Generator skills directly into
# ~/.codex/skills. Archive those stale duplicates without touching offer-specific
# skills or the local user profile.
$LegacySkills = @(
    "leadgenerator",
    "lead-company-search",
    "lead-company-research",
    "lead-company-visuals",
    "lead-contact-discovery",
    "lead-contact-enrichment",
    "lead-hubspot-sync"
)
$LegacyBackup = $null
foreach ($Skill in $LegacySkills) {
    $SkillPath = Join-Path $HOME ".codex/skills/$Skill"
    if (Test-Path -LiteralPath $SkillPath -PathType Container) {
        if (-not $LegacyBackup) {
            $Timestamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
            $LegacyBackup = Join-Path $HOME ".codex/leadgenerator/legacy-skill-backups/$Timestamp"
            New-Item -ItemType Directory -Path $LegacyBackup -Force | Out-Null
        }
        Move-Item -LiteralPath $SkillPath -Destination (Join-Path $LegacyBackup $Skill)
    }
}
if ($LegacyBackup) {
    Write-Host "Anciens skills generiques archives dans $LegacyBackup"
}

# Codex copies local marketplace plugins into its cache. A copied Python virtual
# environment contains absolute links and cannot be reused from the cache, so
# temporarily move it outside the plugin snapshot while Codex installs the plugin.
$PluginVenv = Join-Path $RootDir "plugins/leadgenerator/.venv"
$VenvStashDir = $null
$VenvStash = $null
if (Test-Path -LiteralPath $PluginVenv -PathType Container) {
    $VenvStashDir = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString())
    New-Item -ItemType Directory -Path $VenvStashDir | Out-Null
    $VenvStash = Join-Path $VenvStashDir ".venv"
    Move-Item -LiteralPath $PluginVenv -Destination $VenvStash
}

try {
    $MarketplaceList = (& $CodexBin plugin marketplace list | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "La lecture des marketplaces Codex a echoue." }
    if (-not $MarketplaceList.Contains($RootDir)) {
        & $CodexBin plugin marketplace add $RootDir
        if ($LASTEXITCODE -ne 0) { throw "L'ajout du marketplace Lead Generator a echoue." }
    }
    & $CodexBin plugin add $PluginName
    if ($LASTEXITCODE -ne 0) { throw "L'installation du plugin Lead Generator a echoue." }

    # Build the cached environment explicitly. A development virtualenv is not
    # portable once copied into the Codex cache.
    if (-not (Test-Path -LiteralPath $InstalledPluginRoot -PathType Container)) {
        throw "Le cache installe est introuvable dans $InstalledPluginRoot."
    }
    $CachedPython = if ($RunningOnWindows) {
        Join-Path $InstalledPluginRoot ".venv/Scripts/python.exe"
    }
    else {
        Join-Path $InstalledPluginRoot ".venv/bin/python"
    }
    $CachedVenv = Join-Path $InstalledPluginRoot ".venv"
    if ((Test-Path -LiteralPath $CachedVenv -PathType Container) -and
        -not (Test-Path -LiteralPath $CachedPython -PathType Leaf)) {
        uv venv --clear --python 3.13 $CachedVenv
        if ($LASTEXITCODE -ne 0) { throw "La reconstruction de l'environnement Python du cache a echoue." }
    }
    uv sync --project $InstalledPluginRoot --frozen
    if ($LASTEXITCODE -ne 0) { throw "L'installation Python du cache Lead Generator a echoue." }
    uv run --project $InstalledPluginRoot --frozen python -c "import leadgenerator.mcp.server"
    if ($LASTEXITCODE -ne 0) { throw "Le serveur MCP Lead Generator installe ne demarre pas." }

    # Keep paths retained by already-open Codex tasks resolvable after upgrades.
    foreach ($CachedVersion in $PreviousCacheVersions) {
        $CompatibilityPath = Join-Path $CacheRoot $CachedVersion
        if ($CachedVersion -ne $PluginVersion -and -not (Test-Path -LiteralPath $CompatibilityPath)) {
            if ($RunningOnWindows) {
                New-Item -ItemType Junction -Path $CompatibilityPath -Target $InstalledPluginRoot | Out-Null
            }
            else {
                New-Item -ItemType SymbolicLink -Path $CompatibilityPath -Target $InstalledPluginRoot | Out-Null
            }
        }
    }
}
finally {
    if ($VenvStash -and (Test-Path -LiteralPath $VenvStash -PathType Container)) {
        Move-Item -LiteralPath $VenvStash -Destination $PluginVenv
        Remove-Item -LiteralPath $VenvStashDir -Force
    }
}

Write-Host ""
Write-Host "Installation terminee. Le plugin Lead Generator et ses skills sont installes."
Write-Host "Ouvrez une nouvelle conversation Codex, puis demandez :"
Write-Host "  Trouvez-moi des leads dans l'industrie."
Write-Host "Sans objectif configure, l'agent doit d'abord demander votre offre et votre cible."
Write-Host "Apres creation de l'objectif, il lancera la recherche puis l'interface MCP."

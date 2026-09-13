[CmdletBinding()]
param(
    [ValidateSet("codex", "claude-code", "claude-desktop")]
    [string]$HostTarget = "codex"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$MinimumCodexVersion = [Version]"0.153.4"
$UvInstallerUrl = "https://astral.sh/uv/install.ps1"
$CodexInstallerUrl = "https://chatgpt.com/codex/install.ps1"
$CurrentStep = "initialisation"
$Failure = $null
$BootstrapVenv = $null
$VenvStashDir = $null
$VenvStash = $null
$PreviousUvProjectEnvironment = $env:UV_PROJECT_ENVIRONMENT

function Start-InstallStep {
    param([string]$Message)

    $script:CurrentStep = $Message
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-NativeSuccess {
    param([string]$Message)

    if ($LASTEXITCODE -ne 0) {
        throw "$Message (code $LASTEXITCODE)."
    }
}

function Refresh-ProcessPath {
    $MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $Parts = @($env:Path, $MachinePath, $UserPath) | Where-Object { $_ }
    $env:Path = $Parts -join [IO.Path]::PathSeparator
}

function Find-Executable {
    param(
        [string]$Name,
        [string[]]$Candidates = @()
    )

    $Command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($Command -and $Command.Source) {
        return $Command.Source
    }
    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $Candidate).Path
        }
    }
    return $null
}

function Invoke-OfficialInstaller {
    param(
        [string]$Name,
        [string]$Uri
    )

    $DownloadPath = Join-Path ([IO.Path]::GetTempPath()) (
        "$($Name.ToLowerInvariant())-install-$([Guid]::NewGuid().ToString('N')).ps1"
    )
    try {
        Write-Host "$Name est absent ou trop ancien ; telechargement de l'installateur officiel."
        Invoke-WebRequest -Uri $Uri -OutFile $DownloadPath -UseBasicParsing
        if (-not (Test-Path -LiteralPath $DownloadPath -PathType Leaf)) {
            throw "Le script officiel de $Name n'a pas ete telecharge."
        }
        $PowerShellHost = (Get-Process -Id $PID).Path
        & $PowerShellHost -NoProfile -ExecutionPolicy Bypass -File $DownloadPath
        Assert-NativeSuccess "L'installation officielle de $Name a echoue"
        Refresh-ProcessPath
    }
    finally {
        Remove-Item -LiteralPath $DownloadPath -Force -ErrorAction SilentlyContinue
    }
}

function Get-VersionFromCommand {
    param([string]$CommandPath)

    $Output = (& $CommandPath --version | Out-String)
    Assert-NativeSuccess "La lecture de version a echoue pour $CommandPath"
    if ($Output -notmatch '(\d+\.\d+\.\d+)') {
        throw "La version n'a pas pu etre determinee : $Output"
    }
    return [Version]$Matches[1]
}

function Write-InstalledMcpConfig {
    param(
        [string]$PluginRoot,
        [string]$UvCommand
    )

    $ConfigPath = Join-Path $PluginRoot ".mcp.json"
    $Config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $Config.mcpServers.leadgenerator.command = $UvCommand
    $Json = $Config | ConvertTo-Json -Depth 20
    $Utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($ConfigPath, $Json, $Utf8WithoutBom)
}

$RunningOnWindows = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
if (-not $RunningOnWindows) {
    throw "Ce script est reserve a Windows. Utilisez scripts/install_client.sh sur macOS ou Linux."
}

# Windows PowerShell 5 can otherwise negotiate an obsolete TLS version.
[Net.ServicePointManager]::SecurityProtocol = (
    [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
)

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RootDir

$UvCandidates = @(
    (Join-Path $HOME ".local\bin\uv.exe"),
    (Join-Path $HOME ".cargo\bin\uv.exe")
)
$CodexCandidates = @(
    (Join-Path $HOME ".local\bin\codex.exe"),
    (Join-Path $HOME ".cargo\bin\codex.exe")
)
if ($env:LOCALAPPDATA) {
    $UvCandidates += Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\uv.exe"
    $CodexCandidates += Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\codex.exe"
}
if ($env:APPDATA) {
    $CodexCandidates += Join-Path $env:APPDATA "npm\codex.cmd"
    $CodexCandidates += Join-Path $env:APPDATA "npm\codex.exe"
}

try {
    Start-InstallStep "Verification de uv"
    $UvBin = Find-Executable -Name "uv" -Candidates $UvCandidates
    $UvReady = $false
    if ($UvBin) {
        try {
            & $UvBin --version
            $UvReady = $LASTEXITCODE -eq 0
        }
        catch {
            Write-Warning "L'installation uv detectee ne demarre pas : $($_.Exception.Message)"
        }
    }
    if (-not $UvReady) {
        Invoke-OfficialInstaller -Name "uv" -Uri $UvInstallerUrl
        $StandaloneUv = Join-Path $HOME ".local\bin\uv.exe"
        if (Test-Path -LiteralPath $StandaloneUv -PathType Leaf) {
            $UvBin = (Resolve-Path -LiteralPath $StandaloneUv).Path
        }
        else {
            $UvBin = Find-Executable -Name "uv" -Candidates $UvCandidates
        }
    }
    if (-not $UvBin) {
        throw "uv reste introuvable apres son installation officielle."
    }
    $env:Path = "$(Split-Path $UvBin -Parent)$([IO.Path]::PathSeparator)$env:Path"
    & $UvBin --version
    Assert-NativeSuccess "uv ne demarre pas"

    if ($HostTarget -ne "codex") {
        Start-InstallStep "Installation du runtime Claude"
        & $UvBin sync --project plugins/leadgenerator --frozen --python 3.13
        Assert-NativeSuccess "L'installation Python a echoue"
        $WorkspaceOutput = (& $UvBin run --project plugins/leadgenerator --frozen python `
            scripts/configure_workspace.py --code-root $RootDir | Out-String).Trim()
        Assert-NativeSuccess "La preparation du dossier prive a echoue"
        $env:LEADGENERATOR_HOME = ($WorkspaceOutput | ConvertFrom-Json).private_directory
        $env:LEADGENERATOR_DATABASE_URL = ""
        $env:LEADGENERATOR_HOST = "claude"
        & $UvBin run --project plugins/leadgenerator --frozen playwright install chromium
        Assert-NativeSuccess "L'installation de Chromium a echoue"
        & $UvBin run --project plugins/leadgenerator --frozen python scripts/verify_workspace.py
        Assert-NativeSuccess "La verification du premier objectif a echoue"
        & $UvBin run --project plugins/leadgenerator --frozen python scripts/install_claude.py `
            --code-root $RootDir --uv-command $UvBin --host $HostTarget
        Assert-NativeSuccess "La configuration de Claude a echoue"
        Write-Host "Installation terminee. Quittez completement Claude puis relancez-le dans ce projet."
        Write-Host "Le premier usage d'un dossier neuf demande de creer un objectif."
        return
    }

    Start-InstallStep "Verification de Codex"
    $CodexBin = Find-Executable -Name "codex" -Candidates $CodexCandidates
    $CodexVersion = $null
    if ($CodexBin) {
        try {
            $CodexVersion = Get-VersionFromCommand -CommandPath $CodexBin
        }
        catch {
            Write-Warning "L'installation Codex detectee ne demarre pas : $($_.Exception.Message)"
        }
    }
    if (-not $CodexVersion -or $CodexVersion -lt $MinimumCodexVersion) {
        Invoke-OfficialInstaller -Name "Codex" -Uri $CodexInstallerUrl
        # Prefer the standalone binary just installed over an older npm shim.
        $StandaloneCodex = Join-Path $HOME ".local\bin\codex.exe"
        if (Test-Path -LiteralPath $StandaloneCodex -PathType Leaf) {
            $CodexBin = (Resolve-Path -LiteralPath $StandaloneCodex).Path
        }
        else {
            $CodexBin = Find-Executable -Name "codex" -Candidates $CodexCandidates
        }
        if (-not $CodexBin) {
            throw "Codex reste introuvable apres son installation officielle."
        }
        $CodexVersion = Get-VersionFromCommand -CommandPath $CodexBin
    }
    if ($CodexVersion -lt $MinimumCodexVersion) {
        throw "Codex $MinimumCodexVersion ou plus recent est requis ; version detectee : $CodexVersion."
    }
    Write-Host "Codex $CodexVersion detecte dans $CodexBin"

    Start-InstallStep "Preparation de l'environnement Python 3.13"
    Write-Host "Installation de Lead Generator dans $RootDir"

    # A project virtual environment is not portable when Codex copies the plugin
    # into its cache. Build in a temporary location so a fresh client checkout
    # never ships a broken .venv into the installed plugin.
    $PluginVenv = Join-Path $RootDir "plugins/leadgenerator/.venv"
    if (Test-Path -LiteralPath $PluginVenv -PathType Container) {
        $VenvStashDir = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Path $VenvStashDir | Out-Null
        $VenvStash = Join-Path $VenvStashDir ".venv"
        Move-Item -LiteralPath $PluginVenv -Destination $VenvStash
    }
    $BootstrapVenv = Join-Path ([IO.Path]::GetTempPath()) (
        "leadgenerator-bootstrap-$([Guid]::NewGuid().ToString('N'))"
    )
    $env:UV_PROJECT_ENVIRONMENT = $BootstrapVenv
    & $UvBin sync --project plugins/leadgenerator --frozen --python 3.13
    Assert-NativeSuccess "L'installation Python a echoue"

    Start-InstallStep "Preparation du dossier prive de cette installation"
    $WorkspaceOutput = (& $UvBin run --project plugins/leadgenerator --frozen python `
        scripts/configure_workspace.py --code-root $RootDir | Out-String).Trim()
    Assert-NativeSuccess "La preparation du dossier prive a echoue"
    $env:LEADGENERATOR_HOME = ($WorkspaceOutput | ConvertFrom-Json).private_directory
    $env:LEADGENERATOR_DATABASE_URL = ""
    Write-Host "Donnees privees : $env:LEADGENERATOR_HOME"
    Write-Host "Aucun ancien objectif ou profil global n'est importe automatiquement."
    & $UvBin run --project plugins/leadgenerator --frozen python `
        scripts/configure_workspace.py --code-root $RootDir
    Assert-NativeSuccess "La verification du dossier prive a echoue"

    Start-InstallStep "Installation du navigateur Chromium"
    & $UvBin run --project plugins/leadgenerator --frozen playwright install chromium
    Assert-NativeSuccess "L'installation de Chromium a echoue"

    # Local MCP installation performs no model call. Authentication belongs to
    # the host application and must not interrupt dependency installation.

    Start-InstallStep "Installation du plugin Codex"
    $MarketplaceName = "leadgenerator-local"
    $PluginName = "leadgenerator@$MarketplaceName"
    $PluginManifest = Get-Content -LiteralPath (
        Join-Path $RootDir "plugins/leadgenerator/.codex-plugin/plugin.json"
    ) -Raw -Encoding UTF8 | ConvertFrom-Json
    $PluginVersion = $PluginManifest.version
    $CodexHomeDir = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
    $CacheRoot = Join-Path $CodexHomeDir "plugins/cache/$MarketplaceName/leadgenerator"
    $InstalledPluginRoot = Join-Path $CacheRoot $PluginVersion
    $PreviousCacheVersions = @()
    if (Test-Path -LiteralPath $CacheRoot -PathType Container) {
        $PreviousCacheVersions = @(
            Get-ChildItem -LiteralPath $CacheRoot -Force |
                Where-Object { $_.Name -match '^\d+\.\d+\.\d+([+-][A-Za-z0-9._-]+)?$' } |
                ForEach-Object { $_.Name }
        )
    }

    # Archive only obsolete generic copies. Client-specific skills and private
    # profiles are deliberately left untouched.
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
                $LegacyBackup = Join-Path $env:LEADGENERATOR_HOME "legacy-skill-backups/$Timestamp"
                New-Item -ItemType Directory -Path $LegacyBackup -Force | Out-Null
            }
            Move-Item -LiteralPath $SkillPath -Destination (Join-Path $LegacyBackup $Skill)
        }
    }
    if ($LegacyBackup) {
        Write-Host "Anciens skills generiques archives dans $LegacyBackup"
    }

    & $UvBin run --project plugins/leadgenerator --frozen python `
        scripts/register_codex_marketplace.py --code-root $RootDir --codex-command $CodexBin
    Assert-NativeSuccess "La liaison du marketplace au dossier source a echoue"
    & $CodexBin plugin add $PluginName
    Assert-NativeSuccess "L'installation du plugin Lead Generator a echoue"

    if (-not (Test-Path -LiteralPath $InstalledPluginRoot -PathType Container)) {
        throw "Le cache installe est introuvable dans $InstalledPluginRoot."
    }

    # The bootstrap environment has served its purpose. The cached plugin now
    # gets its own environment, built in place with paths valid on this PC.
    Remove-Item Env:UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue

    Start-InstallStep "Construction du runtime local du plugin"
    $CachedVenv = Join-Path $InstalledPluginRoot ".venv"
    & $UvBin venv --clear --python 3.13 $CachedVenv
    Assert-NativeSuccess "La creation de l'environnement Python du plugin a echoue"
    & $UvBin sync --project $InstalledPluginRoot --frozen --python 3.13
    Assert-NativeSuccess "L'installation Python du cache Lead Generator a echoue"

    # Codex Desktop can inherit a PATH captured before uv was installed. Store
    # the absolute executable path in the installed MCP config to remove that
    # Windows-only startup dependency.
    Write-InstalledMcpConfig -PluginRoot $InstalledPluginRoot -UvCommand $UvBin
    & $UvBin run --project $InstalledPluginRoot --frozen python `
        (Join-Path $RootDir "scripts/configure_workspace.py") `
        --code-root $RootDir --plugin-root $InstalledPluginRoot --uv-command $UvBin
    Assert-NativeSuccess "La liaison du plugin a son dossier prive a echoue"

    & $UvBin run --project $InstalledPluginRoot --frozen python -c "import leadgenerator.mcp.server"
    Assert-NativeSuccess "Le serveur MCP Lead Generator installe ne demarre pas"

    Start-InstallStep "Validation reelle du serveur et de l'interface"
    & $UvBin run --project $InstalledPluginRoot --frozen python `
        (Join-Path $RootDir "scripts/verify_installed_plugin.py") `
        --plugin-root $InstalledPluginRoot `
        --uv-command $UvBin
    Assert-NativeSuccess "Le test MCP reel de Lead Generator a echoue"

    # Keep paths retained by already-open tasks usable after an upgrade. Failure
    # to create a compatibility junction must not invalidate the fresh install.
    foreach ($CachedVersion in $PreviousCacheVersions) {
        $CompatibilityPath = Join-Path $CacheRoot $CachedVersion
        if ($CachedVersion -ne $PluginVersion -and -not (Test-Path -LiteralPath $CompatibilityPath)) {
            try {
                New-Item -ItemType Junction -Path $CompatibilityPath -Target $InstalledPluginRoot | Out-Null
            }
            catch {
                Write-Warning "Ancien cache $CachedVersion non relie : $($_.Exception.Message)"
            }
        }
    }
}
catch {
    $Failure = $_
}
finally {
    if ($null -eq $PreviousUvProjectEnvironment) {
        Remove-Item Env:UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue
    }
    else {
        $env:UV_PROJECT_ENVIRONMENT = $PreviousUvProjectEnvironment
    }
    if ($BootstrapVenv -and (Test-Path -LiteralPath $BootstrapVenv)) {
        Remove-Item -LiteralPath $BootstrapVenv -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($VenvStash -and (Test-Path -LiteralPath $VenvStash -PathType Container)) {
        if (Test-Path -LiteralPath $PluginVenv) {
            Remove-Item -LiteralPath $PluginVenv -Recurse -Force -ErrorAction SilentlyContinue
        }
        Move-Item -LiteralPath $VenvStash -Destination $PluginVenv
        Remove-Item -LiteralPath $VenvStashDir -Force -ErrorAction SilentlyContinue
    }
}

if ($Failure) {
    Write-Host ""
    Write-Host "Installation interrompue pendant : $CurrentStep" -ForegroundColor Red
    Write-Host $Failure.Exception.Message -ForegroundColor Red
    Write-Host "Fermez completement Codex puis relancez ce meme installateur. Il peut etre execute plusieurs fois sans effacer les profils." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Installation et validation terminees." -ForegroundColor Green
Write-Host "Lead Generator, son serveur MCP et son interface sont fonctionnels sur ce PC."
Write-Host "Quittez completement ChatGPT/Codex puis relancez l'application."
Write-Host "Dans une nouvelle conversation, demandez :"
Write-Host "  Trouvez-moi des leads dans l'industrie."
Write-Host "Sans objectif configure, l'agent demandera d'abord votre offre et votre cible."

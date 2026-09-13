#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

HOST_TARGET="codex"
if [[ $# -gt 0 ]]; then
    if [[ $# -ne 2 || "$1" != "--host" ]]; then
        echo "Usage: scripts/install_client.sh [--host codex|claude-code|claude-desktop]"
        exit 1
    fi
    HOST_TARGET="$2"
fi
case "$HOST_TARGET" in
    codex|claude-code|claude-desktop) ;;
    *) echo "Hote inconnu : $HOST_TARGET"; exit 1 ;;
esac

# Install missing tools from the vendors' official HTTPS installers. Download
# first so a failed transfer can never be mistaken for a successful shell run.
install_official_tool() {
    local url="$1"
    local download
    download="$(mktemp)"
    if ! curl --proto '=https' --tlsv1.2 -fsSL "$url" -o "$download"; then
        rm -f "$download"
        return 1
    fi
    sh "$download" || { rm -f "$download"; return 1; }
    rm -f "$download"
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    hash -r
}

if ! command -v uv >/dev/null 2>&1; then
    echo "Installation automatique de uv."
    UV_NO_MODIFY_PATH=1 install_official_tool "https://astral.sh/uv/install.sh"
fi

if [[ "$HOST_TARGET" != "codex" ]]; then
    uv sync --project plugins/leadgenerator --frozen --python 3.13
    LEADGENERATOR_HOME="$(uv run --project plugins/leadgenerator --frozen python \
        scripts/configure_workspace.py --code-root "$ROOT_DIR" --print-home)"
    export LEADGENERATOR_HOME
    export LEADGENERATOR_DATABASE_URL=""
    export LEADGENERATOR_HOST="claude"
    if [[ "$(uname -s)" == "Linux" ]]; then
        uv run --project plugins/leadgenerator --frozen playwright install --with-deps chromium
    else
        uv run --project plugins/leadgenerator --frozen playwright install chromium
    fi
    uv run --project plugins/leadgenerator --frozen python scripts/verify_workspace.py
    uv run --project plugins/leadgenerator --frozen python scripts/install_claude.py \
        --code-root "$ROOT_DIR" --uv-command "$(command -v uv)" --host "$HOST_TARGET"
    echo "Installation terminee. Quitte completement Claude puis relance-le dans ce projet."
    echo "Le premier usage d'un dossier neuf demande de creer un objectif."
    exit 0
fi

if ! command -v codex >/dev/null 2>&1; then
    echo "Installation automatique du CLI Codex."
    install_official_tool "https://chatgpt.com/codex/install.sh"
fi
CODEX_BIN="$(command -v codex)"
MIN_CODEX_VERSION="0.153.4"
CODEX_VERSION="$($CODEX_BIN --version | awk '{print $NF}')"
version_at_least() {
    awk -v current="$1" -v minimum="$2" 'BEGIN {
        split(current, actual, ".")
        split(minimum, required, ".")
        for (part = 1; part <= 3; part++) {
            sub(/[^0-9].*$/, "", actual[part])
            sub(/[^0-9].*$/, "", required[part])
            actual[part] += 0
            required[part] += 0
            if (actual[part] > required[part]) exit 0
            if (actual[part] < required[part]) exit 1
        }
        exit 0
    }'
}
if ! version_at_least "$CODEX_VERSION" "$MIN_CODEX_VERSION"; then
    echo "Mise a jour de Codex requise ($CODEX_VERSION -> $MIN_CODEX_VERSION ou version plus recente)."
    "$CODEX_BIN" update
    hash -r
    CODEX_BIN="$(command -v codex)"
    CODEX_VERSION="$($CODEX_BIN --version | awk '{print $NF}')"
    if ! version_at_least "$CODEX_VERSION" "$MIN_CODEX_VERSION"; then
        echo "Codex $MIN_CODEX_VERSION ou plus recent est requis ; version detectee : $CODEX_VERSION."
        exit 1
    fi
fi

echo "Installation de Lead Generator dans $ROOT_DIR"
uv sync --project plugins/leadgenerator --frozen --python 3.13
LEADGENERATOR_HOME="$(uv run --project plugins/leadgenerator --frozen python \
    scripts/configure_workspace.py --code-root "$ROOT_DIR" --print-home)"
export LEADGENERATOR_HOME
export LEADGENERATOR_DATABASE_URL=""
echo "Donnees privees de cette installation : $LEADGENERATOR_HOME"
echo "Aucun ancien objectif ou profil global n'est importe automatiquement."
uv run --project plugins/leadgenerator --frozen python \
    scripts/configure_workspace.py --code-root "$ROOT_DIR"

if [[ "$(uname -s)" == "Linux" ]]; then
    uv run --project plugins/leadgenerator playwright install --with-deps chromium
else
    uv run --project plugins/leadgenerator playwright install chromium
fi

if ! "$CODEX_BIN" login status >/dev/null 2>&1; then
    echo "Connexion ChatGPT requise pour utiliser le modele OpenAI."
    "$CODEX_BIN" login --device-auth
fi

MARKETPLACE_NAME="leadgenerator-local"
PLUGIN_NAME="leadgenerator@$MARKETPLACE_NAME"
PLUGIN_VERSION="$(
    uv run --project plugins/leadgenerator --frozen python -c \
        'import json; from pathlib import Path; print(json.loads(Path("plugins/leadgenerator/.codex-plugin/plugin.json").read_text())["version"])'
)"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
CACHE_ROOT="$CODEX_HOME_DIR/plugins/cache/$MARKETPLACE_NAME/leadgenerator"
INSTALLED_PLUGIN_ROOT="$CACHE_ROOT/$PLUGIN_VERSION"
# Seed the array for macOS Bash 3, where expanding an empty array under `set -u`
# raises an unbound-variable error. The current version is ignored by the loop.
PREVIOUS_CACHE_VERSIONS=("$PLUGIN_VERSION")
if [[ -d "$CACHE_ROOT" ]]; then
    while IFS= read -r cached_path; do
        cached_version="$(basename "$cached_path")"
        if [[ "$cached_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([+-][A-Za-z0-9._-]+)?$ ]]; then
            PREVIOUS_CACHE_VERSIONS+=("$cached_version")
        fi
    done < <(find "$CACHE_ROOT" -mindepth 1 -maxdepth 1 \( -type d -o -type l \) -print)
fi

# Older installers copied the generic Lead Generator skills directly into
# ~/.codex/skills. Those copies shadow the plugin-owned skills and can keep stale
# instructions alive after an upgrade. Archive only the generic duplicates; keep
# offer-specific skills and the local user profile untouched.
LEGACY_SKILLS=(
    leadgenerator
    lead-company-search
    lead-company-research
    lead-company-visuals
    lead-contact-discovery
    lead-contact-enrichment
    lead-hubspot-sync
)
LEGACY_BACKUP=""
for skill in "${LEGACY_SKILLS[@]}"; do
    skill_path="$HOME/.codex/skills/$skill"
    if [[ -d "$skill_path" ]]; then
        if [[ -z "$LEGACY_BACKUP" ]]; then
            LEGACY_BACKUP="$LEADGENERATOR_HOME/legacy-skill-backups/$(date -u +%Y%m%dT%H%M%SZ)"
            mkdir -p "$LEGACY_BACKUP"
        fi
        mv "$skill_path" "$LEGACY_BACKUP/$skill"
    fi
done
if [[ -n "$LEGACY_BACKUP" ]]; then
    echo "Anciens skills generiques archives dans $LEGACY_BACKUP"
fi

uv run --project plugins/leadgenerator --frozen python \
    scripts/register_codex_marketplace.py --code-root "$ROOT_DIR" --codex-command "$CODEX_BIN"

# Local marketplace installs copy the plugin into Codex's cache. A copied Python
# virtual environment contains absolute links to its original location and is not
# portable, so keep the development environment out of the installed snapshot.
PLUGIN_VENV="$ROOT_DIR/plugins/leadgenerator/.venv"
VENV_STASH=""
restore_plugin_venv() {
    if [[ -n "$VENV_STASH" && -d "$VENV_STASH" ]]; then
        mv "$VENV_STASH" "$PLUGIN_VENV"
        rmdir "$(dirname "$VENV_STASH")"
        VENV_STASH=""
    fi
}
if [[ -d "$PLUGIN_VENV" ]]; then
    VENV_STASH_DIR="$(mktemp -d)"
    VENV_STASH="$VENV_STASH_DIR/.venv"
    mv "$PLUGIN_VENV" "$VENV_STASH"
    trap restore_plugin_venv EXIT
fi

"$CODEX_BIN" plugin add "$PLUGIN_NAME"

# Build the cached environment explicitly. Running `codex plugin add` directly
# can copy a non-portable development virtualenv whose Python links no longer
# resolve from the cache. The installed MCP server must be healthy before this
# installer reports success.
if [[ ! -d "$INSTALLED_PLUGIN_ROOT" ]]; then
    echo "Le cache installe est introuvable dans $INSTALLED_PLUGIN_ROOT."
    exit 1
fi
if [[ -d "$INSTALLED_PLUGIN_ROOT/.venv" && ! -x "$INSTALLED_PLUGIN_ROOT/.venv/bin/python" ]]; then
    uv venv --clear --python 3.13 "$INSTALLED_PLUGIN_ROOT/.venv"
fi
uv sync --project "$INSTALLED_PLUGIN_ROOT" --frozen --python 3.13
uv run --project "$INSTALLED_PLUGIN_ROOT" --frozen python \
    "$ROOT_DIR/scripts/configure_workspace.py" --code-root "$ROOT_DIR" \
    --plugin-root "$INSTALLED_PLUGIN_ROOT"
uv run --project "$INSTALLED_PLUGIN_ROOT" --frozen python -c \
    'import leadgenerator.mcp.server'
uv run --project "$INSTALLED_PLUGIN_ROOT" --frozen python \
    "$ROOT_DIR/scripts/verify_installed_plugin.py" \
    --plugin-root "$INSTALLED_PLUGIN_ROOT"

# Keep paths referenced by already-open Codex tasks resolvable. Codex removes
# older version directories during an upgrade, while existing tasks retain their
# original absolute skill and MCP paths until they are closed.
for cached_version in "${PREVIOUS_CACHE_VERSIONS[@]}"; do
    compatibility_path="$CACHE_ROOT/$cached_version"
    if [[ "$cached_version" != "$PLUGIN_VERSION" && ! -e "$compatibility_path" && ! -L "$compatibility_path" ]]; then
        ln -s "$PLUGIN_VERSION" "$compatibility_path"
    fi
done

restore_plugin_venv
trap - EXIT

echo
echo "Installation et validation reelle terminees. Le plugin Lead Generator, son serveur MCP et son interface sont fonctionnels."
echo "Quitte completement l'application ChatGPT/Codex puis relance-la : un simple nouvel onglet ne recharge pas les plugins installes."
echo "Le plugin utilise maintenant les donnees du dossier affiche ci-dessus. Les autres dossiers restent intacts."
echo "Dans une nouvelle conversation apres redemarrage, demande :"
echo "  Trouve-moi des leads dans l'industrie."
echo "Sans objectif configure, l'agent doit d'abord te demander ton offre et ta cible."
echo "Apres creation de l'objectif, il lancera la recherche puis l'interface MCP."

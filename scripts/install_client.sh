#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv n'est pas installe. Installe-le depuis https://docs.astral.sh/uv/ puis relance ce script."
    exit 1
fi

echo "Installation de Lead Generator dans $ROOT_DIR"
uv sync --project plugins/leadgenerator --frozen
uv run --project plugins/leadgenerator leadgenerator-migrate-profiles

if [[ "$(uname -s)" == "Linux" ]]; then
    uv run --project plugins/leadgenerator playwright install --with-deps chromium
else
    uv run --project plugins/leadgenerator playwright install chromium
fi

if ! command -v codex >/dev/null 2>&1; then
    echo "Codex n'est pas installe. Installe-le depuis https://developers.openai.com/codex/ puis relance ce script."
    exit 1
fi
CODEX_BIN="$(command -v codex)"
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
            LEGACY_BACKUP="$HOME/.codex/leadgenerator/legacy-skill-backups/$(date -u +%Y%m%dT%H%M%SZ)"
            mkdir -p "$LEGACY_BACKUP"
        fi
        mv "$skill_path" "$LEGACY_BACKUP/$skill"
    fi
done
if [[ -n "$LEGACY_BACKUP" ]]; then
    echo "Anciens skills generiques archives dans $LEGACY_BACKUP"
fi

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

if ! "$CODEX_BIN" plugin marketplace list | grep -Fq "$ROOT_DIR"; then
    "$CODEX_BIN" plugin marketplace add "$ROOT_DIR"
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
uv sync --project "$INSTALLED_PLUGIN_ROOT" --frozen
uv run --project "$INSTALLED_PLUGIN_ROOT" --frozen python -c \
    'import leadgenerator.mcp.server'

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
echo "Installation terminee. Le plugin Lead Generator et ses skills sont installes."
echo "Ouvre une nouvelle conversation Codex, puis demande :"
echo "  Trouve-moi des prospects et affiche le parcours visuel Lead Generator."
echo "  Ou : montre-moi 20 entreprises du code NAF 62.01Z."

#!/bin/bash
# Repair the known desktop PATH failure without moving code or private data.
set -euo pipefail
umask 077

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Ce reparateur est reserve a macOS." >&2
    exit 1
fi

CACHE_ROOT="${CODEX_HOME:-$HOME/.codex}/plugins/cache/leadgenerator-local/leadgenerator"
if [[ $# -gt 0 ]]; then
    if [[ $# -ne 2 || "$1" != "--cache-root" ]]; then
        echo "Usage: repair_macos.command [--cache-root chemin]" >&2
        exit 1
    fi
    CACHE_ROOT="$2"
fi

UV_BIN=""
for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv; do
    if [[ -x "$candidate" ]]; then
        UV_BIN="$candidate"
        break
    fi
done
if [[ -z "$UV_BIN" ]]; then
    UV_BIN="$(command -v uv || true)"
fi
if [[ "$UV_BIN" != /* || ! -x "$UV_BIN" ]]; then
    echo "uv est introuvable. Relancez l'installateur actuel depuis code/scripts/install_client.sh." >&2
    exit 1
fi
"$UV_BIN" --version

repaired=0
failed=0
for config in "$CACHE_ROOT"/*/.mcp.json; do
    [[ -f "$config" ]] || continue
    # Compatibility links are repaired via their real version only.
    root="${config%/.mcp.json}"
    [[ -L "$root" ]] && continue
    if [[ -L "$config" ]]; then
        echo "Configuration redirigee : aucune modification." >&2
        failed=1
        continue
    fi
    command="$(/usr/bin/plutil -extract mcpServers.leadgenerator.command raw "$config" 2>/dev/null || true)"
    if [[ "$command" != "uv" && "$command" != */uv ]]; then
        echo "Lancement personnalise : relancez l'installateur pour le verifier." >&2
        failed=1
        continue
    fi
    binding="$(/usr/bin/plutil -extract mcpServers.leadgenerator.env.LEADGENERATOR_HOME raw "$config" 2>/dev/null || true)"
    if [[ "$binding" != /* || ! -d "$binding" || ! -x "$root/.venv/bin/python" ]]; then
        echo "Installation incomplete : relancez code/scripts/install_client.sh. Donnees conservees." >&2
        failed=1
        continue
    fi
    backup="$(mktemp "$root/.mcp.json.before-macos-repair.XXXXXX")"
    cp -p "$config" "$backup"
    temporary="$(mktemp "$root/.mcp.json.repair.XXXXXX")"
    cp "$config" "$temporary"
    /usr/bin/plutil -replace mcpServers.leadgenerator.command -string "$UV_BIN" "$temporary"
    /usr/bin/plutil -convert json -r "$temporary"
    # plutil -lint rejects JSON on some macOS releases; extraction validates it.
    [[ "$(/usr/bin/plutil -extract mcpServers.leadgenerator.command raw "$temporary")" == "$UV_BIN" ]]
    chmod 600 "$temporary"
    mv "$temporary" "$config"
    repaired=$((repaired + 1))
done

if [[ "$repaired" -eq 0 ]]; then
    echo "Aucune configuration reparee. Relancez l'installateur actuel depuis le dossier code." >&2
    exit 1
fi
echo "$repaired configuration(s) de lancement corrigee(s), avec sauvegarde."
echo "Quittez completement Codex (Cmd+Q), puis relancez-le et envoyez un message."
echo "Le chargement des outils sera verifie apres ce redemarrage."
exit "$failed"

"use strict";

// Register the same engine with Desktop's MCP Apps-capable connection owner.
// The project .mcp.json remains the CLI/bootstrap fallback. Never change trust,
// permissions, feature flags, other connectors, or private engine storage.
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const crypto = require("node:crypto");

function desktopConfig(home = os.homedir(), platform = process.platform) {
    if (platform === "darwin")
        return path.join(
            home,
            "Library/Application Support/Claude/claude_desktop_config.json",
        );
    if (platform === "win32")
        return path.join(
            process.env.APPDATA || path.join(home, "AppData/Roaming"),
            "Claude/claude_desktop_config.json",
        );
    return path.join(
        process.env.XDG_CONFIG_HOME || path.join(home, ".config"),
        "Claude/claude_desktop_config.json",
    );
}

function object(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
}

function readConfig(file) {
    let stat;
    try {
        stat = fs.lstatSync(file);
    } catch (error) {
        if (error.code === "ENOENT") return { bytes: null, value: {} };
        throw error;
    }
    if (!stat.isFile() || stat.isSymbolicLink())
        throw new Error(
            "Desktop configuration must be a regular file; no changes made.",
        );
    const bytes = fs.readFileSync(file);
    let value;
    try {
        value = JSON.parse(bytes.toString("utf8"));
    } catch {
        throw new Error(
            "Desktop configuration is not valid JSON; no changes made.",
        );
    }
    if (
        !object(value) ||
        (value.mcpServers !== undefined && !object(value.mcpServers))
    )
        throw new Error(
            "Unexpected Desktop configuration structure; no changes made.",
        );
    return { bytes, value };
}

function nodeCommand() {
    // Prefer a stable package-manager symlink over a versioned Cellar path.
    for (const candidate of ["/opt/homebrew/bin/node", "/usr/local/bin/node"])
        if (
            fs.existsSync(candidate) &&
            fs.realpathSync(candidate) === fs.realpathSync(process.execPath)
        )
            return candidate;
    return process.execPath;
}

function configure({
    project = path.resolve(__dirname, "../.."),
    config = desktopConfig(),
    install = false,
    node = nodeCommand(),
} = {}) {
    project = fs.realpathSync(project);
    const launcher = path.join(project, "scripts/claude/project.cjs");
    if (!fs.statSync(launcher).isFile())
        throw new Error("Project launcher is missing.");
    const desired = { command: node, args: [launcher] };
    const snapshot = readConfig(config);
    const existing = snapshot.value.mcpServers?.leadgenerator;
    if (existing !== undefined) {
        if (JSON.stringify(existing) === JSON.stringify(desired))
            return {
                status: "configured",
                changed: false,
                connection_owner: "claude_desktop",
                render_verified: false,
            };
        // A different installation may belong to another project. Do not replace it.
        return {
            status: "conflict",
            changed: false,
            message:
                "A different Lead Generator Desktop connection already exists. Review it before replacing it.",
        };
    }
    if (!install)
        return {
            status: "missing",
            changed: false,
            next_action:
                "Run this project helper with --install; do not ask the user to pick a package.",
        };

    const directory = path.dirname(config);
    fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
    const id = crypto.randomUUID();
    const temporary = path.join(directory, `.leadgenerator-${id}.tmp`);
    const backup =
        snapshot.bytes === null
            ? null
            : path.join(directory, `.leadgenerator-config-${id}.bak`);
    const value = {
        ...snapshot.value,
        mcpServers: { ...snapshot.value.mcpServers, leadgenerator: desired },
    };
    try {
        fs.writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, {
            flag: "wx",
            mode: 0o600,
        });
        const current = readConfig(config);
        if (
            (snapshot.bytes === null) !== (current.bytes === null) ||
            (snapshot.bytes !== null && !snapshot.bytes.equals(current.bytes))
        )
            throw new Error(
                "Desktop configuration changed concurrently; retry without overwriting it.",
            );
        if (backup)
            fs.writeFileSync(backup, snapshot.bytes, {
                flag: "wx",
                mode: 0o600,
            });
        fs.renameSync(temporary, config);
    } finally {
        if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
    }
    return {
        status: "configured",
        changed: true,
        connection_owner: "claude_desktop",
        private_backup_created: backup !== null,
        render_verified: false,
        next_action:
            "Reload MCP Configuration using Claude Desktop's Developer menu, or quit and reopen Claude once. Then use this same project and verify the actual MCP App.",
    };
}

module.exports = { configure, desktopConfig };
if (require.main === module) {
    try {
        if (
            process.argv.length !== 3 ||
            !["--status", "--install"].includes(process.argv[2])
        )
            throw new Error(
                "Usage: node scripts/claude/desktop.cjs --status|--install",
            );
        const result = configure({ install: process.argv[2] === "--install" });
        process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
        if (result.status === "conflict") process.exitCode = 2;
    } catch (error) {
        // Parse errors must never echo configuration contents or credentials.
        process.stderr.write(
            `Lead Generator Desktop setup: ${error.message}\n`,
        );
        process.exitCode = 1;
    }
}

"use strict";

// Claude Desktop supplies Node. Python dependencies remain owned by uv, never
// copied from a developer's virtualenv. Keep stdout exclusively for MCP JSON-RPC.
const { spawn, spawnSync } = require("node:child_process");
const { homedir } = require("node:os");
const path = require("node:path");

function start(root = path.resolve(__dirname, "..")) {
    const home = homedir();
    const candidates = [
        process.env.LEADGENERATOR_UV,
        "uv",
        path.join(
            home,
            ".local",
            "bin",
            process.platform === "win32" ? "uv.exe" : "uv",
        ),
        path.join(
            home,
            ".cargo",
            "bin",
            process.platform === "win32" ? "uv.exe" : "uv",
        ),
        "/opt/homebrew/bin/uv",
        "/usr/local/bin/uv",
    ].filter(Boolean);
    const uv = candidates.find(
        (command) =>
            spawnSync(command, ["--version"], {
                stdio: "ignore",
                timeout: 5000,
                windowsHide: true,
            }).status === 0,
    );
    if (!uv) {
        process.stderr.write(
            "Lead Generator: uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/ and restart Claude.\n",
        );
        process.exit(1);
    }

    const child = spawn(
        uv,
        [
            "run",
            "--project",
            root,
            "--frozen",
            "--no-dev",
            "--python",
            "3.13",
            "leadgenerator-mcp",
        ],
        {
            cwd: root,
            env: { ...process.env, LEADGENERATOR_HOST: "claude" },
            stdio: ["pipe", "pipe", "pipe"],
            windowsHide: true,
        },
    );
    process.stdin.pipe(child.stdin);
    // Proxy rather than inherit Node's potentially non-blocking stdout descriptor.
    // Large tools/list responses must reach Python's blocking pipe intact.
    child.stdout.pipe(process.stdout);
    child.stderr.pipe(process.stderr);
    child.stdin.on("error", (error) => {
        if (error.code !== "EPIPE")
            process.stderr.write(
                "Lead Generator: MCP input closed unexpectedly.\n",
            );
    });
    const stop = () => {
        if (!child.killed) child.kill("SIGTERM");
    };
    process.once("SIGTERM", stop);
    process.once("SIGINT", stop);
    process.stdin.once("end", stop);
    child.once("error", () => {
        process.stderr.write(
            "Lead Generator: unable to start the Python MCP server.\n",
        );
        process.exit(1);
    });
    child.once("exit", (code) => process.exit(code ?? 1));
    return child;
}

module.exports = { start };
if (require.main === module) start();

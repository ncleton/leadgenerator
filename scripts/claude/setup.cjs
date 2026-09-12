"use strict";

// Keep host configuration local; distribute only reviewed, portable templates.
const fs = require("node:fs");
const path = require("node:path");

function prepare(root) {
    const files = ["CLAUDE.md", ".mcp.json"];
    const templates = path.join(__dirname, "templates");
    // Preflight every destination before creating anything. Never overwrite a
    // customized instruction file or another MCP registration.
    for (const name of files) {
        const target = path.join(root, name);
        if (fs.existsSync(target) &&
            !fs.readFileSync(target).equals(fs.readFileSync(path.join(templates, name)))) {
            throw new Error(`Existing ${name} differs; review it manually. Nothing overwritten.`);
        }
    }
    for (const name of files) {
        const target = path.join(root, name);
        if (!fs.existsSync(target)) {
            fs.copyFileSync(path.join(templates, name), target, fs.constants.COPYFILE_EXCL);
        }
    }
}

module.exports = { prepare };
if (require.main === module) {
    try {
        prepare(path.resolve(__dirname, "../.."));
        console.log("Claude project files ready. Open this folder in Claude Code.");
    } catch (error) {
        console.error(error.message);
        process.exitCode = 1;
    }
}

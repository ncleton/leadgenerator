"use strict";

// Project sessions use the live canonical engine, never a generated build path.
const path = require("node:path");
const codeRoot = path.resolve(__dirname, "../..");
// A project launch follows the folder it was opened from, not an unrelated
// global workspace inherited from the shell or a previous installation.
process.env.LEADGENERATOR_HOME = path.join(
    path.dirname(codeRoot),
    path.basename(codeRoot).toLowerCase() === "code"
        ? "donnees-privees"
        : `${path.basename(codeRoot)}-donnees-privees`,
);
process.env.LEADGENERATOR_DATABASE_URL = "";
require("./launcher.cjs").start(
    path.join(codeRoot, "plugins/leadgenerator"),
);

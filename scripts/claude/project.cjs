"use strict";

// Project sessions use the live canonical engine, never a generated build path.
const path = require("node:path");
require("./launcher.cjs").start(
    path.resolve(__dirname, "../../plugins/leadgenerator"),
);

const path = require("path");
const fs = require("fs");

function loadConfig() {
  const file = path.join(__dirname, "..", "config", "default.json");
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

module.exports = { loadConfig };

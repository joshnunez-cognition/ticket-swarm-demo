const { createApp } = require("./app");
const { loadConfig } = require("./config");

const fakeDb = { query: () => [] };
const port = loadConfig().port;
createApp({ db: fakeDb }).listen(port, () => console.log(`member-portal on :${port}`));

const express = require("express");
const { loadConfig } = require("./config");
const { searchInbox } = require("./messages");

function createApp({ db } = {}) {
  const config = loadConfig();
  const app = express();

  app.get("/health", (req, res) => res.json({ status: "ok" }));

  app.get("/api/settings", (req, res) => {
    res.json({ sessionTtlMinutes: config.sessionTtlMinutes, region: config.aws.region });
  });

  app.get("/api/inbox", (req, res) => {
    const memberId = req.header("x-member-id");
    if (!memberId) return res.status(401).json({ error: "unauthenticated" });
    res.json({ results: searchInbox(db, memberId, req.query.q || "") });
  });

  return app;
}

module.exports = { createApp };

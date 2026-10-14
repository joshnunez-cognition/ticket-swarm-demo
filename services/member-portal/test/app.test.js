const test = require("node:test");
const assert = require("node:assert");
const { createApp } = require("../src/app");
const { INBOX_SQL } = require("../src/messages");

function withServer(db, fn) {
  return new Promise((resolve, reject) => {
    const server = createApp({ db }).listen(0, async () => {
      try {
        await fn(`http://127.0.0.1:${server.address().port}`);
        resolve();
      } catch (err) {
        reject(err);
      } finally {
        server.close();
      }
    });
  });
}

test("health responds ok", () =>
  withServer({ query: () => [] }, async (base) => {
    const res = await fetch(`${base}/health`);
    assert.deepStrictEqual(await res.json(), { status: "ok" });
  }));

test("inbox requires a member id", () =>
  withServer({ query: () => [] }, async (base) => {
    const res = await fetch(`${base}/api/inbox`);
    assert.strictEqual(res.status, 401);
  }));

test("inbox query is parameterized", () => {
  assert.ok(!INBOX_SQL.includes("${"));
  assert.strictEqual(INBOX_SQL.split("?").length - 1, 2);
});

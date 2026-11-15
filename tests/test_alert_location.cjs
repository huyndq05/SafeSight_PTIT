const assert = require("node:assert/strict");
const fs = require("node:fs");
const source = fs.readFileSync("static/js/app.js", "utf8");
const start = source.indexOf("function alertLocation(");
const end = source.indexOf("VIEWS.verify =", start);
const S = { settings: { site_name: "Site A", site_address: "Address A" } };
eval(source.slice(start, end));
assert.equal(alertLocation({ location: "" }), "Site A · Address A");
assert.equal(
  alertLocation({ location: "Gate 1" }),
  "Gate 1 · Site A · Address A",
);
assert.equal(alertLocation({ location: "Site A" }), "Site A · Address A");
S.settings = {};
assert.equal(alertLocation({ location: "Gate 1" }), "Gate 1");
assert.ok(alertLocation({ location: "" }).length > 0);
console.log("5 alert location checks passed");

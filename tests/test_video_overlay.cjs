const assert = require("node:assert/strict");
const fs = require("node:fs");
const source = fs.readFileSync("static/js/app.js", "utf8");
const start = source.indexOf("function cachedFrameIndex(");
const end = source.indexOf("function connectDemoVideo(", start);
eval(source.slice(start, end));
const frames = [
  { time: 0, detections: [] },
  { time: 0.04, detections: [] },
  { time: 0.08, detections: [] },
];
assert.equal(cachedFrameIndex(frames, 0), 0);
assert.equal(cachedFrameIndex(frames, 0.039), 0);
assert.equal(cachedFrameIndex(frames, 0.04), 1);
assert.equal(cachedFrameIndex(frames, 0.079), 1);
assert.equal(cachedFrameIndex(frames, 0.08), 2);
assert.equal(cachedFrameIndex(frames, 100), 2);
assert.equal(cachedFrameIndex([], 1), -1);
assert.equal(cachedFrameIndex(frames, -1), -1);
const playback = source.slice(
  end,
  source.indexOf("function drawDemoDetections(", end),
);
assert.ok(!playback.includes("toBlob("));
assert.ok(!playback.includes("drawImage("));
assert.ok(!playback.includes("/frame"));
assert.ok(playback.includes("metadata?.mediaTime"));
console.log("12 cached playback checks passed");
const drawingStart = source.indexOf("function drawDemoDetections(");
const drawingEnd = source.indexOf(
  "function clearDemoDetections(",
  drawingStart,
);
const window = { devicePixelRatio: 2 };
let drawingArgs;
const drawAnnotations = (...args) => {
  drawingArgs = args;
};
const ctx = { setTransform() {}, clearRect() {} };
const canvas = {
  width: 300,
  height: 150,
  getBoundingClientRect: () => ({ width: 600, height: 400 }),
  getContext: () => ctx,
};
eval(source.slice(drawingStart, drawingEnd));
drawDemoDetections(canvas, [], 1920, 1080);
assert.equal(canvas.width, 1200);
assert.equal(canvas.height, 800);
assert.equal(drawingArgs[4], 0.625);
assert.equal(drawingArgs[5], 0.625);
assert.equal(drawingArgs[6], 0);
assert.equal(drawingArgs[7], 62.5);
console.log("6 sharp overlay sizing and letterbox checks passed");

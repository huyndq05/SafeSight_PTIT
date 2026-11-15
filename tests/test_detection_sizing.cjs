const assert = require("node:assert/strict");
const fs = require("node:fs");
const source = fs.readFileSync("static/js/app.js", "utf8");
const start = source.indexOf("function drawAnnotations(");
const end = source.indexOf("const statusName", start);
const style = {
  line_width: 4,
  font_size: 18,
  reference_width: 960,
  padding: 4,
  label_height: 28,
  colors: {},
  default_color: "#fff",
};
const render = new Function(
  "S",
  "DETECTION_STYLE",
  "detectionLabel",
  source.slice(start, end) + "return drawAnnotations;",
)({ preferences: {} }, style, () => "knife 90%");
for (const width of [640, 1280, 1920, 3840]) {
  for (const dpr of [1, 2]) {
    const scale = (600 * dpr) / width;
    const ctx = {
      save() {},
      restore() {},
      translate() {},
      scale() {},
      beginPath() {},
      rect() {},
      clip() {},
      strokeRect() {},
      measureText() {
        return { width: 60 };
      },
      fillRect() {},
      fillText() {},
    };
    render(
      ctx,
      [{ label: "knife", conf: 0.9, box: [10, 20, 100, 200] }],
      width,
      (width * 9) / 16,
      scale,
      scale,
      0,
      0,
      dpr,
    );
    assert.ok(Math.abs((ctx.lineWidth * scale) / dpr - 4) < 1e-6);
    assert.ok(Math.abs((parseFloat(ctx.font) * scale) / dpr - 18) < 1e-6);
    const imageScale = 600 / width;
    render(
      ctx,
      [{ label: "knife", conf: 0.9, box: [10, 20, 100, 200] }],
      width,
      (width * 9) / 16,
      imageScale,
      imageScale,
      0,
      0,
      1,
    );
    assert.ok(Math.abs(ctx.lineWidth * imageScale - 4) < 1e-6);
    assert.ok(Math.abs(parseFloat(ctx.font) * imageScale - 18) < 1e-6);
  }
}
console.log(
  "Consistent border and label size across four source resolutions and two DPI levels",
);

const cameraState = { simplified: false };
const cameraSizing = new Function(
  "S",
  source.slice(
    source.indexOf("function cameraDisplayWidth("),
    source.indexOf("const cameraFeedResizeObserver"),
  ) + "return { cameraDisplayWidth, updateCameraFeed };",
)(cameraState);
let rect = { width: 960, height: 540 };
const image = {
  naturalWidth: 2560,
  naturalHeight: 1440,
  dataset: {},
  src: "/video_feed/test",
  getBoundingClientRect: () => rect,
};
cameraSizing.updateCameraFeed(image);
assert.equal(image.dataset.displayWidth, 960);
assert.match(image.src, /display_width=960/);
rect = { width: 0, height: 0 };
cameraSizing.updateCameraFeed(image, true);
assert.equal(
  image.dataset.displayWidth,
  960,
  "Hidden settings must preserve valid camera sizing",
);
rect = { width: 1920, height: 1080 };
cameraSizing.updateCameraFeed(image);
assert.equal(
  image.dataset.displayWidth,
  1920,
  "Fullscreen must replace the old thumbnail width",
);
rect = { width: 1600, height: 400 };
assert.equal(
  cameraSizing.cameraDisplayWidth(image),
  711,
  "Use contained image width, not black borders",
);
image.naturalWidth = 1080;
image.naturalHeight = 1920;
assert.equal(cameraSizing.cameraDisplayWidth(image), 225);
rect = { width: 600, height: 400 };
image.naturalWidth = 2560;
image.naturalHeight = 1440;
cameraState.simplified = true;
cameraSizing.updateCameraFeed(image);
assert.equal(image.dataset.displayWidth, 600);
assert.match(image.src, /simple=1/);
console.log(
  "Camera sizing follows visible image bounds, hidden views and fullscreen",
);

"use strict";
const sessionUser = JSON.parse(
  document.getElementById("session-user")?.textContent || "null",
);
const originalFetch = window.fetch.bind(window);
window.fetch = async (input, options = {}) => {
  const url = new URL(
    typeof input === "string" ? input : input.url,
    location.href,
  );
  if (url.origin === location.origin) {
    const headers = new Headers(
      options.headers || (input instanceof Request ? input.headers : undefined),
    );
    const method = (
      options.method || (input instanceof Request ? input.method : "GET")
    ).toUpperCase();
    if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
      headers.set(
        "X-CSRF-Token",
        document.querySelector("meta[name=csrf-token]")?.content || "",
      );
    }
    options = { ...options, headers };
  }
  const response = await originalFetch(input, options);
  if (response.status === 401 && url.origin === location.origin)
    location.assign("/login");
  return response;
};
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const searchName = (value) =>
  String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase()
    .trim()
    .replace(/\s+/g, " ");
const matchesSourceName = (name, query) =>
  searchName(name).includes(searchName(query));
const fmt = (iso) => (iso ? new Date(iso).toLocaleString("vi-VN") : "-");
const CLASS_NAMES = {
  axe: "Rìu",
  baseball_bat: "Gậy bóng chày",
  hammer: "Búa",
  pistol: "Súng ngắn",
  knife: "Dao",
  sword: "Kiếm",
  rifle: "Súng trường",
  machete: "Dao rựa",
  stick: "Gậy",
  spear: "Giáo",
};
const className = (label) => CLASS_NAMES[label] || label;
const DETECTION_STYLE = JSON.parse($("#detection-style").textContent);
const detectionLabel = (d) =>
  `${d.label} ${Math.floor(Math.max(0, Math.min(1, Number(d.conf))) * 100 + 0.5)}%`;

function drawAnnotations(
  ctx,
  detections,
  width,
  height,
  scaleX = 1,
  scaleY = 1,
  offsetX = 0,
  offsetY = 0,
  displayPixelRatio = null,
) {
  const prefs = S.preferences || {};
  const style = {
    ...DETECTION_STYLE,
    line_width: prefs.box_width || DETECTION_STYLE.line_width,
    font_size: prefs.label_size || DETECTION_STYLE.font_size,
    label_height: (prefs.label_size || DETECTION_STYLE.font_size) + 10,
  };
  const scale =
    displayPixelRatio === null
      ? Math.max(1, width / style.reference_width)
      : displayPixelRatio /
        Math.max(0.0001, Math.min(Math.abs(scaleX), Math.abs(scaleY)));
  const padding = style.padding * scale,
    labelHeight = style.label_height * scale;
  ctx.save();
  ctx.translate(offsetX, offsetY);
  ctx.scale(scaleX, scaleY);
  ctx.beginPath();
  ctx.rect(0, 0, width, height);
  ctx.clip();
  ctx.lineWidth = style.line_width * scale;
  ctx.font = `${style.font_size * scale}px Arial, sans-serif`;
  ctx.textBaseline = "alphabetic";
  for (const d of detections || []) {
    if (
      !Array.isArray(d.box) ||
      d.box.length !== 4 ||
      ![...d.box, Number(d.conf)].every(Number.isFinite)
    )
      continue;
    const [x1, y1, x2, y2] = d.box.map((v, i) =>
      Math.max(0, Math.min((i % 2 ? height : width) - 1, v)),
    );
    if (x2 <= x1 || y2 <= y1) continue;
    const color = prefs[`color_${d.label}`] || "#22c55e";
    ctx.strokeStyle = color;
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
    if (prefs.label_content === "none") continue;
    const label =
      prefs.label_content === "name"
        ? d.label
        : prefs.label_content === "confidence"
          ? `${Math.round(d.conf * 100)}%`
          : detectionLabel(d);
    const labelWidth = ctx.measureText(label).width + 2 * padding;
    const left = Math.max(0, Math.min(x1, width - labelWidth));
    const top = Math.max(0, Math.min(y1 - labelHeight, height - labelHeight));
    ctx.fillStyle = color;
    ctx.fillRect(left, top, labelWidth, labelHeight);
    const rgb = [1, 3, 5].map((index) =>
      parseInt(color.slice(index, index + 2), 16),
    );
    ctx.fillStyle =
      0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2] > 150
        ? "#111111"
        : "#ffffff";
    ctx.fillText(
      label,
      left + padding,
      top + labelHeight - padding - 4 * scale,
    );
  }
  ctx.restore();
}
const statusName = (status) =>
  ({
    pending: "Chờ xác minh",
    confirmed: "Đã xác nhận",
    dispatched: "Đã gửi thông báo",
    completed: "Đã hoàn tất",
    deleted: "Nhận diện sai",
  })[status] || status;
const wtext = (a) =>
  Object.entries(a.summary)
    .map(([k, n]) => `${n} ${className(k)}`)
    .join(", ");
const chips = (a) =>
  Object.entries(a.summary)
    .map(
      ([k, n]) =>
        `<span class="chip ${esc(k)}">${n} ${esc(className(k))}</span>`,
    )
    .join("");
const imgUrl = (a) => `/alert_images/${a.image}`;
const evidenceRecord = (entry) =>
  typeof entry === "string"
    ? { image: entry, detections: null, captured_at: null }
    : entry;
const detectionInfoText = (detections) =>
  detections == null
    ? "Chưa có dữ liệu nhận diện cho ảnh này"
    : detections.length
      ? detections
          .map((d) => `${className(d.label)} ${Math.round(d.conf * 100)}%`)
          .join(" · ")
      : "Không phát hiện lại vật thể mục tiêu";
const detectionInfo = (detections) => esc(detectionInfoText(detections));
const evidenceStrip = (a, selectedImage) =>
  (a.evidence_images || []).length
    ? `<div class="evidence-strip"><h3>Ảnh bổ sung (${a.evidence_images.length}/5)</h3><div class="evidence-frames">${a.evidence_images
        .map((rawEntry, i) => {
          const entry = evidenceRecord(rawEntry);
          const image = entry.image;
          return `<button class="evidence-frame${selectedImage === `/alert_images/${encodeURIComponent(image)}` ? " sel" : ""}" data-act="evidence-frame" data-image="/alert_images/${encodeURIComponent(image)}" data-frame="${i + 1}" title="Xem ảnh ${i + 1} sau phát hiện ban đầu">
      <span class="evidence-thumb-view"><img src="/alert_images/${encodeURIComponent(image)}" alt="Ảnh ${i + 1}"><canvas class="evidence-detections-canvas"></canvas></span>
      <span>Ảnh ${i + 1}</span></button>`;
        })
        .join("")}</div></div>`
    : "";

async function api(url, method = "GET", body) {
  const isForm = body instanceof FormData;
  const r = await fetch(url, {
    method,
    headers: body && !isForm ? { "Content-Type": "application/json" } : {},
    body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
  });
  if (!r.ok) throw new Error(r.status);
  return r.json();
}

const S = {
  sources: [],
  pending: [],
  logs: [],
  stats: null,
  settings: {},
  selected: null,
  selectedEvidence: null,
  known: new Set(),
  first: true,
  view: "live",
  sigs: {},
  tickN: 0,
  silencedUntil: 0,
  maps: {},
  showDetectionLabels: true,
  focusedSource: null,
  liveStreamsSignature: null,
  refreshing: false,
  cameraSearch: "",
};

function paintDetectionOverlay(img, canvas, detections, showLabels) {
  if (!showLabels && canvas) {
    canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
    return;
  }
  if (!img?.complete || !img.naturalWidth || !canvas) {
    if (img && canvas && !img.detectionOverlayPending) {
      img.detectionOverlayPending = true;
      img.addEventListener(
        "load",
        () => {
          img.detectionOverlayPending = false;
          paintDetectionOverlay(
            img,
            canvas,
            canvas.detections,
            S.showDetectionLabels,
          );
        },
        { once: true },
      );
    }
    return;
  }
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(rect.width * dpr);
  canvas.height = Math.round(rect.height * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, rect.width, rect.height);
  const imageRatio = img.naturalWidth / img.naturalHeight;
  const canvasRatio = rect.width / rect.height;
  const contentWidth =
    imageRatio > canvasRatio ? rect.width : rect.height * imageRatio;
  const contentHeight =
    imageRatio > canvasRatio ? rect.width / imageRatio : rect.height;
  const offsetX = (rect.width - contentWidth) / 2;
  const offsetY = (rect.height - contentHeight) / 2;
  const scaleX = contentWidth / img.naturalWidth;
  const scaleY = contentHeight / img.naturalHeight;
  drawAnnotations(
    ctx,
    detections,
    img.naturalWidth,
    img.naturalHeight,
    scaleX,
    scaleY,
    offsetX,
    offsetY,
    1,
  );
}

function refreshDetectionOverlays(root) {
  $$(".alert-detections-canvas, .evidence-detections-canvas", root).forEach(
    (canvas) => {
      paintDetectionOverlay(
        canvas.previousElementSibling,
        canvas,
        canvas.detections,
        S.showDetectionLabels,
      );
    },
  );
}

const evidenceResizeObserver = new ResizeObserver((entries) => {
  for (const entry of entries) {
    const canvas = entry.target.nextElementSibling;
    if (
      canvas?.matches(".alert-detections-canvas, .evidence-detections-canvas")
    ) {
      paintDetectionOverlay(
        entry.target,
        canvas,
        canvas.detections,
        S.showDetectionLabels,
      );
    }
  }
});

function setupAlertDetectionOverlays(root, alert, mainDetections) {
  evidenceResizeObserver.disconnect();
  const mainCanvas = $(".alert-detections-canvas", root);
  if (mainCanvas) {
    mainCanvas.detections = mainDetections || [];
    paintDetectionOverlay(
      $("#alert-image", root),
      mainCanvas,
      mainCanvas.detections,
      S.showDetectionLabels,
    );
  }
  $$(".evidence-frame", root).forEach((button, index) => {
    const canvas = $(".evidence-detections-canvas", button);
    if (!canvas) return;
    canvas.detections =
      evidenceRecord(alert.evidence_images[index]).detections || [];
    paintDetectionOverlay(
      $("img", button),
      canvas,
      canvas.detections,
      S.showDetectionLabels,
    );
  });
  $$("#alert-image, .evidence-frame img", root).forEach((img) =>
    evidenceResizeObserver.observe(img),
  );
}

function toast(msg, actionLabel, action) {
  const t = $("#toast");
  t.replaceChildren(document.createTextNode(msg));
  if (actionLabel && action) {
    const button = document.createElement("button");
    button.className = "toast-action";
    button.textContent = actionLabel;
    button.onclick = () => {
      t.classList.remove("show", "actionable");
      action();
    };
    t.append(" ", button);
  }
  t.classList.toggle("actionable", !!(actionLabel && action));
  t.classList.add("show");
  clearTimeout(toast.id);
  toast.id = setTimeout(
    () => t.classList.remove("show", "actionable"),
    actionLabel ? 8000 : 2600,
  );
}

function beep() {
  if (!S.settings.sound || Date.now() < S.silencedUntil) return;
  try {
    const c = new AudioContext(),
      o = c.createOscillator(),
      g = c.createGain();
    o.type = "square";
    o.frequency.value = 880;
    g.gain.value = 0.08;
    o.connect(g);
    g.connect(c.destination);
    o.start();
    o.stop(c.currentTime + 0.4);
  } catch (e) {}
}

const ICON = {
  dashboard:
    '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>',
  live: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/>',
  verify: '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17v.5"/>',
  history: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  camera:
    '<rect x="3" y="7" width="18" height="13" rx="2"/><circle cx="12" cy="13.5" r="3.5"/><path d="M8 7l1.5-3h5L16 7"/>',
  drone:
    '<circle cx="5" cy="5" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M7 7l2 2M17 7l-2 2M7 17l2-2M17 17l-2-2"/>',
  robot:
    '<rect x="4" y="8" width="16" height="12" rx="2"/><path d="M12 8V4"/><circle cx="9" cy="14" r="1.5"/><circle cx="15" cy="14" r="1.5"/>',
  map: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>',
  site: '<rect x="5" y="3" width="14" height="18"/><path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2"/>',
  bell: '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 21h4"/>',
  settings:
    '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="8" cy="18" r="2"/>',
  log: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
};
const svg = (n) =>
  `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICON[n]}</svg>`;
const NAV = [
  { sep: "VẬN HÀNH" },
  { id: "live", t: "Giám sát trực tiếp", i: "live" },
  { id: "verify", t: "Xử lý cảnh báo", i: "verify", badge: true },
  { id: "history", t: "Lịch sử xử lý", i: "history" },
  { sep: "QUẢN LÝ" },
  { id: "dashboard", t: "Tổng quan", i: "dashboard" },
  { id: "dev-camera", t: "Camera", i: "camera" },
  { id: "dev-drone", t: "Drone", i: "drone" },
  { id: "dev-robot", t: "Robot", i: "robot" },
  { id: "map", t: "Bản đồ", i: "map" },
  { sep: "CẤU HÌNH" },
  { id: "site", t: "Địa điểm", i: "site" },
  { id: "notify", t: "Thông báo", i: "bell" },
  { id: "settings", t: "Cài đặt", i: "settings" },
  { id: "logs", t: "Nhật ký hệ thống", i: "log" },
];

function buildShell() {
  $("#sidebar").innerHTML = NAV.map((n) =>
    n.sep
      ? `<div class="nav-sep">${n.sep}</div>`
      : n.id === "live"
        ? `<div class="live-nav-group"><div class="settings-nav-heading"><button class="nav" data-view="live" title="Giám sát trực tiếp" aria-expanded="false" aria-controls="live-submenu">${svg(n.i)}<span>Giám sát trực tiếp</span><span class="settings-expand" aria-hidden="true" aria-expanded="false"><svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m5 8 5 4 5-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></span></button></div><div id="live-submenu" hidden><nav class="settings-subnav" aria-label="Chế độ giám sát"><button type="button" class="settings-subnav-item" data-live-mode="full" aria-pressed="true">Đầy đủ</button><button type="button" class="settings-subnav-item" data-live-mode="simple" aria-pressed="false">Giản lược</button></nav></div></div>`
        : n.id === "settings"
          ? `<div class="settings-nav-group"><div class="settings-nav-heading"><button class="nav" data-view="settings" title="Cài đặt" aria-expanded="false" aria-controls="settings-submenu">${svg(n.i)}<span>Cài đặt</span><span class="settings-expand" aria-hidden="true" aria-expanded="false"><svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m5 8 5 4 5-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></span></button></div><div id="settings-submenu" hidden></div></div>`
          : `<button class="nav" data-view="${n.id}" title="${n.t}">${svg(n.i)}<span>${n.t}</span>${n.badge ? '<b class="badge" id="badge" hidden>0</b>' : ""}</button>`,
  ).join("");
  $("#main").innerHTML = NAV.filter((n) => n.id)
    .map((n) => `<section class="view" id="view-${n.id}" hidden></section>`)
    .join("");
  if (sessionUser?.is_admin)
    $("#sidebar").insertAdjacentHTML(
      "beforeend",
      `<a class="nav staff-nav" href="/accounts" title="Tài khoản nhân viên">${svg("settings")}<span>Tài khoản nhân viên</span></a>`,
    );
  $$(".nav[data-view]").forEach(
    (b) =>
      (b.onclick = () => {
        if (b.dataset.view === "live") {
          const expand = S.view !== "live" || $("#live-submenu").hidden;
          if (S.view !== "live") showView("live");
          setLiveExpanded(expand);
          return;
        }
        if (b.dataset.view === "settings") {
          const expand = S.view !== "settings" || $("#settings-submenu").hidden;
          if (S.view !== "settings") showView("settings");
          setSettingsExpanded(expand);
          if (innerWidth <= 1100)
            document.body.classList.toggle("mobile-nav-open", expand);
          return;
        }
        showView(b.dataset.view);
        if (innerWidth <= 1100)
          document.body.classList.toggle(
            "mobile-nav-open",
            b.dataset.view === "settings",
          );
      }),
  );
  $("#menu-btn").onclick = () => {
    if (innerWidth <= 1100) document.body.classList.toggle("mobile-nav-open");
    else document.body.classList.toggle("collapsed");
  };
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".live-nav-group")) setLiveExpanded(false);
    if (innerWidth <= 1100 && !event.target.closest("#sidebar, #menu-btn"))
      document.body.classList.remove("mobile-nav-open");
  });
}

function setSettingsExpanded(expanded) {
  $("#settings-submenu").hidden = !expanded;
  $(".nav[data-view=settings] .settings-expand").setAttribute(
    "aria-expanded",
    String(expanded),
  );
  $(".nav[data-view=settings]").setAttribute("aria-expanded", String(expanded));
}

function setLiveExpanded(expanded) {
  $("#live-submenu").hidden = !expanded;
  document.body.classList.toggle("live-menu-open", expanded);
  $(".nav[data-view=live]").setAttribute("aria-expanded", String(expanded));
  $(".nav[data-view=live] .settings-expand").setAttribute(
    "aria-expanded",
    String(expanded),
  );
}

function applySettings() {
  const s = S.settings;
  $("#operator").textContent = sessionUser?.display_name || s.operator || "";
  const p = S.preferences || {};
  document.documentElement.dataset.theme =
    (p.theme || s.theme) === "dark" ? "dark" : "light";
  document.body.dataset.density = p.density || "standard";
  document.body.dataset.fontSize = p.font_size || "medium";
  document.body.dataset.reduceMotion = String(!!p.reduce_motion);
  document.body.dataset.sidebar = p.sidebar || "auto";
  for (const key of [
    "show_camera_name",
    "show_location",
    "show_fps",
    "show_status",
  ]) {
    document.body.dataset[key.replace(/_([a-z])/g, (_, c) => c.toUpperCase())] =
      String(p[key] !== false);
  }
  if (p.sidebar === "collapsed") document.body.classList.add("collapsed");
  else if (p.sidebar === "expanded" || p.sidebar === "auto")
    document.body.classList.remove("collapsed");
  const layout = $("#live-layout");
  if (layout) {
    layout.value = p.camera_columns || "auto";
    $("#streams")?.style.setProperty(
      "--grid-columns",
      layout.value === "auto"
        ? "repeat(auto-fit,minmax(min(100%,360px),1fr))"
        : `repeat(${layout.value},minmax(0,1fr))`,
    );
  }
  $$(".streams img[src*='/video_feed/']").forEach((image) => {
    updateCameraFeed(image, true);
  });
  if (S.view === "verify") refreshDetectionOverlays($("#view-verify"));
}

function showView(id) {
  (VIEWS[S.view] || {}).hide?.();
  S.view = id;
  document.body.classList.toggle(
    "simplified-shell",
    id === "live" && !!S.simplified,
  );
  $$(".view").forEach((v) => (v.hidden = v.id !== `view-${id}`));
  $$(".nav").forEach((b) => {
    b.classList.toggle("active", b.dataset.view === id);
    b.setAttribute("aria-current", b.dataset.view === id ? "page" : "false");
  });
  S.sigs = {};
  (VIEWS[id] || {}).show?.(id);
  (VIEWS[id] || {}).tick?.(id);
}

function makeMap(el) {
  if (typeof L === "undefined") {
    el.innerHTML =
      '<div class="empty">Không tải được Leaflet (cần internet để hiện bản đồ).</div>';
    return null;
  }
  const s = S.settings;
  const siteLat =
    s.site_lat !== "" &&
    s.site_lat != null &&
    Number.isFinite(Number(s.site_lat))
      ? Number(s.site_lat)
      : 21.0285;
  const siteLon =
    s.site_lon !== "" &&
    s.site_lon != null &&
    Number.isFinite(Number(s.site_lon))
      ? Number(s.site_lon)
      : 105.8542;
  const m = L.map(el).setView([siteLat, siteLon], 17);
  L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    { maxZoom: 19, attribution: "Esri" },
  ).addTo(m);
  return {
    m,
    layer: L.layerGroup().addTo(m),
    sitePoint: [siteLat, siteLon],
    siteName: s.site_name,
    fitted: false,
  };
}
function updateMap(mp) {
  if (!mp) return;
  mp.layer.clearLayers();
  const pts = [],
    letter = { camera: "C", drone: "D", robot: "R" };
  L.marker(mp.sitePoint, {
    icon: L.divIcon({
      className: "",
      html: '<div class="site-pin"><span></span></div>',
      iconSize: [36, 42],
      iconAnchor: [18, 42],
    }),
    zIndexOffset: 1000,
  })
    .bindTooltip(mp.siteName || "Vị trí đã cài đặt")
    .addTo(mp.layer);
  pts.push(mp.sitePoint);
  const mk = (lat, lon, cls, txt, tip, onclick) => {
    const m = L.marker([lat, lon], {
      icon: L.divIcon({
        className: "",
        html: `<div class="mk ${cls}">${txt}</div>`,
        iconSize: [26, 26],
      }),
    })
      .bindTooltip(tip)
      .addTo(mp.layer);
    if (onclick) m.on("click", onclick);
    pts.push([lat, lon]);
  };
  S.sources
    .filter((s) => s.lat != null && s.lon != null)
    .forEach((s) =>
      mk(
        s.lat,
        s.lon,
        `${s.type} ${s.online ? "" : "off"}`,
        letter[s.type],
        s.name,
      ),
    );
  S.pending
    .filter((a) => a.lat != null && a.lon != null)
    .forEach((a) =>
      mk(a.lat, a.lon, "alert", "!", `Cảnh báo #${a.id} - ${wtext(a)}`, () => {
        S.selected = a.id;
        showView("verify");
      }),
    );
  if (!mp.fitted && pts.length) {
    mp.m.fitBounds(pts, { maxZoom: 18, padding: [30, 30] });
    mp.fitted = true;
  }
}

function current() {
  if (!S.pending.length) {
    S.selected = null;
    return null;
  }
  if (!S.pending.find((a) => a.id === S.selected)) S.selected = S.pending[0].id;
  return S.pending.find((a) => a.id === S.selected);
}
const alertQueue = (alerts, live = false) =>
  alerts
    .map(
      (
        a,
      ) => `${!live && S.bulkMode ? `<div class="queue-selection"><label class="bulk-check"><input class="bulk-select" type="checkbox" value="${a.id}" aria-label="Chọn cảnh báo ${a.id}" ${S.bulkSelected?.has(a.id) ? "checked" : ""} ${S.bulkBusy || a.notification_status === "sending" ? "disabled" : ""}></label>` : ""}<button class="queue-item ${!live && a.id === S.selected ? "sel" : ""}" data-act="${live ? "open-alert" : "select"}" data-id="${a.id}" aria-label="Mở cảnh báo ${a.id} từ ${esc(a.source_name)}">
  <img src="${imgUrl(a)}" alt="" loading="lazy"><span><b>#${a.id} · ${esc(a.source_name)}</b><span>${esc(wtext(a))}</span><time>${fmt(a.created_at)}</time><span class="status ${a.status}">${statusName(a.status)}</span></span></button>${!live && S.bulkMode ? "</div>" : ""}`,
    )
    .join("") || '<div class="empty"><strong>Không có cảnh báo</strong></div>';
function alertActions(a) {
  if (a.notification_status === "sending")
    return '<p role="status">Đang gửi thông báo…</p>';
  const remove = `<button class="btn alert-remove" data-act="purge" data-id="${a.id}">Xóa cảnh báo</button>`;
  if (a.status === "pending")
    return `<button class="btn primary" data-act="dispatch" data-id="${a.id}">Xác nhận & gửi cảnh báo</button><button class="btn" data-act="delete" data-id="${a.id}">Đánh dấu nhận diện sai</button>${remove}`;
  return `${a.status === "confirmed" ? `<button class="btn primary" data-act="dispatch" data-id="${a.id}">${a.notification_status === "failed" ? "Thử gửi lại thông báo" : "Gửi thông báo"}</button>` : ""}
    <button class="btn" data-act="complete" data-id="${a.id}">Hoàn tất xử lý</button><button class="btn" data-act="delete" data-id="${a.id}">Đánh dấu nhận diện sai</button>${remove}`;
}
function showFalseAlarmDialog(id) {
  const d = $("#dlg");
  d.className = "";
  d.innerHTML = `<form id="false-alarm-form"><h2>${Array.isArray(id) ? `Đánh dấu sai ${id.length} cảnh báo đã chọn` : `Nhận diện sai #${id}`}</h2>
    <label class="dialog-field">Lý do<select name="reason"><option>Không phải hung khí</option><option>Sai loại vật thể</option><option>Ảnh không rõ</option><option>Cảnh báo trùng lặp</option><option>Khác</option></select></label>
    <label class="dialog-field">Loại thực tế (nếu xác định được)<select name="actual_label"><option value="">Chưa xác định</option><option value="background">Không có hung khí</option>${DETECTION_CLASSES.map(([name, label]) => `<option value="${name}">${label}</option>`).join("")}</select></label>
    <label>Thông tin bổ sung<textarea class="note" name="detail" maxlength="300"></textarea></label>
    <p id="false-alarm-error" role="alert"></p><div class="dlg-actions"><button type="button" class="btn" id="cancel-false-alarm">Hủy</button><button type="submit" class="btn primary">Lưu kết quả xác minh</button></div></form>`;
  $("#cancel-false-alarm").onclick = () => d.close();
  $("#false-alarm-form").onsubmit = async (event) => {
    event.preventDefault();
    const form = event.currentTarget,
      button = $("button[type=submit]", form);
    button.disabled = true;
    const data = new FormData(form);
    try {
      if (Array.isArray(id)) {
        d.close();
        await runBulkAlerts("false", {
          reason: data.get("reason"),
          note: data.get("detail"),
          actual_label: data.get("actual_label"),
        });
        return;
      }
      await api(`/api/alerts/${id}/delete`, "POST", {
        reason: data.get("reason"),
        note: data.get("detail"),
        actual_label: data.get("actual_label"),
      });
      d.close();
      toast("Đã lưu kết quả nhận diện sai");
      dirty();
      await refresh(true);
      if (S.view === "history") await VIEWS.history.show();
    } catch (error) {
      $("#false-alarm-error").textContent =
        "Không thể lưu. Cảnh báo có thể đã được xử lý.";
    } finally {
      button.disabled = false;
    }
  };
  d.showModal();
}

async function runBulkAlerts(mode, payload = {}) {
  const ids = [...(S.bulkSelected || [])];
  if (!ids.length || S.bulkBusy) return;
  S.bulkBusy = true;
  dirty();
  tickCurrent();
  const failed = [];
  for (const id of ids) {
    try {
      if (mode === "purge") await api(`/api/alerts/${id}`, "DELETE");
      else await api(`/api/alerts/${id}/delete`, "POST", payload);
    } catch (error) {
      failed.push(id);
    }
  }
  S.bulkBusy = false;
  S.bulkSelected = new Set(failed);
  if (!failed.length) S.bulkMode = null;
  dirty();
  await refresh(true);
  toast(
    `Đã ${mode === "purge" ? "xóa" : "đánh dấu sai"} ${ids.length - failed.length}/${ids.length} cảnh báo${failed.length ? `. Không thực hiện được: ${failed.map((id) => "#" + id).join(", ")}` : ""}`,
  );
}

document.addEventListener("change", (event) => {
  if (!event.target.matches(".bulk-select") || S.bulkBusy) return;
  S.bulkSelected ||= new Set();
  const id = Number(event.target.value);
  if (event.target.checked) S.bulkSelected.add(id);
  else S.bulkSelected.delete(id);
  dirty();
  tickCurrent();
});
document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-bulk]");
  if (!button || S.bulkBusy) return;
  const action = button.dataset.bulk;
  if (["purge", "false"].includes(action)) {
    S.bulkMode = action;
    S.bulkSelected = new Set();
  } else if (action === "cancel") {
    S.bulkMode = null;
    S.bulkSelected = new Set();
  } else if (action === "all")
    S.bulkSelected = new Set(
      S.pending
        .filter((a) => a.notification_status !== "sending")
        .map((a) => a.id),
    );
  else if (action === "submit") {
    const ids = [...(S.bulkSelected || [])];
    if (!ids.length) return;
    if (S.bulkMode === "false") showFalseAlarmDialog(ids);
    else if (
      confirm(
        `Xóa ${ids.length} cảnh báo đã chọn cùng ảnh bằng chứng? Không thể hoàn tác.`,
      )
    )
      runBulkAlerts("purge");
    return;
  }
  dirty();
  tickCurrent();
});
document.addEventListener("input", (event) => {
  if (event.target.matches("#live-search")) tickCurrent();
  if (event.target.matches("#camera-search")) {
    S.cameraSearch = event.target.value;
    filterCameraRows();
  }
});
const logTable = (rows) =>
  `<div class="table-scroll"><table class="tbl log-table"><thead><tr><th>ID</th><th>Thời gian</th><th>Sự kiện</th><th>Chi tiết</th></tr></thead><tbody>${
    rows
      .map(
        (l) =>
          `<tr class="lv-${esc(l.level)}"><td>${l.id}</td><td>${fmt(l.ts)}</td><td><span class="log-level">${esc(l.level)}</span> ${esc(l.subject)}</td><td>${esc(l.info)}</td></tr>`,
      )
      .join("") ||
    '<tr><td colspan="4" class="table-empty">Chưa có nhật ký hệ thống.</td></tr>'
  }</tbody></table></div>`;

async function act(what, id) {
  if (S.acting) return;
  S.acting = true;
  const controls = $$(".review-actions button");
  controls.forEach((button) => {
    button.disabled = true;
  });
  $("#view-verify").setAttribute("aria-busy", "true");
  try {
    if (what === "dispatch") {
      const r = await api(`/api/alerts/${id}/dispatch`, "POST");
      toast(r.info);
    } else if (what === "confirm" || what === "complete") {
      await api(`/api/alerts/${id}/${what}`, "POST");
      toast(what === "confirm" ? "Đã xác nhận cảnh báo" : "Đã hoàn tất xử lý");
    } else if (what === "purge") {
      if (
        !confirm(
          "Xóa cảnh báo này cùng ảnh bằng chứng? Thao tác không thể hoàn tác và không đánh dấu nhận diện đúng/sai.",
        )
      )
        return;
      await api(`/api/alerts/${id}`, "DELETE");
      toast("Đã xóa cảnh báo");
    } else if (what === "delete") {
      showFalseAlarmDialog(id);
      return;
    }
  } catch (e) {
    toast("Không thực hiện được (cảnh báo có thể đã được xử lý)");
  } finally {
    S.acting = false;
    controls.forEach((button) => {
      button.disabled = false;
    });
    $("#view-verify").setAttribute("aria-busy", "false");
  }
  dirty();
  await refresh(true);
}

function zoom(src) {
  const d = $("#dlg");
  d.className = "wide zoom-dlg";
  d.innerHTML = `<div class="zoom-view"><img src="${src}" alt="Ảnh cảnh báo"><canvas class="zoom-lens" width="200" height="130" hidden></canvas></div>
    <div class="dlg-actions"><button type="button" class="btn" id="zoom-close">Đóng</button></div>`;
  const view = $(".zoom-view", d),
    img = $("img", view),
    lens = $(".zoom-lens", view);
  const mag = 2.6;
  const paint = (e) => {
    if (!img.naturalWidth) return;
    const r = img.getBoundingClientRect();
    const x = e.clientX - r.left,
      y = e.clientY - r.top;
    if (x < 0 || y < 0 || x > r.width || y > r.height) {
      lens.hidden = true;
      return;
    }
    lens.hidden = false;
    const lensWidth = lens.width,
      lensHeight = lens.height,
      vr = view.getBoundingClientRect();
    lens.style.left = `${e.clientX - vr.left - lensWidth / 2}px`;
    lens.style.top = `${e.clientY - vr.top - lensHeight / 2}px`;
    const nx = (x / r.width) * img.naturalWidth,
      ny = (y / r.height) * img.naturalHeight;
    const srcWidth = ((lensWidth / mag) * img.naturalWidth) / r.width;
    const srcHeight = ((lensHeight / mag) * img.naturalHeight) / r.height;
    const srcX = Math.max(
      0,
      Math.min(img.naturalWidth - srcWidth, nx - srcWidth / 2),
    );
    const srcY = Math.max(
      0,
      Math.min(img.naturalHeight - srcHeight, ny - srcHeight / 2),
    );
    const ctx = lens.getContext("2d");
    ctx.clearRect(0, 0, lensWidth, lensHeight);
    ctx.drawImage(
      img,
      srcX,
      srcY,
      srcWidth,
      srcHeight,
      0,
      0,
      lensWidth,
      lensHeight,
    );
    ctx.strokeStyle = "#3ee07a";
    ctx.lineWidth = 3;
    ctx.strokeRect(1.5, 1.5, lensWidth - 3, lensHeight - 3);
  };
  view.onmousemove = paint;
  view.onmouseleave = () => {
    lens.hidden = true;
  };
  $("#zoom-close").onclick = () => d.close();
  d.onclick = (e) => {
    if (e.target === d) d.close();
  };
  d.showModal();
}

function attachAlertMagnifier(view) {
  const img = $(".vimg", view),
    canvas = $(".alert-magnifier", view);
  if (!img || !canvas) return;
  const magnification = 2.5,
    lensWidth = 200,
    lensHeight = 130;
  const ctx = canvas.getContext("2d");
  const hide = () => {
    canvas.hidden = true;
  };
  const paint = (e) => {
    if (!img.complete || !img.naturalWidth) return;
    const imageRect = img.getBoundingClientRect(),
      viewRect = view.getBoundingClientRect();
    const scale = Math.min(
      imageRect.width / img.naturalWidth,
      imageRect.height / img.naturalHeight,
    );
    const renderedWidth = img.naturalWidth * scale,
      renderedHeight = img.naturalHeight * scale;
    const imageLeft = imageRect.left + (imageRect.width - renderedWidth) / 2;
    const imageTop = imageRect.top + (imageRect.height - renderedHeight) / 2;
    const x = e.clientX - imageLeft,
      y = e.clientY - imageTop;
    if (x < 0 || y < 0 || x > renderedWidth || y > renderedHeight) {
      hide();
      return;
    }

    const width = Math.min(lensWidth, renderedWidth),
      height = Math.min(lensHeight, renderedHeight);
    const left = Math.max(0, Math.min(renderedWidth - width, x + 18));
    const top = Math.max(0, Math.min(renderedHeight - height, y + 18));
    const ratioX = img.naturalWidth / renderedWidth,
      ratioY = img.naturalHeight / renderedHeight;
    const sourceWidth = (width / magnification) * ratioX,
      sourceHeight = (height / magnification) * ratioY;
    const sourceX = Math.max(
      0,
      Math.min(img.naturalWidth - sourceWidth, x * ratioX - sourceWidth / 2),
    );
    const sourceY = Math.max(
      0,
      Math.min(img.naturalHeight - sourceHeight, y * ratioY - sourceHeight / 2),
    );
    const dpr = window.devicePixelRatio || 1;
    const canvasWidth = Math.round(viewRect.width * dpr),
      canvasHeight = Math.round(viewRect.height * dpr);
    if (canvas.width !== canvasWidth || canvas.height !== canvasHeight) {
      canvas.width = canvasWidth;
      canvas.height = canvasHeight;
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(
      img,
      sourceX,
      sourceY,
      sourceWidth,
      sourceHeight,
      (imageLeft - viewRect.left + left) * dpr,
      (imageTop - viewRect.top + top) * dpr,
      width * dpr,
      height * dpr,
    );
    ctx.strokeStyle = "#3ee07a";
    ctx.lineWidth = 3 * dpr;
    ctx.strokeRect(
      (imageLeft - viewRect.left + left) * dpr,
      (imageTop - viewRect.top + top) * dpr,
      width * dpr,
      height * dpr,
    );
    canvas.hidden = false;
  };
  view.addEventListener("mousemove", paint);
  view.addEventListener("mouseleave", hide);
  img.addEventListener("load", hide);
}

async function toggleStreamFullscreen(button) {
  const panel = button.closest(".pvid");
  const sourceId = button.closest(".panel").dataset.id;
  try {
    if (document.fullscreenElement === panel) {
      await document.exitFullscreen();
      return;
    }
    if (document.fullscreenElement) await document.exitFullscreen();
    if (S.focusedSource !== sourceId) {
      S.focusedSource = sourceId;
      tickCurrent();
    }
    await panel.requestFullscreen();
  } catch (error) {
    toast(`Không thể đổi chế độ toàn màn hình: ${error.message}`);
  }
}

document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-act]");
  if (!el) return;
  const id = +el.dataset.id,
    a = el.dataset.act;
  if (a === "navigate") return showView(el.dataset.view);
  if (a === "view-source") {
    S.focusedSource = el.dataset.sourceId;
    if ($("#live-filter")) $("#live-filter").value = "all";
    return showView("live");
  }
  if (["dispatch", "delete", "purge", "confirm", "complete"].includes(a))
    return act(a, id);
  if (a === "original-frame") {
    S.selectedEvidence = null;
    dirty();
    tickCurrent();
  } else if (a === "select") {
    S.selected = id;
    S.selectedEvidence = null;
    dirty();
    tickCurrent();
  } else if (a === "evidence-frame") {
    const image = $("#alert-image");
    if (!image) return;
    S.selectedEvidence = {
      alertId: S.selected,
      image: el.dataset.image,
      frame: el.dataset.frame,
    };
    const alert = S.pending.find((item) => item.id === S.selected);
    const evidence = alert?.evidence_images
      ?.map(evidenceRecord)
      .find(
        (item) =>
          `/alert_images/${encodeURIComponent(item.image)}` ===
          el.dataset.image,
      );
    image.src = el.dataset.image;
    image.alt = `Ảnh ${el.dataset.frame}`;
    $("#alert-frame-detections").textContent = detectionInfoText(
      evidence?.detections,
    );
    $("#alert-frame-time").textContent = fmt(evidence?.captured_at);
    const canvas = $(".alert-detections-canvas", $("#view-verify"));
    if (canvas) {
      canvas.detections = evidence?.detections || [];
      paintDetectionOverlay(
        image,
        canvas,
        canvas.detections,
        S.showDetectionLabels,
      );
    }
    $$(".evidence-frame", el.closest(".evidence-strip")).forEach((frame) =>
      frame.classList.toggle("sel", frame === el),
    );
  } else if (a === "silence") {
    S.silencedUntil = Date.now() + 5 * 60000;
    toast("Tắt âm báo trong 5 phút");
  } else if (a === "zoom")
    zoom(el.getAttribute("src") || $("img", el)?.getAttribute("src"));
  else if (a === "fs") toggleStreamFullscreen(el);
  else if (a === "open-alert") {
    S.selected = id;
    showView("verify");
  }
});
document.addEventListener("change", (e) => {
  if (e.target.matches("#live-layout")) {
    S.focusedSource = null;
    $("#streams").style.setProperty(
      "--grid-columns",
      e.target.value === "auto"
        ? "repeat(auto-fit,minmax(min(100%,360px),1fr))"
        : `repeat(${e.target.value},minmax(0,1fr))`,
    );
    tickCurrent();
  }
  if (e.target.matches("#live-filter")) {
    S.focusedSource = null;
    tickCurrent();
  }
  if (e.target.matches("#dashboard-period")) {
    S.dashboardDays = Number(e.target.value);
    refresh(true);
  }
  if (e.target.matches("#show-detection-labels")) {
    S.showDetectionLabels = e.target.checked;
    refreshDetectionOverlays($("#view-verify"));
  }
});

function cameraDisplayWidth(image) {
  const rect = image.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return null;
  // object-fit: contain can leave horizontal borders, especially in fullscreen.
  const width = image.naturalWidth;
  const height = image.naturalHeight;
  return Math.max(
    160,
    Math.round(
      width > 0 && height > 0
        ? Math.min(rect.width, (rect.height * width) / height)
        : rect.width,
    ),
  );
}

function updateCameraFeed(image, force = false) {
  const displayWidth = cameraDisplayWidth(image);
  // A hidden view has no usable dimensions. Keep its last valid size.
  if (displayWidth === null) return;
  const simple = String(!!S.simplified);
  if (
    !force &&
    image.dataset.simple === simple &&
    Math.abs(Number(image.dataset.displayWidth) - displayWidth) < 2
  )
    return;
  image.dataset.simple = simple;
  image.dataset.displayWidth = displayWidth;
  image.src =
    image.src.split("?")[0] +
    `?simple=${S.simplified ? 1 : 0}&display_width=${displayWidth}&ui=${Date.now()}`;
}

const cameraFeedResizeObserver = new ResizeObserver((entries) => {
  for (const { target } of entries) {
    if (!target.isConnected) cameraFeedResizeObserver.unobserve(target);
    else updateCameraFeed(target);
  }
});

function applySimplifiedView() {
  const root = $("#view-live"),
    streams = $("#streams");
  if (!root || !streams) return;
  const enabled = !!S.simplified;
  root.classList.toggle("simplified-live", enabled);
  document.body.classList.toggle(
    "simplified-shell",
    S.view === "live" && enabled,
  );
  if (enabled && S.view === "live")
    document.body.classList.remove("mobile-nav-open");
  $$("[data-live-mode]").forEach((button) => {
    const active = (button.dataset.liveMode === "simple") === enabled;
    button.setAttribute("aria-pressed", String(active));
    button.classList.toggle("active", active);
  });
  $$("video.demo-video", streams).forEach((video) => {
    video.controls = false;
    video.tabIndex = enabled ? 0 : -1;
    if (enabled)
      video.setAttribute("aria-label", "Bấm để phát hoặc tạm dừng video");
    else video.removeAttribute("aria-label");
  });
  $$("img[src*='/video_feed/']", streams).forEach((image) => {
    updateCameraFeed(image);
  });
}

document.addEventListener("click", (event) => {
  const mode = event.target.closest("[data-live-mode]");
  if (!mode) return;
  S.simplified = mode.dataset.liveMode === "simple";
  if (S.simplified) S.focusedSource = null;
  if (S.view !== "live") showView("live");
  tickCurrent();
  applySimplifiedView();
  setLiveExpanded(false);
});
document.addEventListener("click", (e) => {
  if (e.target.closest("#live-play-all")) {
    const videos = $$(".demo-video", $("#view-live"));
    if (videos.length && videos.every((video) => !video.paused)) {
      videos.forEach((video) => video.pause());
    } else {
      Promise.allSettled(
        videos.map((video) => {
          if (video.ended) video.currentTime = 0;
          return video.play();
        }),
      ).then((results) => {
        const failures = results.filter(
          (result) => result.status === "rejected",
        );
        if (failures.length) {
          toast(
            `Không thể phát ${failures.length} video. Kiểm tra định dạng hoặc nguồn video.`,
          );
        }
        updateLivePlaybackButton();
      });
    }
    updateLivePlaybackButton();
  }
  if (e.target.closest("#live-grid-view")) {
    S.focusedSource = null;
    tickCurrent();
  }
});
document.addEventListener("click", (e) => {
  const panel = e.target.closest(".pvid");
  if (!panel || e.target.closest("button")) return;
  const id = panel.closest(".panel").dataset.id;
  if (S.focusedSource !== id) {
    S.focusedSource = id;
    tickCurrent();
  }
});
document.addEventListener("click", (e) => {
  const header = e.target.closest(".pbar[data-source-id]");
  if (!header) return;
  const id = header.dataset.sourceId;
  if (S.focusedSource !== id) {
    S.focusedSource = id;
    tickCurrent();
  }
});
document.addEventListener("keydown", (e) => {
  const header = e.target.closest(".pbar[data-source-id]");
  if (!header || !["Enter", " "].includes(e.key)) return;
  e.preventDefault();
  const id = header.dataset.sourceId;
  if (S.focusedSource !== id) {
    S.focusedSource = id;
    tickCurrent();
  }
});
document.addEventListener("dblclick", (e) => {
  const panel = e.target.closest(".pvid");
  if (!panel) return;
  e.preventDefault();
});
document.addEventListener("fullscreenchange", () => {
  $$(".fs-btn").forEach((button) => {
    const isFullscreen = document.fullscreenElement === button.closest(".pvid");
    button.title = isFullscreen ? "Thoát toàn màn hình" : "Toàn màn hình";
    button.setAttribute("aria-label", button.title);
  });
});
document.addEventListener("keydown", (e) => {
  if (
    ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName) ||
    !["verify", "live"].includes(S.view)
  )
    return;
  const a = current();
  if (!a) return;
  if ($("#dlg").open || S.view !== "verify") return;
  if (e.key === "d" && ["pending", "confirmed"].includes(a.status))
    act("dispatch", a.id);
  else if (e.key === "x" && a.status === "pending") act("delete", a.id);
});

const dirty = () => {
  delete S.sigs.alarm;
  delete S.sigs.verify;
};
const tickCurrent = () => (VIEWS[S.view] || {}).tick?.(S.view);

const VIEWS = {};

function updateLivePlaybackButton() {
  const button = $("#live-play-all");
  if (!button) return;
  const videos = $$(".demo-video", $("#view-live"));
  const allPlaying =
    videos.length > 0 && videos.every((video) => !video.paused);
  button.disabled = videos.length === 0;
  button.textContent = allPlaying ? "Tạm dừng video" : "Phát tất cả video";
  button.setAttribute("aria-pressed", String(allPlaying));
}

const dashboardCard = (title, value, icon, tone, action, detail = "") =>
  `<button class="metric-card ${tone}" data-act="navigate" data-view="${action}"><span class="metric-top">${title}<span class="metric-icon">${svg(icon)}</span></span><strong>${value}</strong>${detail ? `<span class="metric-detail">${detail}</span>` : ""}</button>`;

VIEWS.dashboard = {
  tick() {
    const st = S.stats;
    if (!st) return;
    const sig = JSON.stringify([st, S.sources, S.pending]);
    if (sig === S.sigs.dash) return;
    S.sigs.dash = sig;
    const online = S.sources.filter((s) => s.online && s.enabled).length;
    const offline = S.sources.filter((s) => s.enabled && !s.online);
    const disabled = S.sources.filter((s) => !s.enabled).length;
    const active = st.pending + st.confirmed + st.dispatched;
    const colors = {
      active: "#4186d9",
      completed: "#24a782",
      deleted: "#9caabc",
    };
    const totals = st.per_day.map(
      (d) => d.pending + d.confirmed + d.dispatched + d.completed + d.deleted,
    );
    const max = Math.max(1, ...totals);
    const plotX = 42,
      plotW = 656,
      plotBottom = 183,
      plotHeight = 149;
    const step = plotW / st.per_day.length,
      barWidth = Math.min(32, step * 0.55);
    const axis = [0, 0.5, 1]
      .map((ratio) => {
        const y = plotBottom - ratio * plotHeight;
        return `<line x1="${plotX}" y1="${y}" x2="${plotX + plotW}" y2="${y}" class="chart-grid"/><text x="30" y="${y + 4}" class="chart-label" text-anchor="end">${Math.round(max * ratio)}</text>`;
      })
      .join("");
    const bars = st.per_day
      .map((d, index) => {
        let y = plotBottom;
        const x = plotX + step * index + (step - barWidth) / 2;
        const parts = [
          [d.deleted, colors.deleted],
          [d.completed, colors.completed],
          [d.pending + d.confirmed + d.dispatched, colors.active],
        ];
        const date = d.date.split("-").reverse().join("/");
        const rectangles = parts
          .map(([count, color]) => {
            const height = (count / max) * plotHeight;
            y -= height;
            return height
              ? `<rect x="${x}" y="${y}" width="${barWidth}" height="${height}" rx="2" fill="${color}"/>`
              : "";
          })
          .join("");
        const label =
          st.days === 7 || index % 5 === 0 || index === st.per_day.length - 1
            ? `<text x="${x + barWidth / 2}" y="207" class="chart-label" text-anchor="middle">${date}</text>`
            : "";
        return `<g><title>${date}: ${totals[index]} cảnh báo</title>${rectangles}${label}</g>`;
      })
      .join("");
    const weaponEntries = Object.entries(st.by_weapon)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);
    const weaponMax = Math.max(1, ...weaponEntries.map(([, n]) => n));
    const weapons =
      weaponEntries
        .map(
          ([label, count]) =>
            `<div class="rank-row"><span>${esc(className(label))}</span><b>${count}</b><div class="rank-track"><i style="width:${(count / weaponMax) * 100}%"></i></div></div>`,
        )
        .join("") || '<div class="empty">Chưa có dữ liệu</div>';
    const sourceMax = Math.max(
      1,
      ...st.by_source.map((source) => source.count),
    );
    const rankedSources =
      st.by_source
        .map(
          (source) =>
            `<div class="rank-row"><span>${esc(source.source_name)}</span><b>${source.count}</b><div class="rank-track"><i style="width:${(source.count / sourceMax) * 100}%"></i></div></div>`,
        )
        .join("") || '<div class="empty">Chưa có dữ liệu</div>';
    const healthSources = [...S.sources]
      .sort(
        (a, b) =>
          Number(!!b.enabled && !b.online) - Number(!!a.enabled && !a.online),
      )
      .slice(0, 4);
    const health =
      healthSources
        .map(
          (source) =>
            `<button class="health-row" data-act="view-source" data-source-id="${esc(source.id)}"><span class="source-symbol">${svg(source.type)}</span><span class="health-name"><b>${esc(source.name)}</b><small>${esc(source.location || TYPE_NAME[source.type])}</small></span><span class="health-status ${!source.enabled ? "muted" : source.online ? "healthy" : "unhealthy"}"><i></i>${!source.enabled ? "Đang tắt" : source.online ? "Kết nối" : "Mất kết nối"}</span></button>`,
        )
        .join("") || '<div class="empty">Chưa có thiết bị</div>';
    $("#view-dashboard").innerHTML =
      `<header class="page-heading dashboard-heading"><h2>Tổng quan</h2><label class="compact-field">Thống kê<select id="dashboard-period"><option value="7" ${st.days === 7 ? "selected" : ""}>7 ngày</option><option value="30" ${st.days === 30 ? "selected" : ""}>30 ngày</option></select></label></header>
      <div class="dashboard-metrics">
        ${dashboardCard("Cảnh báo hôm nay", st.today, "bell", "blue", "verify")}
        ${dashboardCard("Chờ xác minh", st.pending, "verify", st.pending ? "amber" : "blue", "verify")}
        ${dashboardCard("Đang xử lý", active, "history", "violet", "verify")}
        ${dashboardCard("Nguồn kết nối", `${online}<span>/${S.sources.length}</span>`, "camera", offline.length ? "amber" : "green", "live", `${offline.length} mất kết nối · ${disabled} đang tắt`)}
      </div>
      <div class="dashboard-body">
        <section class="dashboard-card trend-card"><header><h3>Xu hướng cảnh báo</h3><span class="count-badge">${st.period_total} cảnh báo</span></header>
          <svg class="trend-chart" viewBox="0 0 720 220" role="img" aria-label="Cảnh báo theo ngày trong ${st.days} ngày"><title>Xu hướng cảnh báo ${st.days} ngày</title>${axis}${bars}</svg>
          <div class="chart-legend"><span><i style="background:${colors.active}"></i>Đang xử lý</span><span><i style="background:${colors.completed}"></i>Hoàn tất</span><span><i style="background:${colors.deleted}"></i>Nhận diện sai</span></div>
        </section>
        <section class="dashboard-card health-card"><header><h3>Trạng thái nguồn</h3><button class="text-action" data-act="navigate" data-view="live">Xem tất cả →</button></header><div class="health-list">${health}</div>
          ${st.notification_failures ? `<button class="delivery-issue" data-act="navigate" data-view="verify">${svg("bell")} ${st.notification_failures} cảnh báo gửi tin thất bại →</button>` : ""}
        </section>
        <section class="dashboard-card workload-card"><header><h3>Cảnh báo đang xử lý</h3><button class="text-action" data-act="navigate" data-view="verify">Xem tất cả →</button></header><div class="dashboard-queue">${alertQueue(S.pending.slice(0, 4), true)}</div></section>
        <section class="dashboard-card ranking-card"><header><h3>Vật thể phát hiện</h3><span class="period-label">${st.days} ngày</span></header>${weapons}</section>
        <section class="dashboard-card ranking-card"><header><h3>Nguồn phát sinh cảnh báo</h3><span class="period-label">${st.days} ngày</span></header>${rankedSources}</section>
      </div>`;
  },
};

const statBits = (s) => {
  const t = s.telemetry || {},
    b = [];
  if (t.temp != null) b.push(`${t.temp}°C`);
  if (t.wind != null) b.push(`gió ${t.wind} m/s`);
  if (t.sats != null) b.push(`${t.sats} sat`);
  if (t.signal != null) b.push(`sóng ${t.signal}%`);
  if (t.battery != null) b.push(`pin ${t.battery}%`);
  if (t.voltage != null) b.push(`${t.voltage} V`);
  if (t.flight_time) b.push(`${t.flight_time}`);
  if (s.resolution) b.push(s.resolution);
  if (s.online && s.fps) b.push(`${Math.round(s.fps)} fps`);
  return b.map((x) => `<span>${esc(x)}</span>`).join("");
};
const hudText = (s) => {
  const t = s.telemetry || {},
    l = [];
  if (t.lat != null && t.lon != null) l.push(`LAT: ${t.lat}  LON: ${t.lon}`);
  if (t.altitude != null) l.push(`ALT: ${t.altitude} m`);
  if (t.speed != null) l.push(`SPD: ${t.speed} m/s`);
  if (t.heading != null) l.push(`HDG: ${t.heading}°`);
  return l.join("\n");
};

VIEWS.live = {
  show() {
    if (!$("#streams")) {
      $("#view-live").innerHTML = `<div class="live">
        <header class="page-heading"><h2>Giám sát trực tiếp</h2><div class="live-toolbar">
          <label class="compact-field source-search">Tìm camera<input id="live-search" type="search" placeholder="Nhập tên camera…" autocomplete="off"></label>
          <label class="compact-field">Nguồn<select id="live-filter"><option value="all">Tất cả</option><option value="camera">Camera</option><option value="drone">Drone</option><option value="robot">Robot</option><option value="online">Đang kết nối</option><option value="offline">Chưa kết nối</option></select></label>
          <label class="compact-field">Bố cục<select id="live-layout"><option value="auto">Tự động</option><option value="1">1 cột</option><option value="2">2 cột</option><option value="3">3 cột</option><option value="4">4 cột</option></select></label>
          <button class="btn sm" id="live-play-all" disabled>Phát tất cả video</button>
          <button class="btn sm" id="live-grid-view" hidden>Trở về dạng lưới</button>
        </div></header><div class="live-workspace"><div class="streams" id="streams"></div></div></div>`;
      S.liveStreamsSignature = null;
      applySettings();
    }
  },
  tick() {
    const box = $("#streams");
    if (!box) return;
    const filter = $("#live-filter").value;
    const query = $("#live-search").value;
    const visibleSources = S.sources.filter(
      (s) =>
        matchesSourceName(s.name, query) &&
        (filter === "all" ||
          filter === s.type ||
          (filter === "online" && s.online) ||
          (filter === "offline" && !s.online)),
    );
    const sig = JSON.stringify(
      S.sources.map((s) => [
        s.id,
        s.enabled,
        s.name,
        s.url,
        s.demo_video,
        s.location,
      ]),
    );
    if (sig !== S.liveStreamsSignature) {
      S.liveStreamsSignature = sig;
      cameraFeedResizeObserver.disconnect();
      box.innerHTML =
        S.sources
          .map(
            (s) => `<div class="panel" id="p-${s.id}" data-id="${esc(s.id)}">
        <div class="pbar${s.demo_video ? " demo-pbar" : ""}" data-source-id="${esc(s.id)}" role="button" tabindex="0" aria-label="Phóng to màn hình ${esc(s.name)}"><div class="camera-heading"><span class="dot"></span><b>${esc(s.name)}</b><span class="source-location">${esc(s.location || "Chưa khai báo vị trí")}</span><span class="mode none">${s.type}</span><span class="pstats"></span></div>${
          s.demo_video
            ? `
          <div class="scan-progress" role="progressbar" aria-label="Tiến trình xử lý video" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div class="scan-progress-track"><i></i></div><span class="scan-progress-label">Chưa xử lý</span><b class="scan-percent">0%</b></div>
          <div class="demo-tools"><div class="video-versions" role="group" aria-label="Phiên bản video"><button type="button" class="video-version active" data-version="original" aria-pressed="true">Video gốc</button><button type="button" class="video-version" data-version="detected" aria-pressed="false" disabled>Đã nhận diện</button></div><button type="button" class="btn sm primary process-video">Xử lý video</button></div>`
            : ""
        }</div>
        <div class="pvid"><div class="tracking-stage" data-source="${esc(s.id)}">${
          s.demo_video
            ? `<video class="demo-video" src="/source_video/${encodeURIComponent(s.id)}" playsinline loop preload="metadata"></video>`
            : `<img src="/video_feed/${encodeURIComponent(s.id)}" alt="${esc(s.name)}">`
        }
          <canvas class="tracking-overlay"></canvas></div>
          ${s.demo_video ? `<div class="demo-error" role="status"></div>` : ""}
          <div class="hud"></div>
          ${s.demo_video ? `<div class="video-controls" role="group" aria-label="Điều khiển video"><button type="button" class="player-play" aria-label="Phát video">▶</button><span class="player-time">0:00 / 0:00</span><input class="player-seek" type="range" min="0" max="0" step="0.01" value="0" aria-label="Tua video"><button type="button" class="player-mute" aria-label="Tắt âm">🔊</button><input class="player-volume" type="range" min="0" max="1" step="0.05" value="1" aria-label="Âm lượng"><div class="live-tag"><i></i><span>VIDEO THỬ NGHIỆM</span></div><button class="fs-btn" data-act="fs" title="Toàn màn hình" aria-label="Toàn màn hình gồm nhận diện">&#x26F6;</button></div>` : `<div class="live-tag"><i></i><span>LIVE</span></div><button class="fs-btn" data-act="fs" title="Toàn màn hình">&#x26F6;</button>`}</div>
        </div>`,
          )
          .join("") ||
        '<div class="empty"><strong>Chưa có thiết bị</strong>Vào Cameras, Drones hoặc Robots để thêm.</div>';
      $$("img[src*='/video_feed/']", box).forEach((image) => {
        cameraFeedResizeObserver.observe(image);
        image.addEventListener("load", () => updateCameraFeed(image));
      });
      S.sources
        .filter((s) => s.demo_video)
        .forEach((s) => {
          const panel = $(`#p-${s.id}`);
          const video = $(".demo-video", panel);
          connectDemoVideo(video, panel, s.id);
        });
    }
    updateLivePlaybackButton();
    if (!visibleSources.some((s) => s.id === S.focusedSource))
      S.focusedSource = null;
    $("#live-grid-view").hidden = !S.focusedSource;
    box.classList.toggle("focused", !!S.focusedSource);
    box.classList.toggle(
      "single-focused",
      !!S.focusedSource && visibleSources.length === 1,
    );
    if (S.focusedSource) {
      box.style.setProperty(
        "--focus-height",
        `${Math.max(320, innerHeight - box.getBoundingClientRect().top - 20)}px`,
      );
    }
    const miniCount = Math.max(1, visibleSources.length - 1);
    box.style.setProperty("--mini-count", miniCount);
    S.sources.forEach((s) => {
      const p = $(`#p-${s.id}`);
      if (!p) return;
      $(".source-location", p)?.classList.toggle(
        "unspecified",
        !String(s.location || "").trim(),
      );
      p.hidden = !visibleSources.some((source) => source.id === s.id);
      const isMain = s.id === S.focusedSource;
      p.classList.toggle("focus-main", isMain);
      if (S.focusedSource) {
        p.style.gridColumn = isMain
          ? visibleSources.length === 1
            ? "1"
            : "2"
          : "1";
        p.style.gridRow = isMain
          ? `1 / span ${miniCount}`
          : String(
              visibleSources
                .filter((other) => other.id !== S.focusedSource)
                .findIndex((other) => other.id === s.id) + 1,
            );
      } else {
        p.style.gridColumn = "";
        p.style.gridRow = "";
      }
    });
    let emptyFilter = $(".filter-empty", box);
    if (!emptyFilter) {
      emptyFilter = document.createElement("div");
      emptyFilter.className = "filter-empty empty";
      emptyFilter.textContent = "Không có nguồn phù hợp với bộ lọc.";
      box.append(emptyFilter);
    }
    emptyFilter.hidden = !S.sources.length || visibleSources.length > 0;
    S.sources.forEach((s) => {
      const p = $(`#p-${s.id}`);
      if (!p) return;
      $(".dot", p).classList.toggle("on", s.online);
      const t = s.telemetry || {},
        mode = $(".mode", p);
      mode.textContent = t.mode || TYPE_NAME[s.type] || s.type;
      mode.classList.toggle("none", !t.mode);
      const stats = statBits(s),
        ps = $(".pstats", p);
      if (ps.dataset.v !== stats) {
        ps.innerHTML = stats;
        ps.dataset.v = stats;
      }
      $(".hud", p).textContent = hudText(s);
      $(".live-tag", p).classList.toggle("off", !s.online);
      $(".live-tag span", p).textContent = !s.enabled
        ? "ĐANG TẮT"
        : !s.online
          ? "MẤT KẾT NỐI"
          : s.demo_video
            ? "VIDEO THỬ NGHIỆM"
            : "TRỰC TIẾP";
    });
    applySimplifiedView();
  },
};

const demoVideoStates = new WeakMap();

function cachedFrameIndex(frames, time) {
  let low = 0,
    high = frames.length - 1,
    result = -1;
  while (low <= high) {
    const middle = (low + high) >>> 1;
    if (frames[middle].time <= time + 0.0001) {
      result = middle;
      low = middle + 1;
    } else high = middle - 1;
  }
  return result;
}

function connectDemoVideo(video, panel, sourceId) {
  const canvas = $(".tracking-overlay", panel),
    status = $(".demo-error", panel);
  const state = {
    timeline: null,
    version: "original",
    animationFrame: null,
    eventBusy: false,
    lastEvent: -1,
    eventAt: 0,
  };
  demoVideoStates.set(video, state);
  const controls = $(".video-controls", panel);
  const formatTime = (value) => {
    const seconds = Number.isFinite(value) ? Math.max(0, Math.floor(value)) : 0;
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  };
  const updateControls = () => {
    if (!controls) return;
    const play = $(".player-play", controls),
      seek = $(".player-seek", controls);
    play.textContent = video.paused ? "▶" : "❚❚";
    play.setAttribute(
      "aria-label",
      video.paused ? "Phát video" : "Tạm dừng video",
    );
    seek.max = Number.isFinite(video.duration) ? video.duration : 0;
    seek.value = video.currentTime || 0;
    seek.disabled = !Number.isFinite(video.duration);
    $(".player-time", controls).textContent =
      `${formatTime(video.currentTime)} / ${formatTime(video.duration)}`;
    $(".player-mute", controls).textContent =
      video.muted || video.volume === 0 ? "🔇" : "🔊";
    $(".player-mute", controls).setAttribute(
      "aria-label",
      video.muted ? "Bật âm" : "Tắt âm",
    );
    $(".player-volume", controls).value = video.muted ? 0 : video.volume;
  };
  if (controls) {
    $(".player-play", controls).onclick = () => {
      if (video.paused)
        video.play().catch((error) => {
          status.textContent = error.message;
        });
      else video.pause();
    };
    $(".player-seek", controls).oninput = (event) => {
      if (Number.isFinite(video.duration))
        video.currentTime = Math.min(
          video.duration,
          Number(event.target.value),
        );
    };
    $(".player-mute", controls).onclick = () => {
      video.muted = !video.muted;
    };
    $(".player-volume", controls).oninput = (event) => {
      video.volume = Number(event.target.value);
      video.muted = false;
    };
    for (const event of [
      "loadedmetadata",
      "durationchange",
      "timeupdate",
      "play",
      "pause",
      "ended",
      "volumechange",
    ])
      video.addEventListener(event, updateControls);
    updateControls();
  }
  const endpoint = `/api/sources/${encodeURIComponent(sourceId)}`;
  const rescan = $(".process-video", panel),
    tools = $(".demo-tools", panel);
  const progressBar = $(".scan-progress", panel);
  const versions = [...panel.querySelectorAll(".video-version")];
  const setProgress = (value, label) => {
    value = Math.max(0, Math.min(100, Number(value) || 0));
    progressBar.setAttribute("aria-valuenow", value);
    $("i", progressBar).style.width = `${value}%`;
    $(".scan-percent", progressBar).textContent = `${value}%`;
    $(".scan-progress-label", progressBar).textContent = label;
  };
  tools.addEventListener("click", (event) => event.stopPropagation());
  tools.addEventListener("keydown", (event) => event.stopPropagation());
  progressBar.addEventListener("click", (event) => event.stopPropagation());
  const selectVersion = (version) => {
    state.version = version;
    versions.forEach((button) => {
      const active = button.dataset.version === version;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    state.lastEvent = -1;
    render(video.currentTime);
  };
  versions.forEach((button) => {
    button.onclick = () => selectVersion(button.dataset.version);
  });
  const render = (time) => {
    if (!state.timeline || state.version === "original")
      return clearDemoDetections(canvas);
    const index = cachedFrameIndex(state.timeline.frames, time);
    if (index < 0) return clearDemoDetections(canvas);
    const frame = state.timeline.frames[index];
    const detections = frame.detections.filter(
      (item) => S.settings[`${item.label}_enabled`] !== false,
    );
    drawDemoDetections(
      canvas,
      detections,
      state.timeline.width,
      state.timeline.height,
    );
    // Use saved detections for alerts; the server never runs inference on playback.
    if (
      !video.paused &&
      !video.seeking &&
      !state.eventBusy &&
      index !== state.lastEvent &&
      performance.now() - state.eventAt >= 250
    ) {
      state.eventBusy = true;
      state.lastEvent = index;
      state.eventAt = performance.now();
      fetch(`${endpoint}/playback-event`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ index }),
      })
        .catch(() => {})
        .finally(() => {
          state.eventBusy = false;
        });
    }
  };
  const animate = (now, metadata) => {
    state.animationFrame = null;
    if (!video.isConnected) return;
    render(metadata?.mediaTime ?? video.currentTime);
    if (!video.paused && !video.ended) schedule();
  };
  const schedule = () => {
    if (state.animationFrame !== null) return;
    state.animationFrame = video.requestVideoFrameCallback
      ? video.requestVideoFrameCallback(animate)
      : requestAnimationFrame(animate);
  };
  const cancel = () => {
    if (state.animationFrame === null) return;
    if (video.cancelVideoFrameCallback)
      video.cancelVideoFrameCallback(state.animationFrame);
    else cancelAnimationFrame(state.animationFrame);
    state.animationFrame = null;
  };
  const poll = async () => {
    if (!video.isConnected) return;
    try {
      const response = await fetch(`${endpoint}/analysis`);
      if (response.status === 404)
        throw new Error(
          "App chưa nạp chức năng xử lý video hoặc nguồn đã bị xóa. Khởi động lại app bằng run.bat rồi tải lại trang.",
        );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const progress = await response.json();
      if (progress.state === "ready") {
        const result = await fetch(`${endpoint}/analysis?results=1`);
        if (!result.ok) throw new Error(`HTTP ${result.status}`);
        const timeline = await result.json();
        if (!timeline.frames) throw new Error("Kết quả video chưa sẵn sàng");
        state.timeline = timeline;
        versions.find(
          (button) => button.dataset.version === "detected",
        ).disabled = false;
        rescan.disabled = false;
        rescan.textContent = "Xử lý lại";
        setProgress(100, "Hoàn tất");
        status.textContent = "";
        render(video.currentTime);
        return;
      }
      if (progress.state === "error")
        throw new Error(progress.error || "Không thể xử lý video");
      if (progress.state === "idle") {
        setProgress(0, "Chưa xử lý");
        rescan.disabled = false;
        return;
      }
      rescan.disabled = true;
      setProgress(
        progress.progress,
        progress.state === "queued" ? "Đang chờ" : "Đang xử lý",
      );
      setTimeout(poll, 1000);
    } catch (error) {
      status.textContent = `Lỗi xử lý video: ${error.message}`;
      setProgress(0, "Có lỗi");
      rescan.disabled = false;
    }
  };
  rescan.onclick = async () => {
    selectVersion("original");
    state.timeline = null;
    versions.find((button) => button.dataset.version === "detected").disabled =
      true;
    clearDemoDetections(canvas);
    rescan.disabled = true;
    setProgress(0, "Đang gửi yêu cầu");
    status.textContent = "";
    try {
      const response = await fetch(`${endpoint}/analysis`, { method: "POST" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      poll();
    } catch (error) {
      status.textContent = error.message;
      rescan.disabled = false;
    }
  };
  video.controls = false;
  const toggleSimplePlayback = () => {
    if (!panel.closest(".simplified-live")) return;
    if (video.paused)
      video
        .play()
        .catch((error) => toast(`Không thể phát video: ${error.message}`));
    else video.pause();
  };
  video.addEventListener("click", toggleSimplePlayback);
  video.addEventListener("keydown", (event) => {
    if (
      panel.closest(".simplified-live") &&
      [" ", "Enter"].includes(event.key)
    ) {
      event.preventDefault();
      event.stopPropagation();
      toggleSimplePlayback();
    }
  });
  video.addEventListener("play", () => {
    schedule();
    updateLivePlaybackButton();
  });
  video.addEventListener("pause", () => {
    cancel();
    render(video.currentTime);
    updateLivePlaybackButton();
  });
  video.addEventListener("seeking", () => {
    clearDemoDetections(canvas);
    state.lastEvent = -1;
  });
  video.addEventListener("seeked", () => {
    render(video.currentTime);
    if (!video.paused) schedule();
  });
  video.addEventListener("loadedmetadata", () => render(video.currentTime));
  video.addEventListener("ended", () => {
    cancel();
    render(video.currentTime);
    updateLivePlaybackButton();
  });
  const overlayResize = new ResizeObserver(() => {
    if (!video.isConnected) {
      overlayResize.disconnect();
      return;
    }
    render(video.currentTime);
  });
  overlayResize.observe(canvas);
  poll();
}

function drawDemoDetections(
  canvas,
  detections,
  width = canvas.width,
  height = canvas.height,
) {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const pixelWidth = Math.max(1, Math.round(rect.width * dpr));
  const pixelHeight = Math.max(1, Math.round(rect.height * dpr));
  if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
    canvas.width = pixelWidth;
    canvas.height = pixelHeight;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const scale = Math.min(
    canvas.width / Math.max(1, width),
    canvas.height / Math.max(1, height),
  );
  drawAnnotations(
    ctx,
    detections,
    width,
    height,
    scale,
    scale,
    (canvas.width - width * scale) / 2,
    (canvas.height - height * scale) / 2,
    dpr,
  );
}

function clearDemoDetections(canvas) {
  canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
}

function alertLocation(alert) {
  const parts = [alert.location, S.settings.site_name, S.settings.site_address]
    .map((value) => String(value || "").trim())
    .filter(Boolean);
  return [...new Set(parts)].join(" · ") || "Chưa khai báo địa điểm hệ thống";
}

VIEWS.verify = {
  tick() {
    const a = current(),
      el = $("#view-verify");
    if (document.activeElement?.matches(".note")) return;
    const sig = JSON.stringify([
      S.pending,
      S.selected,
      S.settings.site_name,
      S.settings.site_address,
      S.bulkMode,
      [...(S.bulkSelected || [])],
      S.bulkBusy,
    ]);
    if (sig === S.sigs.verify) return;
    S.sigs.verify = sig;
    if (!a) {
      el.innerHTML = `<h2>Xử lý cảnh báo</h2><div class="box empty"><strong>Không có cảnh báo chờ xử lý</strong></div>`;
      return;
    }

    const selectedImage =
      S.selectedEvidence?.alertId === a.id ? S.selectedEvidence.image : null;
    const mainImage = selectedImage || imgUrl(a);
    const mainLabel =
      S.selectedEvidence?.alertId === a.id
        ? `Ảnh ${S.selectedEvidence.frame}`
        : "Ảnh phát hiện ban đầu";
    const selectedEvidence = (a.evidence_images || [])
      .map(evidenceRecord)
      .find(
        (entry) =>
          `/alert_images/${encodeURIComponent(entry.image)}` === selectedImage,
      );
    const imageDetections =
      selectedEvidence?.detections ??
      (a.detections?.length ? a.detections : a.weapons);
    const imageCapturedAt = selectedEvidence?.captured_at || a.created_at;
    el.innerHTML = `<header class="page-heading"><h2>Xử lý cảnh báo</h2><div class="bulk-alert-toolbar">${S.bulkMode ? `<span>Đã chọn ${S.bulkSelected?.size || 0}</span><button class="btn sm" data-bulk="all" ${S.bulkBusy ? "disabled" : ""}>Chọn tất cả</button><button class="btn sm ${S.bulkMode === "purge" ? "bulk-purge" : "bulk-false"}" data-bulk="submit" ${S.bulkBusy || !S.bulkSelected?.size ? "disabled" : ""}>${S.bulkBusy ? "Đang thực hiện…" : S.bulkMode === "purge" ? "Xóa đã chọn" : "Đánh dấu sai đã chọn"}</button><button class="btn sm" data-bulk="cancel" ${S.bulkBusy ? "disabled" : ""}>Hủy chọn</button>` : `<button class="btn sm" data-bulk="purge">Xóa hàng loạt</button><button class="btn sm" data-bulk="false">Đánh dấu sai hàng loạt</button>`}<span class="count-badge">${S.pending.length} đang xử lý</span></div></header>
      <div class="verify-workspace">
        <aside class="alert-queue"><h3>Hàng chờ xử lý</h3>${alertQueue(S.pending)}</aside>
        <section class="evidence-panel"><div class="vtitle">Cảnh báo #${a.id} · ${esc(a.source_name)}</div>
          <div class="alert-image-view">
            <img id="alert-image" class="vimg" src="${mainImage}" alt="${mainLabel}">
            <canvas class="alert-detections-canvas"></canvas><canvas class="alert-magnifier" hidden></canvas></div>
          <div class="evidence-tools"><label class="detection-label-toggle"><span>Hiển thị nhận diện AI</span>
            <input id="show-detection-labels" type="checkbox" role="switch" ${S.showDetectionLabels ? "checked" : ""}><span class="toggle-slider" aria-hidden="true"></span></label>
            <button class="btn sm" data-act="original-frame">Ảnh ban đầu</button></div>
          <div class="box alert-frame-info"><strong id="alert-frame-detections">${detectionInfo(imageDetections)}</strong><span class="hint" id="alert-frame-time">${fmt(imageCapturedAt)}</span></div>
          ${evidenceStrip(a, selectedImage)}
        </section>
        <aside class="review-panel"><span class="status ${a.status}">${statusName(a.status)}</span>
          <h3>Thông tin cảnh báo #${a.id}</h3><dl class="facts"><dt>Hung khí</dt><dd>${chips(a)}</dd>
            <dt>Độ tin cậy</dt><dd>${Math.round(a.max_conf * 100)}%</dd>
            <dt>Nguồn</dt><dd>${esc(a.source_name)}</dd><dt>Vị trí</dt><dd>${esc(alertLocation(a))}</dd>
            <dt>Phát hiện lúc</dt><dd>${fmt(a.created_at)}</dd></dl>
          ${a.notification_info ? `<div class="notification-result" role="status">${esc(a.notification_info)}</div>` : ""}
          <div class="review-actions">${alertActions(a)}</div>
        </aside>
      </div>`;
    attachAlertMagnifier($(".alert-image-view", el));
    setupAlertDetectionOverlays(el, a, imageDetections);
  },
};

VIEWS.history = {
  async show() {
    const el = $("#view-history");
    el.innerHTML = `<div class="toolbar"><h2 class="grow" style="margin:0">Lịch sử xử lý</h2>
      <select id="hf" aria-label="Lọc trạng thái cảnh báo"><option value="">Tất cả</option><option value="pending">Chờ xác minh</option><option value="processed">Đã xử lý</option><option value="confirmed">Đã xác nhận</option><option value="dispatched">Đã gửi thông báo</option><option value="completed">Đã hoàn tất</option><option value="deleted">Nhận diện sai</option></select><a class="btn sm" id="export-history-csv">Xuất CSV</a><a class="btn sm primary" id="export-history-zip">Xuất CSV + ảnh (ZIP)</a></div><p class="hint">CSV lưu kết quả xử lý và đường dẫn ảnh. Chọn ZIP để tải kèm ảnh gốc và bằng chứng; nhãn AI được giữ riêng với kết luận của nhân viên.</p><div id="hbody"></div>`;
    const excel = document.createElement("a");
    excel.id = "export-history-excel";
    excel.className = "btn sm primary";
    excel.textContent = "Xuất Excel kèm ảnh";
    $("#export-history-csv").before(excel);
    $(".hint", el).textContent =
      "Excel nhúng ảnh gốc và ảnh có box cùng kết quả xử lý. ZIP giữ ảnh gốc đầy đủ độ phân giải; CSV chỉ lưu đường dẫn.";
    const rows = await api("/api/alerts?status=all");
    const draw = () => {
      const f = $("#hf").value,
        list = rows.filter(
          (a) =>
            !f || (f === "processed" ? a.status !== "pending" : a.status === f),
        );
      $("#export-history-csv").href =
        `/api/alerts/export?status=${encodeURIComponent(f || "all")}&format=csv`;
      excel.href = `/api/alerts/export?status=${encodeURIComponent(f || "all")}&format=xlsx`;
      $("#export-history-zip").href =
        `/api/alerts/export?status=${encodeURIComponent(f || "all")}&format=zip`;
      $("#hbody").innerHTML = list.length
        ? `<table class="tbl"><thead><tr><th>Ảnh</th><th>Mã</th><th>Thời gian</th><th>Nguồn</th><th>Hung khí</th><th>Xử lý bởi</th><th>Kết quả</th><th>Ghi chú</th></tr></thead><tbody>${list
            .map(
              (
                a,
              ) => `<tr><td><img src="${imgUrl(a)}" alt="" data-act="zoom"></td><td>#${a.id}</td><td>${fmt(a.created_at)}</td><td>${esc(a.source_name)}</td><td>${wtext(a)}</td>
        <td>${esc(a.handled_by)}<br><span class="hint">${fmt(a.handled_at)}</span></td><td><span class="status ${a.status}">${statusName(a.status)}</span></td>
        <td>${esc(a.review_reason || "")}${a.actual_label ? `<br>Thực tế: ${esc(a.actual_label === "background" ? "Không có hung khí" : className(a.actual_label))}` : ""}${a.review_note ? `<br>${esc(a.review_note)}` : ""}<br>${a.events
          .filter((e) => e.text.startsWith("Ghi chú"))
          .map((e) => esc(e.text))
          .join(
            "<br>",
          )}${a.status !== "deleted" ? `<br><button class="btn sm" data-act="delete" data-id="${a.id}" ${a.notification_status === "sending" ? "disabled" : ""}>Đánh dấu nhận diện sai</button>` : ""}</td></tr>`,
            )
            .join("")}</tbody></table>`
        : '<div class="empty"><strong>Chưa có dữ liệu</strong>Các cảnh báo đã xử lý sẽ hiện ở đây.</div>';
    };
    $("#hf").onchange = draw;
    draw();
  },
};

const TYPE_NAME = { camera: "Camera", drone: "Drone", robot: "Robot" };
function filterCameraRows() {
  const root = $("#view-dev-camera");
  if (!root) return;
  let visible = 0;
  $$("tbody tr[data-source-name]", root).forEach((row) => {
    row.hidden = !matchesSourceName(row.dataset.sourceName, S.cameraSearch);
    if (!row.hidden) visible++;
  });
  const empty = $("#camera-search-empty", root);
  if (empty) empty.hidden = visible > 0;
}
function deviceView(type) {
  return {
    async show() {
      await loadSources();
      this.draw();
    },
    draw() {
      const rows = S.sources.filter((s) => s.type === type),
        el = $(`#view-dev-${type}`);
      const coordinates = type === "camera" ? "" : "<th>Tọa độ</th>";
      const hint =
        type === "camera"
          ? ""
          : `<details class="box" style="margin-top:14px"><summary>Hướng dẫn tích hợp telemetry</summary>
        <p class="hint">Chương trình điều khiển ${type} gọi API này vài giây một lần. Các trường không bắt buộc: mode, battery, voltage, signal, altitude, speed, heading, sats, temp, wind, flight_time, lat, lon.</p>
        <pre>curl -X POST http://127.0.0.1:5000/api/sources/&lt;ID&gt;/telemetry -H "Content-Type: application/json" -d '{"mode":"AUTO","battery":76,"altitude":46,"speed":5.4,"sats":15,"flight_time":"4:22"}'</pre></details>`;
      el.innerHTML = `<div class="toolbar device-toolbar"><h2 class="grow" style="margin:0">${TYPE_NAME[type]}</h2>${type === "camera" ? `<label class="compact-field source-search">Tìm camera<input id="camera-search" type="search" placeholder="Nhập tên camera…" autocomplete="off" value="${esc(S.cameraSearch)}"></label>` : ""}<button class="btn primary" id="add-${type}">Thêm ${TYPE_NAME[type].toLowerCase()}</button></div>
        ${
          rows.length
            ? `<table class="tbl"><thead><tr><th></th><th>Tên</th><th>ID</th><th>Nguồn video</th><th>Vị trí</th>${coordinates}<th></th></tr></thead><tbody>${rows
                .map(
                  (
                    s,
                  ) => `<tr data-source-name="${esc(s.name)}"><td><span class="dot ${s.online ? "on" : ""}" title="${s.online ? "online" : "offline"}"></span></td><td>${esc(s.name)}${s.enabled ? "" : ' <span class="hint">(đang tắt)</span>'}</td><td><code>${esc(s.id)}</code></td><td>${s.demo_video ? `Video demo (${esc(s.video_name)})` : esc(s.url)}</td><td>${esc(s.location)}</td>
          ${type === "camera" ? "" : `<td>${s.lat != null ? `${s.lat}, ${s.lon}` : "-"}</td>`}
          <td><button class="btn sm edit" data-id="${s.id}">Sửa</button> <button class="btn sm del" data-id="${s.id}">Xóa</button></td></tr>`,
                )
                .join(
                  "",
                )}${type === "camera" ? '<tr id="camera-search-empty" hidden><td colspan="6" class="table-empty" role="status">Không tìm thấy camera phù hợp.</td></tr>' : ""}</tbody></table>`
            : `<div class="box empty"><strong>Chưa có ${type}</strong>Bấm "Thêm" để khai báo nguồn video đầu tiên.</div>`
        }${hint}`;
      $(`#add-${type}`).onclick = () => this.form(null);
      if (type === "camera") filterCameraRows();
      $$(".edit", el).forEach(
        (b) =>
          (b.onclick = () =>
            this.form(S.sources.find((s) => s.id === b.dataset.id))),
      );
      $$(".del", el).forEach(
        (b) =>
          (b.onclick = async () => {
            if (!confirm("Xóa thiết bị này?")) return;
            try {
              await api(`/api/sources/${b.dataset.id}`, "DELETE");
              toast("Đã xóa thiết bị");
              await this.show();
            } catch (error) {
              toast(`Không thể xóa thiết bị (${error.message})`);
            }
          }),
      );
    },
    form(s) {
      const d = $("#dlg");
      d.className = "";
      const sourceFields =
        type === "camera"
          ? `<label>Nguồn<select name="source_mode">
          <option value="url">Camera hoặc URL video</option><option value="video">Tải video demo lên</option></select></label>
        <div id="source-url-field"><label>Địa chỉ nguồn<input name="url" placeholder="0, 1, 2 (webcam/Iriun), rtsp://... hoặc http://..."></label><span class="hint">Iriun: mở ứng dụng trên điện thoại và máy tính, kiểm tra đã có hình rồi nhập chỉ số camera (0, 1, 2…). Mỗi camera chỉ thêm một lần.</span></div>
        <div id="source-video-field" hidden><label>Tệp video MP4/WebM<input name="video" type="file" accept=".mp4,.webm,video/mp4,video/webm"></label>
          <span class="hint" id="source-video-current"></span></div>`
          : `<label>Nguồn video<input name="url" required placeholder="0 (webcam) | rtsp://... | http://... | data/videos/demo.mp4"></label>`;
      const coordinateFields =
        type === "camera"
          ? ""
          : `<div class="row2"><label>Vĩ độ<input name="lat" type="number" step="any"></label><label>Kinh độ<input name="lon" type="number" step="any"></label></div>`;
      const enabledField =
        type === "camera"
          ? ""
          : `<label class="chk"><input name="enabled" type="checkbox"> Bật thiết bị này</label>`;
      d.innerHTML = `<form id="dev-form"><h3>${s ? "Sửa" : "Thêm"} ${TYPE_NAME[type].toLowerCase()}</h3><div class="sform" style="max-width:none">
        <label>Tên<input name="name" required></label>
        ${sourceFields}
        <label>Mô tả vị trí<input name="location"></label>
        ${coordinateFields}${enabledField}</div>
        <div class="dlg-actions"><button type="button" class="btn" id="dev-cancel">Hủy</button><button class="btn primary">Lưu</button></div></form>`;
      const f = $("#dev-form"),
        E = f.elements;
      E.name.value = s?.name ?? "";
      E.location.value = s?.location ?? "";
      if (type === "camera") {
        E.source_mode.value = s?.demo_video ? "video" : "url";
        E.url.value = s?.demo_video ? "" : (s?.url ?? "");
        $("#source-video-current").textContent = s?.demo_video
          ? `Video hiện tại: ${s.video_name}. Chọn tệp mới để thay thế.`
          : "";
        const updateSourceFields = () => {
          const useVideo = E.source_mode.value === "video";
          $("#source-url-field").hidden = useVideo;
          $("#source-video-field").hidden = !useVideo;
          E.url.required = !useVideo;
          E.video.required = useVideo && !s?.demo_video;
        };
        E.source_mode.onchange = updateSourceFields;
        updateSourceFields();
      } else {
        E.url.value = s?.url ?? "";
        E.lat.value = s?.lat ?? "";
        E.lon.value = s?.lon ?? "";
        E.enabled.checked = s ? !!s.enabled : true;
      }
      $("#dev-cancel").onclick = () => d.close();
      f.onsubmit = async (e) => {
        e.preventDefault();
        const body =
          type === "camera"
            ? new FormData()
            : {
                type,
                name: E.name.value,
                url: E.url.value,
                location: E.location.value,
                lat: E.lat.value,
                lon: E.lon.value,
                enabled: E.enabled.checked,
              };
        if (type === "camera") {
          body.append("type", type);
          body.append("name", E.name.value);
          body.append("location", E.location.value);
          body.append("enabled", String(s ? !!s.enabled : true));
          if (E.source_mode.value === "video") {
            const file = E.video.files[0];
            if (file) body.append("video", file);
            else if (s?.demo_video) body.append("url", s.url);
          } else {
            body.append("url", E.url.value);
          }
        }
        try {
          await api(
            s ? `/api/sources/${s.id}` : "/api/sources",
            s ? "PUT" : "POST",
            body,
          );
          d.close();
          toast("Đã lưu thiết bị");
          await this.show();
        } catch (err) {
          toast("Lưu thất bại, kiểm tra lại thông tin");
        }
      };
      d.onclick = null;
      d.showModal();
    },
  };
}
["camera", "drone", "robot"].forEach(
  (t) => (VIEWS[`dev-${t}`] = deviceView(t)),
);

VIEWS.map = {
  show() {
    $("#view-map").innerHTML = `<div class="mapbox big" id="big-map"></div>`;
    S.maps.big = makeMap($("#big-map"));
    setTimeout(() => S.maps.big?.m.invalidateSize(), 80);
  },
  tick() {
    updateMap(S.maps.big);
  },
};

function settingsForm(
  viewId,
  title,
  fields,
  extra = "",
  description = "",
  saveAfterExtra = false,
) {
  const el = $(`#view-${viewId}`);
  const groups = new Map();
  fields.forEach((field) => {
    const section = field.section || "Cài đặt chung";
    if (!groups.has(section)) groups.set(section, []);
    groups.get(section).push(field);
  });
  const fieldHtml = (field) => {
    if (field.type === "weapon")
      return `<div class="weapon-setting field-wide" data-weapon="${field.name}"><div class="weapon-setting-name"><strong>${field.label}</strong><span>${field.name}</span></div><label class="switch"><input type="checkbox" role="switch" name="${field.toggleKey}" aria-label="Nhận diện ${field.label}"><span class="switch-slider"></span></label><span class="weapon-setting-state"></span><label class="weapon-threshold">Ngưỡng tin cậy<input type="number" name="${field.k}" min="0" max="1" step="0.01" required aria-label="Ngưỡng ${field.label}"></label><label class="weapon-color"><input type="color" name="color_${field.name}" aria-label="${field.label}: color" title="${field.label}"></label></div>`;
    const cls = `field${field.wide || field.type === "checkbox" || field.type === "switch" ? " field-wide" : ""}`;
    const hint = "";
    if (field.type === "checkbox")
      return `<label class="chk ${cls}"><input type="checkbox" name="${field.k}"> ${field.label}${hint}</label>`;
    if (field.type === "switch")
      return `<div class="theme-setting ${cls}"><span>${field.offLabel}</span><label class="switch"><input type="checkbox" name="${field.k}" aria-label="${field.label}"><span class="switch-slider"></span></label><span>${field.onLabel}</span><span class="hint">${field.label}</span></div>`;
    if (field.type === "select")
      return `<label class="${cls}">${field.label}<select name="${field.k}">${field.options.map(([value, label]) => `<option value="${value}">${label}</option>`).join("")}</select>${hint}</label>`;
    return `<label class="${cls}">${field.label}<input type="${field.type || "text"}" name="${field.k}" ${field.hint ? `title="${esc(field.hint)}"` : ""} ${field.step ? `step="${field.step}"` : ""} ${field.min !== undefined ? `min="${field.min}"` : ""} ${field.max !== undefined ? `max="${field.max}"` : ""}>${hint}</label>`;
  };
  const sectionNames = [...groups.keys()];
  const activeSection = sectionNames.includes(S.settingsSection)
    ? S.settingsSection
    : sectionNames[0];
  const sections = [...groups.entries()]
    .map(
      ([section, sectionFields], index) =>
        `<section class="settings-card" ${viewId === "settings" ? `id="settings-panel-${index}" role="tabpanel" aria-labelledby="settings-tab-${index}" ${section !== activeSection ? "hidden" : ""}` : ""}><header class="settings-card-header"><h3>${section}</h3></header><div class="settings-fields">${sectionFields.map(fieldHtml).join("")}</div></section>`,
    )
    .join("");
  const saveButton = `<div class="settings-actions${saveAfterExtra ? " notifications-save" : ""}"><button class="btn primary" ${saveAfterExtra ? `type="submit" form="sf-${viewId}"` : ""}>Lưu thay đổi</button></div>`;
  el.innerHTML = `<header class="admin-page-header"><h2>${title}</h2></header>
    <form class="settings-form" id="sf-${viewId}">${sections}${saveAfterExtra ? "" : saveButton}</form>${extra}${saveAfterExtra ? saveButton : ""}`;
  if (viewId === "settings") {
    const form = $("#sf-settings");
    const workspace = document.createElement("div");
    workspace.className = "settings-content";
    const navigation = document.createElement("nav");
    navigation.className = "settings-subnav";
    navigation.setAttribute("role", "tablist");
    navigation.setAttribute("aria-label", "Các mục cài đặt");
    navigation.innerHTML = sectionNames
      .map(
        (name, index) =>
          `<button type="button" role="tab" id="settings-tab-${index}" aria-controls="settings-panel-${index}" aria-selected="${name === activeSection}" class="settings-subnav-item${name === activeSection ? " active" : ""}" data-section="${index}">${name}<span aria-hidden="true">›</span></button>`,
      )
      .join("");
    form.before(workspace);
    workspace.append(form);
    $("#settings-submenu").replaceChildren(navigation);
    const activate = (index) => {
      S.settingsSection = sectionNames[index];
      if (innerWidth <= 1100) document.body.classList.remove("mobile-nav-open");
      if (S.view !== "settings") {
        showView("settings");
        setSettingsExpanded(true);
        return;
      }
      navigation.querySelectorAll("button").forEach((button, i) => {
        button.classList.toggle("active", i === index);
        button.setAttribute("aria-selected", String(i === index));
        $(`#settings-panel-${i}`).hidden = i !== index;
      });
    };
    navigation.querySelectorAll("button").forEach((button, index) => {
      button.onclick = () => activate(index);
      button.onkeydown = (event) => {
        if (
          !["ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft"].includes(
            event.key,
          )
        )
          return;
        event.preventDefault();
        const next =
          (index +
            (["ArrowDown", "ArrowRight"].includes(event.key) ? 1 : -1) +
            sectionNames.length) %
          sectionNames.length;
        activate(next);
        navigation.querySelectorAll("button")[next].focus();
      };
    });
  }
  const form = $(`#sf-${viewId}`),
    E = form.elements;
  fields.forEach((f) => {
    const saved = f.preference ? S.preferences || {} : S.settings;
    if (f.type === "weapon") {
      E[f.k].value = S.settings[f.k] ?? 0.5;
      E[f.toggleKey].checked = S.settings[f.toggleKey] !== false;
      E[`color_${f.name}`].value =
        S.preferences?.[`color_${f.name}`] || "#22c55e";
      E[`color_${f.name}`].setAttribute("aria-label", `Màu khung ${f.label}`);
      const sync = () => {
        const enabled = E[f.toggleKey].checked;
        E[f.k].disabled = !enabled;
        const row = E[f.k].closest(".weapon-setting");
        row.classList.toggle("weapon-disabled", !enabled);
        $(".weapon-setting-state", row).textContent = enabled
          ? "Đang bật"
          : "Đã tắt";
        E[f.toggleKey].setAttribute("aria-checked", String(enabled));
      };
      E[f.toggleKey].onchange = sync;
      sync();
    } else if (f.type === "checkbox") E[f.k].checked = !!saved[f.k];
    else if (f.type === "switch") E[f.k].checked = saved[f.k] === f.onValue;
    else E[f.k].value = saved[f.k] ?? "";
  });
  const themeSwitch = fields.find((f) => f.type === "switch");
  if (themeSwitch)
    E[themeSwitch.k].onchange = async () => {
      const body = {
        [themeSwitch.k]: E[themeSwitch.k].checked
          ? themeSwitch.onValue
          : themeSwitch.offValue,
      };
      try {
        if (themeSwitch.preference)
          S.preferences = await api("/api/preferences", "PUT", body);
        else S.settings = await api("/api/settings", "PUT", body);
        applySettings();
        toast("Đã đổi chế độ giao diện");
      } catch (error) {
        E[themeSwitch.k].checked =
          (themeSwitch.preference ? S.preferences : S.settings)[
            themeSwitch.k
          ] === themeSwitch.onValue;
        toast(`Không thể đổi chế độ giao diện (${error.message})`);
      }
    };
  form.onsubmit = async (e) => {
    e.preventDefault();
    const body = {},
      preferences = {};
    fields.forEach((f) => {
      if (f.preference) {
        preferences[f.k] =
          f.type === "checkbox"
            ? E[f.k].checked
            : f.type === "switch"
              ? E[f.k].checked
                ? f.onValue
                : f.offValue
              : f.type === "number"
                ? Number(E[f.k].value)
                : E[f.k].value;
        return;
      }
      if (f.type === "weapon") {
        body[f.toggleKey] = E[f.toggleKey].checked;
        preferences[`color_${f.name}`] = E[`color_${f.name}`].value;
      }
      body[f.k] =
        f.type === "checkbox"
          ? E[f.k].checked
          : f.type === "switch"
            ? E[f.k].checked
              ? f.onValue
              : f.offValue
            : E[f.k].value;
    });
    S.settings = await api("/api/settings", "PUT", body);
    if (Object.keys(preferences).length)
      S.preferences = await api("/api/preferences", "PUT", preferences);
    applySettings();
    toast("Đã lưu cài đặt");
  };
  if (viewId === "settings") {
    const reset = document.createElement("button");
    reset.type = "button";
    reset.className = "btn sm";
    reset.textContent = "Khôi phục giao diện mặc định";
    $("#settings-panel-0 .settings-card-header").append(reset);
    reset.onclick = async () => {
      try {
        S.preferences = await api("/api/preferences", "PUT", { reset: true });
        fields
          .filter((field) => field.preference)
          .forEach((field) => {
            if (field.type === "checkbox")
              E[field.k].checked = S.preferences[field.k];
            else if (field.type === "switch")
              E[field.k].checked = S.preferences[field.k] === field.onValue;
            else E[field.k].value = S.preferences[field.k];
          });
        fields
          .filter((field) => field.type === "weapon")
          .forEach((field) => {
            E[`color_${field.name}`].value =
              S.preferences[`color_${field.name}`];
          });
        applySettings();
        toast("Đã khôi phục giao diện của bạn");
      } catch (error) {
        toast(`Không thể khôi phục: ${error.message}`);
      }
    };
  }
}
VIEWS.site = {
  show() {
    settingsForm(
      "site",
      "Địa điểm",
      [
        {
          k: "site_name",
          label: "Tên địa điểm",
          section: "Thông tin địa điểm",
        },
        {
          k: "site_address",
          label: "Địa chỉ",
          section: "Thông tin địa điểm",
          wide: true,
        },
        {
          k: "site_lat",
          label: "Vĩ độ",
          type: "number",
          step: "any",
          section: "Vị trí trên bản đồ",
        },
        {
          k: "site_lon",
          label: "Kinh độ",
          type: "number",
          step: "any",
          section: "Vị trí trên bản đồ",
        },
      ],
      "",
      "Quản lý thông tin địa điểm và tọa độ trung tâm được dùng trên bản đồ.",
    );
  },
};
const DETECTION_CLASSES = [
  ["axe", "Rìu"],
  ["baseball_bat", "Gậy bóng chày"],
  ["hammer", "Búa"],
  ["pistol", "Súng ngắn"],
  ["knife", "Dao"],
  ["sword", "Kiếm"],
  ["rifle", "Súng trường"],
  ["machete", "Mã tấu"],
  ["stick", "Gậy"],
  ["spear", "Giáo"],
];
VIEWS.settings = {
  show() {
    settingsForm(
      "settings",
      "Cài đặt",
      [
        {
          k: "theme",
          label: "Chế độ tối",
          type: "switch",
          offValue: "light",
          onValue: "dark",
          offLabel: "Sáng",
          onLabel: "Tối",
          section: "Giao diện",
          preference: true,
        },
        ...[
          {
            k: "density",
            label: "Mật độ hiển thị",
            options: [
              ["compact", "Gọn"],
              ["standard", "Tiêu chuẩn"],
              ["spacious", "Rộng"],
            ],
          },
          {
            k: "font_size",
            label: "Cỡ chữ giao diện",
            options: [
              ["small", "Nhỏ"],
              ["medium", "Vừa"],
              ["large", "Lớn"],
            ],
          },
          {
            k: "sidebar",
            label: "Thanh bên",
            options: [
              ["auto", "Tự động"],
              ["expanded", "Luôn mở"],
              ["collapsed", "Thu gọn"],
            ],
          },
          {
            k: "camera_columns",
            label: "Bố cục camera mặc định",
            options: [
              ["auto", "Tự động"],
              ["1", "1 cột"],
              ["2", "2 cột"],
              ["3", "3 cột"],
              ["4", "4 cột"],
            ],
          },
          {
            k: "label_content",
            label: "Nội dung nhãn nhận diện",
            options: [
              ["both", "Tên và độ tin cậy"],
              ["name", "Chỉ tên loại"],
              ["confidence", "Chỉ độ tin cậy"],
              ["none", "Ẩn nhãn, giữ khung"],
            ],
          },
        ].map((field) => ({
          ...field,
          type: "select",
          section: "Giao diện",
          preference: true,
        })),
        {
          k: "box_width",
          label: "Độ dày viền nhận diện",
          type: "number",
          min: 1,
          max: 10,
          step: 1,
          section: "Giao diện",
          preference: true,
        },
        {
          k: "label_size",
          label: "Cỡ chữ nhãn nhận diện",
          type: "number",
          min: 12,
          max: 32,
          step: 1,
          section: "Giao diện",
          preference: true,
        },
        ...[
          ["show_camera_name", "Hiển thị tên camera"],
          ["show_location", "Hiển thị vị trí camera"],
          ["show_fps", "Hiển thị FPS và độ phân giải"],
          ["show_status", "Hiển thị trạng thái kết nối trên camera"],
          ["reduce_motion", "Giảm chuyển động và hiệu ứng"],
        ].map(([k, label]) => ({
          k,
          label,
          type: "checkbox",
          section: "Giao diện",
          preference: true,
        })),
        {
          k: "sound",
          label: "Phát âm báo khi có cảnh báo mới",
          type: "checkbox",
          section: "Trực ca và cảnh báo",
        },
        ...DETECTION_CLASSES.map(([name, label]) => ({
          name,
          label,
          k: `${name}_conf_threshold`,
          toggleKey: `${name}_enabled`,
          type: "weapon",
          section: "Nhận diện hung khí",
        })),
        {
          k: "confirm_frames",
          label: "Số lần nhận diện liên tiếp để tạo cảnh báo",
          type: "number",
          section: "Xác nhận cảnh báo",
        },
        {
          k: "alert_cooldown",
          label: "Thời gian chờ giữa hai cảnh báo cùng thiết bị (giây)",
          type: "number",
          section: "Xác nhận cảnh báo",
        },
        {
          k: "imgsz",
          label: "Kích thước ảnh đưa vào model",
          type: "number",
          hint: "Tăng kích thước có thể hỗ trợ vật thể nhỏ hoặc ở xa nhưng xử lý chậm hơn.",
          section: "Hiệu năng xử lý",
        },
        {
          k: "detail_scan",
          label: "Quét thêm 4 vùng ảnh phóng lớn (tăng tải và độ trễ)",
          type: "checkbox",
          section: "Hiệu năng xử lý",
        },
        {
          k: "detect_fps",
          label: "Số lần nhận diện tối đa mỗi giây cho mỗi thiết bị",
          type: "number",
          hint: "Mặc định tối đa 45 lần/giây. Đây là mức trần, không phải FPS đảm bảo; tốc độ thực tế phụ thuộc phần cứng và số nguồn chạy cùng lúc.",
          section: "Hiệu năng xử lý",
        },
      ],
      "",
      "Cấu hình giao diện, xử lý cảnh báo và hiệu năng nhận diện.",
    );
  },
};
VIEWS.notify = {
  show() {
    settingsForm(
      "notify",
      "Thông báo",
      [
        {
          k: "telegram_enabled",
          label: "Cho phép gửi thông báo tới điện thoại sau khi xác nhận",
          type: "checkbox",
          section: "Gửi thông báo",
        },
        {
          k: "telegram_token",
          label: "Bot token",
          type: "password",
          section: "Gửi thông báo",
        },
      ],
      `<div class="box mobile-notifications">
      <h3>Thiết bị di động nhận thông báo</h3>
      <details><summary>Hướng dẫn kết nối</summary><p class="hint">Mở bot Telegram và gửi /start. Nhập tên thiết bị và Chat ID. Bỏ chọn “Nhận thông báo” để tạm ngừng gửi.</p></details>
      <div id="mobile-device-list" class="mobile-device-list"><span class="hint">Đang tải thiết bị...</span></div>
      <button class="btn sm" id="add-mobile-device" type="button">Thêm thiết bị di động</button>
      <form id="mobile-device-form" class="mobile-device-form" hidden>
        <label>Tên thiết bị<input name="name" required maxlength="80" placeholder="Ví dụ: Điện thoại trực ca"></label>
        <label>Chat ID Telegram<input name="chat_id" required inputmode="numeric" placeholder="Nhập Chat ID"></label>
        <div class="mobile-device-actions"><button class="btn primary sm" type="submit">Thêm</button>
          <button class="btn sm" id="cancel-mobile-device" type="button">Hủy</button></div>
      </form>
      <button class="btn sm" id="tg-test" type="button">Gửi tin thử tới tất cả thiết bị đang bật</button>
    </div>`,
      "Thiết lập kênh Telegram và quản lý các điện thoại nhận thông báo.",
      true,
    );
    const list = $("#mobile-device-list");
    const drawDevices = async () => {
      try {
        const devices = await api("/api/mobile-devices");
        list.innerHTML = devices.length
          ? devices
              .map(
                (device) => `<div class="mobile-device-row">
            <label class="mobile-device-toggle"><input type="checkbox" data-mobile-enabled="${device.id}" data-enabled="${!!device.enabled}" ${device.enabled ? "checked" : ""}><span>Nhận thông báo</span></label>
            <div class="mobile-device-content"><div class="mobile-device-name"><strong>${esc(device.name)}</strong>
              <button class="btn sm" type="button" data-mobile-edit="${device.id}">Sửa tên</button></div>
              <form class="mobile-device-edit" data-mobile-edit-form="${device.id}" hidden>
                <input name="name" required maxlength="80" value="${esc(device.name)}" aria-label="Tên thiết bị">
                <button class="btn primary sm" type="submit">Lưu</button>
                <button class="btn sm" type="button" data-mobile-edit-cancel="${device.id}">Hủy</button>
              </form>
              <span class="hint">Chat ID: ${esc(device.chat_id)}</span></div>
            <button class="btn sm" type="button" data-mobile-test="${device.id}">Gửi thử</button>
            <button class="btn sm" type="button" data-mobile-delete="${device.id}">Xóa</button></div>`,
              )
              .join("")
          : '<div class="empty">Chưa có thiết bị di động nào.</div>';
      } catch (error) {
        list.innerHTML =
          '<div class="empty">Không tải được danh sách thiết bị di động.</div>';
        toast(`Không tải được thiết bị di động (${error.message})`);
      }
    };
    const form = $("#mobile-device-form");
    $("#add-mobile-device").onclick = () => {
      form.hidden = !form.hidden;
    };
    $("#cancel-mobile-device").onclick = () => {
      form.reset();
      form.hidden = true;
    };
    form.onsubmit = async (event) => {
      event.preventDefault();
      const data = new FormData(form);
      try {
        await api("/api/mobile-devices", "POST", {
          name: data.get("name"),
          chat_id: data.get("chat_id"),
        });
        form.reset();
        form.hidden = true;
        toast("Đã thêm thiết bị di động");
        await drawDevices();
      } catch (error) {
        toast(`Không thể thêm thiết bị di động (${error.message})`);
      }
    };
    $("#tg-test").onclick = async () => {
      try {
        const result = await api("/api/notify/test", "POST");
        toast(result.info);
      } catch (error) {
        toast(`Gửi tin thử thất bại (${error.message})`);
      }
    };
    list.onclick = async (event) => {
      const testButton = event.target.closest("[data-mobile-test]");
      const deleteButton = event.target.closest("[data-mobile-delete]");
      const editButton = event.target.closest("[data-mobile-edit]");
      const cancelButton = event.target.closest("[data-mobile-edit-cancel]");
      if (editButton) {
        list.querySelector(
          `[data-mobile-edit-form="${editButton.dataset.mobileEdit}"]`,
        ).hidden = false;
        return;
      }
      if (cancelButton) {
        list.querySelector(
          `[data-mobile-edit-form="${cancelButton.dataset.mobileEditCancel}"]`,
        ).hidden = true;
        return;
      }
      try {
        if (testButton) {
          const result = await api(
            `/api/mobile-devices/${testButton.dataset.mobileTest}/test`,
            "POST",
          );
          toast(result.info);
        } else if (deleteButton) {
          if (!confirm("Xóa thiết bị di động này?")) return;
          await api(
            `/api/mobile-devices/${deleteButton.dataset.mobileDelete}`,
            "DELETE",
          );
          toast("Đã xóa thiết bị di động");
          await drawDevices();
        }
      } catch (error) {
        toast(`Không thể xử lý thiết bị di động (${error.message})`);
      }
    };
    list.onchange = async (event) => {
      const checkbox = event.target.closest("[data-mobile-enabled]");
      if (!checkbox) return;
      try {
        await api(
          `/api/mobile-devices/${checkbox.dataset.mobileEnabled}`,
          "PUT",
          { enabled: checkbox.checked },
        );
        toast(
          checkbox.checked
            ? "Đã bật nhận thông báo cho thiết bị"
            : "Đã tắt nhận thông báo cho thiết bị",
        );
        await drawDevices();
      } catch (error) {
        checkbox.checked = checkbox.dataset.enabled === "true";
        toast(`Không thể cập nhật thiết bị (${error.message})`);
      }
    };
    list.onsubmit = async (event) => {
      const form = event.target.closest("[data-mobile-edit-form]");
      if (!form) return;
      event.preventDefault();
      const name = new FormData(form).get("name");
      try {
        await api(`/api/mobile-devices/${form.dataset.mobileEditForm}`, "PUT", {
          name,
        });
        toast("Đã cập nhật tên thiết bị");
        await drawDevices();
      } catch (error) {
        toast(`Không thể sửa tên thiết bị (${error.message})`);
      }
    };
    drawDevices();
  },
};

VIEWS.logs = {
  async show() {
    S.logs = await api("/api/logs");
    $("#view-logs").innerHTML =
      `<header class="admin-page-header"><h2>Nhật ký hệ thống</h2></header>
    <section class="settings-card log-card"><header class="settings-card-header"><h3>Nhật ký hoạt động</h3><span class="count-badge">${S.logs.length} mục</span></header>
    ${logTable(S.logs)}</section>`;
  },
};

async function loadSources() {
  S.sources = await api("/api/sources");
}

async function refresh(force) {
  if (S.refreshing) {
    if (force) S.refreshQueued = true;
    return;
  }
  S.refreshing = true;
  try {
    const [src, pend] = await Promise.all([
      api("/api/sources"),
      api("/api/alerts?status=pending"),
    ]);
    S.sources = src;
    S.pending = pend;
    if (force || S.tickN++ % 3 === 0) {
      [S.stats, S.logs] = await Promise.all([
        api(`/api/stats?days=${S.dashboardDays || 7}`),
        api("/api/logs"),
      ]);
    }
    $("#conn").textContent = "Đã kết nối";
    $("#conn").classList.remove("bad");
  } catch (e) {
    $("#conn").textContent = "Mất kết nối";
    $("#conn").classList.add("bad");
    return;
  } finally {
    S.refreshing = false;
    if (S.refreshQueued) {
      S.refreshQueued = false;
      setTimeout(() => refresh(true), 0);
    }
  }

  const fresh = S.pending.filter((a) => !S.known.has(a.id));
  fresh.forEach((a) => S.known.add(a.id));
  if (fresh.length && !S.first) {
    beep();
    const selectedIsPending = S.pending.some((a) => a.id === S.selected);
    if (S.view !== "verify" || !selectedIsPending) S.selected = fresh[0].id;
    toast(`Có ${fresh.length} cảnh báo mới cần xác minh`, "Mở cảnh báo", () =>
      showView("verify"),
    );
  }
  S.first = false;

  const b = $("#badge");
  b.hidden = !S.pending.length;
  b.textContent = S.pending.length;
  document.title =
    (S.pending.length ? `(${S.pending.length}) ` : "") + "SAFESIGHT";
  tickCurrent();
}

async function start() {
  buildShell();
  S.settings = await api("/api/settings");
  applySettings();
  S.preferences = await api("/api/preferences");
  applySettings();
  setInterval(
    () => ($("#clock").textContent = new Date().toLocaleTimeString("vi-VN")),
    1000,
  );
  await refresh(true);
  showView("live");
  setInterval(refresh, 2000);
}
start();

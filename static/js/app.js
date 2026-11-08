"use strict";
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = iso => iso ? new Date(iso).toLocaleString("vi-VN") : "-";
const wtext = a => Object.entries(a.summary).map(([k, n]) => `${n} ${k}`).join(", ");
const chips = a => Object.entries(a.summary).map(([k, n]) => `<span class="chip ${esc(k)}">${n} ${esc(k)}</span>`).join("");
const imgUrl = a => `/alert_images/${a.image}`;
const evidenceRecord = entry => typeof entry === "string"
  ? { image: entry, detections: null, captured_at: null }
  : entry;
const detectionInfoText = detections => detections == null
  ? "Chưa có dữ liệu nhận diện cho ảnh này"
  : detections.length
    ? detections.map(d => `${d.label} ${Math.round(d.conf * 100)}%`).join(" · ")
    : "Không phát hiện lại vật thể mục tiêu";
const detectionInfo = detections => esc(detectionInfoText(detections));
const evidenceStrip = (a, selectedImage) => (a.evidence_images || []).length
  ? `<div class="evidence-strip"><h3>Ảnh theo dõi tiếp diễn (${a.evidence_images.length}/5)</h3><div class="hint">Chọn ảnh để xem khung hình và kết quả nhận diện. Dispatch xác nhận toàn bộ cảnh báo.</div><div class="evidence-frames">${
    a.evidence_images.map((rawEntry, i) => {
      const entry = evidenceRecord(rawEntry);
      const image = entry.image;
      return `<button class="evidence-frame${selectedImage === `/alert_images/${encodeURIComponent(image)}` ? " sel" : ""}" data-act="evidence-frame" data-image="/alert_images/${encodeURIComponent(image)}" data-frame="${i + 1}" title="Xem ảnh ${i + 1} sau phát hiện ban đầu">
      <span class="evidence-thumb-view"><img src="/alert_images/${encodeURIComponent(image)}" alt="Ảnh ${i + 1}"><canvas class="evidence-detections-canvas"></canvas></span>
      <span>Ảnh ${i + 1}: ${detectionInfo(entry.detections)}</span></button>`;
    }).join("")
  }</div></div>`
  : "";

async function api(url, method = "GET", body) {
  const isForm = body instanceof FormData;
  const r = await fetch(url, { method, headers: body && !isForm ? { "Content-Type": "application/json" } : {}, body: body ? isForm ? body : JSON.stringify(body) : undefined });
  if (!r.ok) throw new Error(r.status);
  return r.json();
}

const S = {
  sources: [], pending: [], logs: [], stats: null, settings: {},
  selected: null, selectedEvidence: null, known: new Set(), first: true, view: "dashboard",
  sigs: {}, tickN: 0, silencedUntil: 0, maps: {}, showDetectionLabels: true,
  focusedSource: null, liveStreamsSignature: null, refreshing: false,
};

function paintDetectionOverlay(img, canvas, detections, showLabels) {
  if (!img?.complete || !img.naturalWidth || !canvas) {
    if (img && canvas && !img.detectionOverlayPending) {
      img.detectionOverlayPending = true;
      img.addEventListener("load", () => {
        img.detectionOverlayPending = false;
        paintDetectionOverlay(img, canvas, canvas.detections, S.showDetectionLabels);
      }, { once: true });
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
  const contentWidth = imageRatio > canvasRatio ? rect.width : rect.height * imageRatio;
  const contentHeight = imageRatio > canvasRatio ? rect.width / imageRatio : rect.height;
  const offsetX = (rect.width - contentWidth) / 2;
  const offsetY = (rect.height - contentHeight) / 2;
  const scaleX = contentWidth / img.naturalWidth;
  const scaleY = contentHeight / img.naturalHeight;
  ctx.lineWidth = 4;
  ctx.font = "bold 13px sans-serif";
  for (const detection of detections || []) {
    if (!Array.isArray(detection.box) || detection.box.length !== 4) continue;
    const [x1, y1, x2, y2] = detection.box;
    const left = offsetX + x1 * scaleX, top = offsetY + y1 * scaleY;
    const width = (x2 - x1) * scaleX, height = (y2 - y1) * scaleY;
    ctx.strokeStyle = "#50dc53";
    ctx.strokeRect(left, top, width, height);
    if (!showLabels) continue;
    const label = `${detection.label} ${Math.round(Number(detection.conf) * 100)}%`;
    const labelHeight = 20, labelWidth = ctx.measureText(label).width + 10;
    const labelTop = Math.max(0, top - labelHeight);
    ctx.fillStyle = "#50dc53";
    ctx.fillRect(left, labelTop, labelWidth, labelHeight);
    ctx.fillStyle = "#fff";
    ctx.fillText(label, left + 5, labelTop + 14);
  }
}

function refreshDetectionOverlays(root) {
  $$(".alert-detections-canvas, .evidence-detections-canvas", root).forEach(canvas => {
    paintDetectionOverlay(canvas.previousElementSibling, canvas, canvas.detections, S.showDetectionLabels);
  });
}

function setupAlertDetectionOverlays(root, alert, mainDetections) {
  const mainCanvas = $(".alert-detections-canvas", root);
  if (mainCanvas) {
    mainCanvas.detections = mainDetections || [];
    paintDetectionOverlay($("#alert-image", root), mainCanvas, mainCanvas.detections, S.showDetectionLabels);
  }
  $$(".evidence-frame", root).forEach((button, index) => {
    const canvas = $(".evidence-detections-canvas", button);
    if (!canvas) return;
    canvas.detections = evidenceRecord(alert.evidence_images[index]).detections || [];
    paintDetectionOverlay($("img", button), canvas, canvas.detections, S.showDetectionLabels);
  });
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
  toast.id = setTimeout(() => t.classList.remove("show", "actionable"), actionLabel ? 8000 : 2600);
}

function beep() {
  if (!S.settings.sound || Date.now() < S.silencedUntil) return;
  try {
    const c = new AudioContext(), o = c.createOscillator(), g = c.createGain();
    o.type = "square"; o.frequency.value = 880; g.gain.value = 0.08;
    o.connect(g); g.connect(c.destination); o.start(); o.stop(c.currentTime + 0.4);
  } catch (e) { }
}

const ICON = {
  dashboard: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>',
  live: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/>',
  verify: '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17v.5"/>',
  history: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  camera: '<rect x="3" y="7" width="18" height="13" rx="2"/><circle cx="12" cy="13.5" r="3.5"/><path d="M8 7l1.5-3h5L16 7"/>',
  drone: '<circle cx="5" cy="5" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M7 7l2 2M17 7l-2 2M7 17l2-2M17 17l-2-2"/>',
  robot: '<rect x="4" y="8" width="16" height="12" rx="2"/><path d="M12 8V4"/><circle cx="9" cy="14" r="1.5"/><circle cx="15" cy="14" r="1.5"/>',
  map: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>',
  site: '<rect x="5" y="3" width="14" height="18"/><path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2"/>',
  bell: '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 21h4"/>',
  settings: '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="8" cy="18" r="2"/>',
  log: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
};
const svg = n => `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICON[n]}</svg>`;
const NAV = [
  { id: "dashboard", t: "Dashboard", i: "dashboard" },
  { id: "live", t: "Live Ops", i: "live" },
  { id: "verify", t: "Alerts", i: "verify", badge: true },
  { id: "history", t: "Past Ops", i: "history" },
  { id: "dev-camera", t: "Cameras", i: "camera" },
  { id: "dev-drone", t: "Drones", i: "drone" },
  { id: "dev-robot", t: "Robots", i: "robot" },
  { id: "map", t: "Map", i: "map" },
  { sep: "Admin" },
  { id: "site", t: "Site", i: "site" },
  { id: "notify", t: "Notifications", i: "bell" },
  { id: "settings", t: "Settings", i: "settings" },
  { id: "logs", t: "System Log", i: "log" },
];

function buildShell() {
  $("#sidebar").innerHTML = NAV.map(n => n.sep ? `<div class="nav-sep">${n.sep}</div>` :
    `<button class="nav" data-view="${n.id}" title="${n.t}">${svg(n.i)}<span>${n.t}</span>${n.badge ? '<b class="badge" id="badge" hidden>0</b>' : ""}</button>`).join("");
  $("#main").innerHTML = NAV.filter(n => n.id).map(n => `<section class="view" id="view-${n.id}" hidden></section>`).join("");
  $$(".nav").forEach(b => b.onclick = () => showView(b.dataset.view));
  $("#menu-btn").onclick = () => document.body.classList.toggle("collapsed");
}

function applySettings() {
  const s = S.settings;
  $("#operator").textContent = s.operator || "";
  document.documentElement.dataset.theme = s.theme === "dark" ? "dark" : "light";
}

function showView(id) {
  (VIEWS[S.view] || {}).hide?.();
  S.view = id;
  $$(".view").forEach(v => v.hidden = v.id !== `view-${id}`);
  $$(".nav").forEach(b => b.classList.toggle("active", b.dataset.view === id));
  S.sigs = {};
  (VIEWS[id] || {}).show?.(id);
  (VIEWS[id] || {}).tick?.(id);
}

function makeMap(el) {
  if (typeof L === "undefined") { el.innerHTML = '<div class="empty">Không tải được Leaflet (cần internet để hiện bản đồ).</div>'; return null; }
  const s = S.settings;
  const siteLat = s.site_lat !== "" && s.site_lat != null && Number.isFinite(Number(s.site_lat)) ? Number(s.site_lat) : 21.0285;
  const siteLon = s.site_lon !== "" && s.site_lon != null && Number.isFinite(Number(s.site_lon)) ? Number(s.site_lon) : 105.8542;
  const m = L.map(el).setView([siteLat, siteLon], 17);
  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19, attribution: "Esri" }).addTo(m);
  return { m, layer: L.layerGroup().addTo(m), sitePoint: [siteLat, siteLon], siteName: s.site_name, fitted: false };
}
function updateMap(mp) {
  if (!mp) return;
  mp.layer.clearLayers();
  const pts = [], letter = { camera: "C", drone: "D", robot: "R" };
  L.marker(mp.sitePoint, {
    icon: L.divIcon({
      className: "",
      html: '<div class="site-pin"><span></span></div>',
      iconSize: [36, 42],
      iconAnchor: [18, 42],
    }),
    zIndexOffset: 1000,
  }).bindTooltip(mp.siteName || "Vị trí đã cài đặt").addTo(mp.layer);
  pts.push(mp.sitePoint);
  const mk = (lat, lon, cls, txt, tip, onclick) => {
    const m = L.marker([lat, lon], { icon: L.divIcon({ className: "", html: `<div class="mk ${cls}">${txt}</div>`, iconSize: [26, 26] }) }).bindTooltip(tip).addTo(mp.layer);
    if (onclick) m.on("click", onclick);
    pts.push([lat, lon]);
  };
  S.sources.filter(s => s.lat != null && s.lon != null)
    .forEach(s => mk(s.lat, s.lon, `${s.type} ${s.online ? "" : "off"}`, letter[s.type], s.name));
  S.pending.filter(a => a.lat != null && a.lon != null)
    .forEach(a => mk(a.lat, a.lon, "alert", "!", `Alert #${a.id} - ${wtext(a)}`, () => { S.selected = a.id; showView("live"); }));
  if (!mp.fitted && pts.length) { mp.m.fitBounds(pts, { maxZoom: 18, padding: [30, 30] }); mp.fitted = true; }
}

function current() {
  if (!S.pending.length) { S.selected = null; return null; }
  if (!S.pending.find(a => a.id === S.selected)) S.selected = S.pending[0].id;
  return S.pending.find(a => a.id === S.selected);
}
const timeline = a => `<ul class="tl">${a.events.map(e => `<li><time>${fmt(e.ts)}</time>${esc(e.text)}</li>`).join("")}</ul>`;
const noteBox = a => `<textarea class="note" id="note-${a.id}" placeholder="Ghi chú cho cảnh báo này..."></textarea>
  <button class="btn sm" data-act="note" data-id="${a.id}">Lưu ghi chú</button>`;
const logTable = rows => `<div class="table-scroll"><table class="tbl log-table"><thead><tr><th>ID</th><th>Thời gian</th><th>Sự kiện</th><th>Chi tiết</th></tr></thead><tbody>${
  rows.map(l => `<tr class="lv-${esc(l.level)}"><td>${l.id}</td><td>${fmt(l.ts)}</td><td><span class="log-level">${esc(l.level)}</span> ${esc(l.subject)}</td><td>${esc(l.info)}</td></tr>`).join("")
  || '<tr><td colspan="4" class="table-empty">Chưa có nhật ký hệ thống.</td></tr>'
}</tbody></table></div>`;

async function act(what, id) {
  try {
    if (what === "dispatch") { const r = await api(`/api/alerts/${id}/dispatch`, "POST"); toast(`Đã dispatch alert ${id} - ${r.info}`); }
    else if (what === "delete") { await api(`/api/alerts/${id}/delete`, "POST"); toast(`Đã xóa alert ${id}`); }
    else if (what === "clear") {
      if (!confirm("Xóa tất cả cảnh báo đang chờ?")) return;
      const r = await api("/api/alerts/clear", "POST"); toast(`Đã xóa ${r.count} cảnh báo`);
    } else if (what === "note") {
      const t = $(`#note-${id}`).value.trim(); if (!t) return;
      await api(`/api/alerts/${id}/note`, "POST", { text: t }); toast("Đã lưu ghi chú");
    }
  } catch (e) { toast("Không thực hiện được (cảnh báo có thể đã được xử lý)"); }
  dirty(); await refresh(true);
}

function zoom(src) {
  const d = $("#dlg");
  d.className = "wide zoom-dlg";
  d.innerHTML = `<p class="hint" style="margin-bottom:8px">Di chuột trên ảnh để phóng to vùng quanh con trỏ. Bấm ra ngoài hoặc Đóng để thoát.</p>
    <div class="zoom-view"><img src="${src}" alt="Ảnh cảnh báo"><canvas class="zoom-lens" width="200" height="130" hidden></canvas></div>
    <div class="dlg-actions"><button type="button" class="btn" id="zoom-close">Đóng</button></div>`;
  const view = $(".zoom-view", d), img = $("img", view), lens = $(".zoom-lens", view);
  const mag = 2.6;
  const paint = e => {
    if (!img.naturalWidth) return;
    const r = img.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    if (x < 0 || y < 0 || x > r.width || y > r.height) { lens.hidden = true; return; }
    lens.hidden = false;
    const lensWidth = lens.width, lensHeight = lens.height, vr = view.getBoundingClientRect();
    lens.style.left = `${e.clientX - vr.left - lensWidth / 2}px`;
    lens.style.top = `${e.clientY - vr.top - lensHeight / 2}px`;
    const nx = x / r.width * img.naturalWidth, ny = y / r.height * img.naturalHeight;
    const srcWidth = lensWidth / mag * img.naturalWidth / r.width;
    const srcHeight = lensHeight / mag * img.naturalHeight / r.height;
    const srcX = Math.max(0, Math.min(img.naturalWidth - srcWidth, nx - srcWidth / 2));
    const srcY = Math.max(0, Math.min(img.naturalHeight - srcHeight, ny - srcHeight / 2));
    const ctx = lens.getContext("2d");
    ctx.clearRect(0, 0, lensWidth, lensHeight);
    ctx.drawImage(img, srcX, srcY, srcWidth, srcHeight, 0, 0, lensWidth, lensHeight);
    ctx.strokeStyle = "#3ee07a"; ctx.lineWidth = 3; ctx.strokeRect(1.5, 1.5, lensWidth - 3, lensHeight - 3);
  };
  view.onmousemove = paint;
  view.onmouseleave = () => { lens.hidden = true; };
  $("#zoom-close").onclick = () => d.close();
  d.onclick = e => { if (e.target === d) d.close(); };
  d.showModal();
}

function attachAlertMagnifier(view) {
  const img = $(".vimg", view), canvas = $(".alert-magnifier", view);
  if (!img || !canvas) return;
  const magnification = 2.5, lensWidth = 200, lensHeight = 130;
  const ctx = canvas.getContext("2d");
  const hide = () => { canvas.hidden = true; };
  const paint = e => {
    if (!img.complete || !img.naturalWidth) return;
    const imageRect = img.getBoundingClientRect(), viewRect = view.getBoundingClientRect();
    const scale = Math.min(imageRect.width / img.naturalWidth, imageRect.height / img.naturalHeight);
    const renderedWidth = img.naturalWidth * scale, renderedHeight = img.naturalHeight * scale;
    const imageLeft = imageRect.left + (imageRect.width - renderedWidth) / 2;
    const imageTop = imageRect.top + (imageRect.height - renderedHeight) / 2;
    const x = e.clientX - imageLeft, y = e.clientY - imageTop;
    if (x < 0 || y < 0 || x > renderedWidth || y > renderedHeight) { hide(); return; }

    const width = Math.min(lensWidth, renderedWidth), height = Math.min(lensHeight, renderedHeight);
    const left = Math.max(0, Math.min(renderedWidth - width, x + 18));
    const top = Math.max(0, Math.min(renderedHeight - height, y + 18));
    const ratioX = img.naturalWidth / renderedWidth, ratioY = img.naturalHeight / renderedHeight;
    const sourceWidth = width / magnification * ratioX, sourceHeight = height / magnification * ratioY;
    const sourceX = Math.max(0, Math.min(img.naturalWidth - sourceWidth, x * ratioX - sourceWidth / 2));
    const sourceY = Math.max(0, Math.min(img.naturalHeight - sourceHeight, y * ratioY - sourceHeight / 2));
    const dpr = window.devicePixelRatio || 1;
    const canvasWidth = Math.round(viewRect.width * dpr), canvasHeight = Math.round(viewRect.height * dpr);
    if (canvas.width !== canvasWidth || canvas.height !== canvasHeight) {
      canvas.width = canvasWidth;
      canvas.height = canvasHeight;
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, sourceX, sourceY, sourceWidth, sourceHeight,
      (imageLeft - viewRect.left + left) * dpr, (imageTop - viewRect.top + top) * dpr,
      width * dpr, height * dpr);
    ctx.strokeStyle = "#3ee07a";
    ctx.lineWidth = 3 * dpr;
    ctx.strokeRect((imageLeft - viewRect.left + left) * dpr, (imageTop - viewRect.top + top) * dpr,
      width * dpr, height * dpr);
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

document.addEventListener("click", e => {
  const el = e.target.closest("[data-act]"); if (!el) return;
  const id = +el.dataset.id, a = el.dataset.act;
  if (["dispatch", "delete", "clear", "note"].includes(a)) return act(a, id);
  if (a === "select") { S.selected = id; S.selectedEvidence = null; dirty(); tickCurrent(); }
  else if (a === "evidence-frame") {
    const image = $("#alert-image");
    if (!image) return;
    S.selectedEvidence = { alertId: S.selected, image: el.dataset.image, frame: el.dataset.frame };
    const alert = S.pending.find(item => item.id === S.selected);
    const evidence = alert?.evidence_images?.map(evidenceRecord).find(
      item => `/alert_images/${encodeURIComponent(item.image)}` === el.dataset.image);
    image.src = el.dataset.image;
    image.alt = `Ảnh ${el.dataset.frame}`;
    $("#alert-image-label").textContent = `Ảnh ${el.dataset.frame}`;
    $("#alert-frame-detections").textContent = detectionInfoText(evidence?.detections);
    $("#alert-frame-time").textContent = fmt(evidence?.captured_at);
    const canvas = $(".alert-detections-canvas", $("#view-verify"));
    if (canvas) {
      canvas.detections = evidence?.detections || [];
      paintDetectionOverlay(image, canvas, canvas.detections, S.showDetectionLabels);
    }
    $$(".evidence-frame", el.closest(".evidence-strip")).forEach(frame => frame.classList.toggle("sel", frame === el));
  }
  else if (a === "silence") { S.silencedUntil = Date.now() + 5 * 60000; toast("Tắt âm báo trong 5 phút"); }
  else if (a === "zoom") zoom(el.getAttribute("src") || $("img", el)?.getAttribute("src"));
  else if (a === "fs") toggleStreamFullscreen(el);
  else if (a === "open-alert") { S.selected = id; showView("verify"); }
});
document.addEventListener("change", e => {
  if (e.target.matches("#show-detection-labels")) {
    S.showDetectionLabels = e.target.checked;
    refreshDetectionOverlays($("#view-verify"));
  }
});
document.addEventListener("click", e => {
  if (e.target.closest("#live-play-all")) {
    const videos = $$(".demo-video", $("#view-live"));
    if (videos.length && videos.every(video => !video.paused)) {
      videos.forEach(video => video.pause());
    } else {
      Promise.allSettled(videos.map(video => {
        if (video.ended) video.currentTime = 0;
        return video.play();
      })).then(results => {
        const failures = results.filter(result => result.status === "rejected");
        if (failures.length) {
          toast(`Không thể phát ${failures.length} video. Kiểm tra định dạng hoặc nguồn video.`);
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
document.addEventListener("click", e => {
  const panel = e.target.closest(".pvid");
  if (!panel || e.target.closest("button")) return;
  const id = panel.closest(".panel").dataset.id;
  if (S.focusedSource !== id) {
    S.focusedSource = id;
    tickCurrent();
  }
});
document.addEventListener("click", e => {
  const header = e.target.closest(".pbar[data-source-id]");
  if (!header) return;
  const id = header.dataset.sourceId;
  if (S.focusedSource !== id) {
    S.focusedSource = id;
    tickCurrent();
  }
});
document.addEventListener("keydown", e => {
  const header = e.target.closest(".pbar[data-source-id]");
  if (!header || !["Enter", " "].includes(e.key)) return;
  e.preventDefault();
  const id = header.dataset.sourceId;
  if (S.focusedSource !== id) {
    S.focusedSource = id;
    tickCurrent();
  }
});
document.addEventListener("dblclick", e => {
  const panel = e.target.closest(".pvid");
  if (!panel) return;
  e.preventDefault();
});
document.addEventListener("fullscreenchange", () => {
  $$(".fs-btn").forEach(button => {
    const isFullscreen = document.fullscreenElement === button.closest(".pvid");
    button.title = isFullscreen ? "Thoát toàn màn hình" : "Toàn màn hình";
    button.setAttribute("aria-label", button.title);
  });
});
document.addEventListener("keydown", e => {
  if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName) || !["verify", "live"].includes(S.view)) return;
  const a = current(); if (!a) return;
  if (e.key === "d") act("dispatch", a.id); else if (e.key === "x") act("delete", a.id);
});

const dirty = () => { delete S.sigs.alarm; delete S.sigs.verify; };
const tickCurrent = () => (VIEWS[S.view] || {}).tick?.(S.view);

const VIEWS = {};

function updateLivePlaybackButton() {
  const button = $("#live-play-all");
  if (!button) return;
  const videos = $$(".demo-video", $("#view-live"));
  const allPlaying = videos.length > 0 && videos.every(video => !video.paused);
  button.disabled = videos.length === 0;
  button.textContent = allPlaying ? "Tạm dừng video" : "Phát tất cả video";
  button.setAttribute("aria-pressed", String(allPlaying));
}

VIEWS.dashboard = {
  tick() {
    const st = S.stats; if (!st) return;
    const sig = JSON.stringify([st, S.sources.map(s => [s.id, s.online])]);
    if (sig === S.sigs.dash) return; S.sigs.dash = sig;
    const on = S.sources.filter(s => s.online).length;
    const handled = st.dispatched + st.deleted;
    const precision = handled ? Math.round(st.dispatched / handled * 100) + "%" : "-";
    const max = Math.max(1, ...st.per_day.map(d => d.dispatched + d.deleted + d.pending));
    const bars = st.per_day.map((d, i) => {
      let y = 130; const x = 14 + i * 56, parts = [["pending", "#f0b43c"], ["deleted", "#6b7a88"], ["dispatched", "#ff5a3c"]];
      return parts.map(([k, c]) => { const h = d[k] / max * 110; y -= h; return h ? `<rect x="${x}" y="${y}" width="34" height="${h}" fill="${c}"/>` : ""; }).join("") +
        `<text x="${x + 17}" y="148" fill="#93a3b1" font-size="11" text-anchor="middle">${d.date}</text>`;
    }).join("");
    const wmax = Math.max(1, ...Object.values(st.by_weapon));
    const weapons = Object.entries(st.by_weapon).map(([k, n]) => `<div class="bar-row"><span>${esc(k)}</span><div class="bar"><i style="width:${n / wmax * 100}%"></i></div><b>${n}</b></div>`).join("") || '<div class="empty">Chưa có dữ liệu</div>';
    $("#view-dashboard").innerHTML = `
      <h2>Dashboard</h2>
      <div class="cards">
        <div class="stat"><b>${st.today}</b><span>Cảnh báo hôm nay</span></div>
        <div class="stat ${st.pending ? "hot" : ""}"><b>${st.pending}</b><span>Chờ xác minh</span></div>
        <div class="stat"><b>${st.dispatched}</b><span>Đã dispatch</span></div>
        <div class="stat"><b>${st.deleted}</b><span>Báo giả đã xóa</span></div>
        <div class="stat"><b>${precision}</b><span>Tỷ lệ cảnh báo đúng</span></div>
        <div class="stat"><b>${on}/${S.sources.length}</b><span>Thiết bị online</span></div>
      </div>
      <div class="dash-grid">
        <div class="box"><h3>Cảnh báo 7 ngày qua</h3>
          <svg viewBox="0 0 400 156" width="100%">${bars}</svg>
          <div class="legend"><span><i style="background:#ff5a3c"></i>Dispatch</span><span><i style="background:#6b7a88"></i>Đã xóa</span><span><i style="background:#f0b43c"></i>Đang chờ</span></div></div>
        <div class="box"><h3>Theo loại hung khí</h3>${weapons}</div>
        <div class="box"><h3>Thiết bị</h3>${S.sources.map(s => `<div class="list-row"><span class="dot ${s.online ? "on" : ""}"></span><span class="grow">${esc(s.name)}</span><span class="hint">${s.type}</span></div>`).join("") || '<div class="empty">Chưa có thiết bị</div>'}</div>
        <div class="box"><h3>Cảnh báo gần đây</h3>${st.recent.map(a => `<div class="list-row linkrow" data-act="${a.status === "pending" ? "open-alert" : ""}" data-id="${a.id}"><img src="${imgUrl(a)}" alt=""><div class="grow"><b>#${a.id}</b> ${esc(a.source_name)}<br><span class="hint">${wtext(a)} · ${fmt(a.created_at)}</span></div><span class="status ${a.status}">${a.status}</span></div>`).join("") || '<div class="empty">Chưa có cảnh báo</div>'}</div>
      </div>`;
  },
};

const statBits = s => {
  const t = s.telemetry || {}, b = [];
  if (t.temp != null) b.push(`${t.temp}°C`);
  if (t.wind != null) b.push(`gió ${t.wind} m/s`);
  if (t.sats != null) b.push(`${t.sats} sat`);
  if (t.signal != null) b.push(`sóng ${t.signal}%`);
  if (t.battery != null) b.push(`pin ${t.battery}%`);
  if (t.voltage != null) b.push(`${t.voltage} V`);
  if (t.flight_time) b.push(`${t.flight_time}`);
  if (s.resolution) b.push(s.resolution);
  if (s.online && s.fps) b.push(`${Math.round(s.fps)} fps`);
  return b.map(x => `<span>${esc(x)}</span>`).join("");
};
const hudText = s => {
  const t = s.telemetry || {}, l = [];
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
        <div class="live-toolbar">
          <button class="btn sm" id="live-play-all" disabled>Phát tất cả video</button>
          <button class="btn sm" id="live-grid-view" hidden>Trở về dạng lưới</button>
        </div>
        <div class="streams" id="streams"></div></div>`;
      S.liveStreamsSignature = null;
    }
  },
  tick() {
    const box = $("#streams"); if (!box) return;
    const sig = JSON.stringify(S.sources.map(s => [s.id, s.enabled, s.name, s.url, s.demo_video]));
    if (sig !== S.liveStreamsSignature) {
      S.liveStreamsSignature = sig;
      box.innerHTML = S.sources.map(s => `<div class="panel" id="p-${s.id}" data-id="${esc(s.id)}">
        <div class="pbar" data-source-id="${esc(s.id)}" role="button" tabindex="0" aria-label="Phóng to màn hình ${esc(s.name)}"><span class="dot"></span><b>${esc(s.name)}</b><span class="mode none">${s.type}</span><span class="pstats"></span></div>
        <div class="pvid"><div class="tracking-stage" data-source="${esc(s.id)}">${s.demo_video
          ? `<video class="demo-video" src="/source_video/${encodeURIComponent(s.id)}" controls playsinline loop preload="metadata"></video>`
          : `<img src="/video_feed/${encodeURIComponent(s.id)}" alt="${esc(s.name)}">`}
          <canvas class="tracking-overlay"></canvas></div>
          ${s.demo_video ? `<div class="demo-error" role="status"></div>` : ""}
          <div class="hud"></div>
          <div class="live-tag"><i></i><span>${s.demo_video ? "DEMO" : "LIVE"}</span></div>
          <button class="fs-btn" data-act="fs" title="Toàn màn hình">&#x26F6;</button></div>
        </div>`).join("")
        || '<div class="empty"><strong>Chưa có thiết bị</strong>Vào Cameras, Drones hoặc Robots để thêm.</div>';
      S.sources.filter(s => s.demo_video).forEach(s => {
        const panel = $(`#p-${s.id}`);
        const video = $(".demo-video", panel);
        connectDemoVideo(video, panel, s.id);
      });
    }
    updateLivePlaybackButton();
    $("#live-grid-view").hidden = !S.focusedSource;
    if (!S.sources.some(s => s.id === S.focusedSource)) S.focusedSource = null;
    box.classList.toggle("focused", !!S.focusedSource);
    box.classList.toggle("single-focused", !!S.focusedSource && S.sources.length === 1);
    const miniCount = Math.max(1, S.sources.length - 1);
    box.style.setProperty("--mini-count", miniCount);
    S.sources.forEach(s => {
      const p = $(`#p-${s.id}`);
      if (!p) return;
      const isMain = s.id === S.focusedSource;
      p.classList.toggle("focus-main", isMain);
      if (S.focusedSource) {
        p.style.gridColumn = isMain ? (S.sources.length === 1 ? "1" : "2") : "1";
        p.style.gridRow = isMain ? `1 / span ${miniCount}` : String(S.sources.filter(other => other.id !== S.focusedSource).findIndex(other => other.id === s.id) + 1);
      } else {
        p.style.gridColumn = "";
        p.style.gridRow = "";
      }
    });
    S.sources.forEach(s => {
      const p = $(`#p-${s.id}`); if (!p) return;
      $(".dot", p).classList.toggle("on", s.online);
      const t = s.telemetry || {}, mode = $(".mode", p);
      mode.textContent = t.mode || s.type; mode.classList.toggle("none", !t.mode);
      const stats = statBits(s), ps = $(".pstats", p);
      if (ps.dataset.v !== stats) { ps.innerHTML = stats; ps.dataset.v = stats; }
      $(".hud", p).textContent = hudText(s);
      $(".live-tag", p).classList.toggle("off", !s.online);
      if (!s.online) $(".live-tag span", p).textContent = "OFFLINE";
    });
  },
};

const demoVideoStates = new WeakMap();

function connectDemoVideo(video, panel, sourceId) {
  const canvas = $(".tracking-overlay", panel), stage = $(".tracking-stage", panel);
  const state = {
    timer: null, animationFrame: null, busy: false, pending: false, seekVersion: 0,
    detectionHistory: [], displayedTime: null, smoothedDetections: [],
  };
  demoVideoStates.set(video, state);
  const clearTimer = () => { clearTimeout(state.timer); state.timer = null; };
  const clearDetectionHistory = () => {
    state.detectionHistory = [];
    state.smoothedDetections = [];
    clearDemoDetections(canvas);
  };
  const clearOverlay = () => {
    state.smoothedDetections = [];
    clearDemoDetections(canvas);
  };
  const smoothCenters = (detections, mediaTime) => {
    const unmatched = new Set(state.smoothedDetections.map((_, index) => index));
    const tracks = detections.map(detection => {
      const [x1, y1, x2, y2] = detection.box;
      const measuredCenter = [(x1 + x2) / 2, (y1 + y2) / 2];
      let bestIndex = -1, bestDistance = Infinity, bestPrediction = null;
      unmatched.forEach(index => {
        const track = state.smoothedDetections[index];
        if (track.label !== detection.label) return;
        const dt = Math.max(0, Math.min(0.25, mediaTime - track.time));
        const predicted = [
          track.center[0] + track.velocity[0] * dt,
          track.center[1] + track.velocity[1] * dt,
        ];
        const distance = Math.hypot(
          measuredCenter[0] - predicted[0], measuredCenter[1] - predicted[1],
        );
        const allowance = Math.max(80, Math.hypot(x2 - x1, y2 - y1) * 2) + dt * 1800;
        if (distance <= allowance && distance < bestDistance) {
          bestIndex = index;
          bestDistance = distance;
          bestPrediction = {dt, center: predicted, track};
        }
      });
      if (bestIndex < 0) {
        return {...detection, center: measuredCenter, velocity: [0, 0], time: mediaTime};
      }

      unmatched.delete(bestIndex);
      const {dt, center: predicted, track} = bestPrediction;
      const residual = [
        measuredCenter[0] - predicted[0],
        measuredCenter[1] - predicted[1],
      ];
      const center = [
        predicted[0] + residual[0] * 0.8,
        predicted[1] + residual[1] * 0.8,
      ];
      const velocity = dt > 0.005
        ? track.velocity.map((value, index) =>
          Math.max(-2500, Math.min(2500, value + residual[index] * 0.06 / dt)))
        : track.velocity;
      return {...detection, center, velocity, time: mediaTime};
    });
    state.smoothedDetections = tracks;
    return tracks.map(detection => {
      const [x1, y1, x2, y2] = detection.box;
      const width = x2 - x1, height = y2 - y1;
      return {
        ...detection,
        box: [
          Math.round(detection.center[0] - width / 2),
          Math.round(detection.center[1] - height / 2),
          Math.round(detection.center[0] + width / 2),
          Math.round(detection.center[1] + height / 2),
        ],
      };
    });
  };
  const matchDetection = (detection, candidates, unmatched, travelAllowance = 0) => {
    const [x1, y1, x2, y2] = detection.box;
    const centerX = (x1 + x2) / 2, centerY = (y1 + y2) / 2;
    let bestIndex = -1, bestDistance = Infinity;
    unmatched.forEach(index => {
      const candidate = candidates[index];
      if (candidate.label !== detection.label) return;
      const [cx1, cy1, cx2, cy2] = candidate.box;
      const distance = Math.hypot(centerX - (cx1 + cx2) / 2, centerY - (cy1 + cy2) / 2);
      const allowance = Math.max(64, Math.hypot(x2 - x1, y2 - y1) * 1.5)
        + travelAllowance;
      if (distance <= allowance && distance < bestDistance) {
        bestIndex = index;
        bestDistance = distance;
      }
    });
    if (bestIndex >= 0) unmatched.delete(bestIndex);
    return bestIndex;
  };
  const renderOverlay = () => {
    state.displayedTime = video.currentTime;
    const history = state.detectionHistory;
    let beforeIndex = -1, afterIndex = -1;
    for (let index = 0; index < history.length; index++) {
      if (history[index].time <= state.displayedTime) beforeIndex = index;
      else { afterIndex = index; break; }
    }
    if (beforeIndex < 0) return clearOverlay();
    const before = history[beforeIndex];
    if (!before.detections.length || state.displayedTime - before.time > 0.75) {
      return clearOverlay();
    }
    const after = afterIndex >= 0 ? history[afterIndex] : null;
    const previous = beforeIndex > 0 ? history[beforeIndex - 1] : null;
    const unmatchedAfter = new Set(after?.detections.map((_, index) => index) || []);
    const unmatchedPrevious = new Set(previous?.detections.map((_, index) => index) || []);
    const detections = before.detections.map(detection => {
      let box = detection.box;
      if (after && after.time > before.time) {
        const afterIndex = matchDetection(
          detection, after.detections, unmatchedAfter,
          Math.min(300, (after.time - before.time) * 1200),
        );
        if (afterIndex >= 0) {
          const nextBox = after.detections[afterIndex].box;
          const ratio = (state.displayedTime - before.time) / (after.time - before.time);
          box = box.map((value, index) =>
            Math.round(value + (nextBox[index] - value) * ratio));
          return {...detection, box};
        }
      }
      if (!previous || !previous.detections.length || before.time <= previous.time) {
        return detection;
      }
      const previousIndex = matchDetection(
        detection, previous.detections, unmatchedPrevious,
        Math.min(300, (before.time - previous.time) * 1200),
      );
      if (previousIndex < 0) return detection;
      const oldBox = previous.detections[previousIndex].box;
      const elapsed = before.time - previous.time;
      const prediction = Math.min(0.25, Math.max(0, state.displayedTime - before.time));
      box = box.map((value, index) =>
        Math.round(value + (value - oldBox[index]) / elapsed * prediction));
      return {...detection, box};
    });
    drawDemoDetections(
      canvas, smoothCenters(detections, state.displayedTime), before.width, before.height,
    );
  };
  const animateOverlay = () => {
    state.animationFrame = null;
    renderOverlay();
    if (!video.paused && !video.ended) {
      state.animationFrame = requestAnimationFrame(animateOverlay);
    }
  };
  const startOverlayAnimation = () => {
    if (state.animationFrame === null) {
      state.animationFrame = requestAnimationFrame(animateOverlay);
    }
  };
  const analyze = async () => {
    if (state.busy) { state.pending = true; return; }
    if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || !video.videoWidth) return;
    state.busy = true;
    state.pending = false;
    const seekVersion = state.seekVersion;
    const startedAt = performance.now();
    try {
      const frame = document.createElement("canvas");
      const scale = Math.min(1, 1280 / video.videoWidth);
      frame.width = Math.round(video.videoWidth * scale);
      frame.height = Math.round(video.videoHeight * scale);
      const sampledAt = video.currentTime;
      frame.getContext("2d").drawImage(video, 0, 0, frame.width, frame.height);
      const blob = await new Promise(resolve => frame.toBlob(resolve, "image/jpeg", 0.75));
      if (!blob) throw new Error("Không thể đọc khung hình video");
      const response = await fetch(`/api/sources/${encodeURIComponent(sourceId)}/frame`, {
        method: "POST", headers: { "Content-Type": "image/jpeg" }, body: blob,
      });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || `HTTP ${response.status}`);
      }
      const result = await response.json();
      $(".demo-error", panel).textContent = "";
      if (seekVersion === state.seekVersion) {
        state.detectionHistory.push({
          time: sampledAt,
          detections: result.detections,
          width: result.width,
          height: result.height,
        });
        while (state.detectionHistory.length > 120) state.detectionHistory.shift();
        renderOverlay();
      }
    } catch (error) {
      $(".demo-error", panel).textContent = `Lỗi phân tích video: ${error.message}`;
      clearOverlay();
    } finally {
      state.busy = false;
      if (state.pending) analyze();
      else if (!video.paused && !video.ended) {
        const interval = 1000 / Math.max(1, Number(S.settings.detect_fps) || 45);
        const delay = Math.max(0, interval - (performance.now() - startedAt));
        state.timer = setTimeout(analyze, delay);
      }
    }
  };
  video.addEventListener("loadedmetadata", () => {
    stage.style.aspectRatio = `${video.videoWidth} / ${video.videoHeight}`;
    canvas.width = Math.min(1280, video.videoWidth);
    canvas.height = Math.round(video.videoHeight * canvas.width / video.videoWidth);
    renderOverlay();
  });
  video.addEventListener("play", () => {
    clearTimer();
    startOverlayAnimation();
    analyze();
  });
  const holdPausedFrame = () => {
    clearTimer();
    state.seekVersion++;
    if (state.animationFrame !== null) {
      cancelAnimationFrame(state.animationFrame);
      state.animationFrame = null;
    }
    clearDetectionHistory();
    renderOverlay();
    analyze();
  };
  video.addEventListener("pause", holdPausedFrame);
  video.addEventListener("ended", holdPausedFrame);
  video.addEventListener("play", updateLivePlaybackButton);
  video.addEventListener("pause", updateLivePlaybackButton);
  video.addEventListener("ended", updateLivePlaybackButton);
  video.addEventListener("seeking", () => {
    state.seekVersion++;
    clearDetectionHistory();
    renderOverlay();
  });
  video.addEventListener("seeked", () => {
    renderOverlay();
    analyze();
  });
  video.addEventListener("error", () => {
    $(".demo-error", panel).textContent = "Không thể phát video. Hãy dùng tệp MP4 hoặc WebM hợp lệ.";
  });
}

function drawDemoDetections(canvas, detections, width = canvas.width, height = canvas.height) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const scale = Math.max(1, canvas.width / 640);
  const scaleX = canvas.width / Math.max(1, width), scaleY = canvas.height / Math.max(1, height);
  ctx.lineWidth = 4 * scale;
  ctx.font = `${14 * scale}px sans-serif`;
  detections.forEach(d => {
    const [rawX1, rawY1, rawX2, rawY2] = d.box;
    const x1 = rawX1 * scaleX, y1 = rawY1 * scaleY;
    const x2 = rawX2 * scaleX, y2 = rawY2 * scaleY;
    const label = `${d.label} ${Number(d.conf).toFixed(2)}`;
    const labelHeight = 22 * scale, labelWidth = ctx.measureText(label).width + 10 * scale;
    ctx.strokeStyle = "#50dc53";
    ctx.fillStyle = "#50dc53";
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
    ctx.fillRect(x1, Math.max(0, y1 - labelHeight), labelWidth, labelHeight);
    ctx.fillStyle = "#fff";
    ctx.fillText(label, x1 + 5 * scale, Math.max(labelHeight * 0.75, y1 - 5 * scale));
  });
}

function clearDemoDetections(canvas) {
  canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
}

VIEWS.verify = {
  tick() {
    const a = current(), el = $("#view-verify");
    const sig = JSON.stringify([S.pending.map(x => [x.id, x.events.length, x.evidence_images?.length]), S.selected, S.logs[0]?.id]);
    if (sig === S.sigs.verify) return; S.sigs.verify = sig;
    if (!a) { el.innerHTML = `<h2>Alerts</h2><div class="box empty"><strong>Không có cảnh báo chờ xác minh</strong>Khi hệ thống phát hiện hung khí, ảnh sẽ hiện ở đây.</div>${logTable(S.logs.slice(0, 8))}`; return; }
    const idx = S.pending.findIndex(x => x.id === a.id) + 1;
    const selectedImage = S.selectedEvidence?.alertId === a.id ? S.selectedEvidence.image : null;
    const mainImage = selectedImage || imgUrl(a);
    const mainLabel = S.selectedEvidence?.alertId === a.id
      ? `Ảnh ${S.selectedEvidence.frame}` : "Ảnh phát hiện ban đầu";
    const selectedEvidence = (a.evidence_images || []).map(evidenceRecord).find(
      entry => `/alert_images/${encodeURIComponent(entry.image)}` === selectedImage);
    const imageDetections = selectedEvidence?.detections
      ?? (a.detections?.length ? a.detections : a.weapons);
    const imageCapturedAt = selectedEvidence?.captured_at || a.created_at;
    el.innerHTML = `<div class="vgrid">
      <div><div class="vtitle">Alert: ${a.id} / Client: ${esc(S.settings.site_name)} / Camera: ${esc(a.source_name)}</div>
        <div class="alert-image-view"><span class="alert-image-label" id="alert-image-label">${mainLabel}</span>
          <img id="alert-image" class="vimg" src="${mainImage}" alt="${mainLabel}">
          <canvas class="alert-detections-canvas"></canvas><canvas class="alert-magnifier" hidden></canvas></div>
        <label class="detection-label-toggle"><span>Hiển thị nhãn nhận diện</span>
          <input id="show-detection-labels" type="checkbox" role="switch" ${S.showDetectionLabels ? "checked" : ""}>
          <span class="toggle-slider" aria-hidden="true"></span></label>
        <div class="box alert-frame-info"><strong id="alert-frame-detections">${detectionInfo(imageDetections)}</strong><span class="hint" id="alert-frame-time">${fmt(imageCapturedAt)}</span></div>
        ${evidenceStrip(a, selectedImage)}
        <div class="vbtns"><button class="btn dispatch" data-act="dispatch" data-id="${a.id}" title="Phím tắt: D">Dispatch</button>
          <button class="btn" data-act="delete" data-id="${a.id}" title="Phím tắt: X">Delete alert</button>
          <button class="btn ghost" data-act="clear">Clear all</button></div>
        <div class="vmeta"><dl class="facts"><dt>Hung khí</dt><dd>${chips(a)}</dd>
          <dt>Độ tin cậy</dt><dd>${Math.round(a.max_conf * 100)}%</dd>
          <dt>Nguồn</dt><dd>${esc(a.source_name)} (${a.source_type})</dd>
          <dt>Vị trí</dt><dd>${esc(a.location) || "-"}</dd>
          <dt>Thời gian</dt><dd>${fmt(a.created_at)}</dd></dl>
          <h3>Timeline</h3>${timeline(a)}${noteBox(a)}</div></div>
      <div class="vside"><div class="total">Total: ${idx}/${S.pending.length}</div>
        ${S.pending.map(x => `<button class="thumb ${x.id === a.id ? "sel" : ""}" data-act="select" data-id="${x.id}" title="Alert ${x.id}"><img src="${imgUrl(x)}" alt="Alert ${x.id}"></button>`).join("")}</div></div>
      <h3 style="margin-top:16px">Messages</h3>${logTable(S.logs.slice(0, 8))}`;
    attachAlertMagnifier($(".alert-image-view", el));
    setupAlertDetectionOverlays(el, a, imageDetections);
  },
};

VIEWS.history = {
  async show() {
    const el = $("#view-history");
    el.innerHTML = `<div class="toolbar"><h2 class="grow" style="margin:0">Past Ops</h2>
      <select id="hf"><option value="">Tất cả</option><option value="dispatched">Đã dispatch</option><option value="deleted">Đã xóa</option></select></div><div id="hbody"></div>`;
    const rows = await api("/api/alerts?status=history");
    const draw = () => {
      const f = $("#hf").value, list = rows.filter(a => !f || a.status === f);
      $("#hbody").innerHTML = list.length ? `<table class="tbl"><thead><tr><th>Ảnh</th><th>Mã</th><th>Thời gian</th><th>Nguồn</th><th>Hung khí</th><th>Xử lý bởi</th><th>Kết quả</th><th>Ghi chú</th></tr></thead><tbody>${
        list.map(a => `<tr><td><img src="${imgUrl(a)}" alt="" data-act="zoom"></td><td>#${a.id}</td><td>${fmt(a.created_at)}</td><td>${esc(a.source_name)}</td><td>${wtext(a)}</td>
        <td>${esc(a.handled_by)}<br><span class="hint">${fmt(a.handled_at)}</span></td><td><span class="status ${a.status}">${a.status === "dispatched" ? "Dispatched" : "Deleted"}</span></td>
        <td>${a.events.filter(e => e.text.startsWith("Ghi chú")).map(e => esc(e.text)).join("<br>")}</td></tr>`).join("")}</tbody></table>`
        : '<div class="empty"><strong>Chưa có dữ liệu</strong>Các cảnh báo đã xử lý sẽ hiện ở đây.</div>';
    };
    $("#hf").onchange = draw; draw();
  },
};

const TYPE_NAME = { camera: "Camera", drone: "Drone", robot: "Robot" };
function deviceView(type) {
  return {
    async show() { await loadSources(); this.draw(); },
    draw() {
      const rows = S.sources.filter(s => s.type === type), el = $(`#view-dev-${type}`);
      const coordinates = type === "camera" ? "" : "<th>Tọa độ</th>";
      const hint = type === "camera" ? "" : `<div class="box" style="margin-top:14px"><h3>Gửi dữ liệu telemetry (pin, độ cao, tốc độ...)</h3>
        <p class="hint">Chương trình điều khiển ${type} gọi API này vài giây một lần. Các trường không bắt buộc: mode, battery, voltage, signal, altitude, speed, heading, sats, temp, wind, flight_time, lat, lon.</p>
        <pre>curl -X POST http://127.0.0.1:5000/api/sources/&lt;ID&gt;/telemetry -H "Content-Type: application/json" -d '{"mode":"AUTO","battery":76,"altitude":46,"speed":5.4,"sats":15,"flight_time":"4:22"}'</pre></div>`;
      el.innerHTML = `<div class="toolbar"><h2 class="grow" style="margin:0">${TYPE_NAME[type]}s</h2><button class="btn primary" id="add-${type}">Thêm ${TYPE_NAME[type].toLowerCase()}</button></div>
        ${rows.length ? `<table class="tbl"><thead><tr><th></th><th>Tên</th><th>ID</th><th>Nguồn video</th><th>Vị trí</th>${coordinates}<th></th></tr></thead><tbody>${
          rows.map(s => `<tr><td><span class="dot ${s.online ? "on" : ""}" title="${s.online ? "online" : "offline"}"></span></td><td>${esc(s.name)}${s.enabled ? "" : ' <span class="hint">(đang tắt)</span>'}</td><td><code>${esc(s.id)}</code></td><td>${s.demo_video ? `Video demo (${esc(s.video_name)})` : esc(s.url)}</td><td>${esc(s.location)}</td>
          ${type === "camera" ? "" : `<td>${s.lat != null ? `${s.lat}, ${s.lon}` : "-"}</td>`}
          <td><button class="btn sm edit" data-id="${s.id}">Sửa</button> <button class="btn sm del" data-id="${s.id}">Xóa</button></td></tr>`).join("")}</tbody></table>`
          : `<div class="box empty"><strong>Chưa có ${type}</strong>Bấm "Thêm" để khai báo nguồn video đầu tiên.</div>`}${hint}`;
      $(`#add-${type}`).onclick = () => this.form(null);
      $$(".edit", el).forEach(b => b.onclick = () => this.form(S.sources.find(s => s.id === b.dataset.id)));
      $$(".del", el).forEach(b => b.onclick = async () => {
        if (!confirm("Xóa thiết bị này?")) return;
        try {
          await api(`/api/sources/${b.dataset.id}`, "DELETE");
          toast("Đã xóa thiết bị");
          await this.show();
        } catch (error) {
          toast(`Không thể xóa thiết bị (${error.message})`);
        }
      });
    },
    form(s) {
      const d = $("#dlg"); d.className = "";
      const sourceFields = type === "camera" ? `<label>Nguồn<select name="source_mode">
          <option value="url">Camera hoặc URL video</option><option value="video">Tải video demo lên</option></select></label>
        <div id="source-url-field"><label>Địa chỉ nguồn<input name="url" placeholder="0 (webcam), rtsp://... hoặc http://..."></label></div>
        <div id="source-video-field" hidden><label>Tệp video MP4/WebM<input name="video" type="file" accept=".mp4,.webm,video/mp4,video/webm"></label>
          <span class="hint" id="source-video-current"></span></div>`
        : `<label>Nguồn video<input name="url" required placeholder="0 (webcam) | rtsp://... | http://... | data/videos/demo.mp4"></label>`;
      const coordinateFields = type === "camera" ? "" : `<div class="row2"><label>Vĩ độ<input name="lat" type="number" step="any"></label><label>Kinh độ<input name="lon" type="number" step="any"></label></div>`;
      const enabledField = type === "camera" ? "" : `<label class="chk"><input name="enabled" type="checkbox"> Bật thiết bị này</label>`;
      d.innerHTML = `<form id="dev-form"><h3>${s ? "Sửa" : "Thêm"} ${TYPE_NAME[type].toLowerCase()}</h3><div class="sform" style="max-width:none">
        <label>Tên<input name="name" required></label>
        ${sourceFields}
        <label>Mô tả vị trí<input name="location"></label>
        ${coordinateFields}${enabledField}</div>
        <div class="dlg-actions"><button type="button" class="btn" id="dev-cancel">Hủy</button><button class="btn primary">Lưu</button></div></form>`;
      const f = $("#dev-form"), E = f.elements;
      E.name.value = s?.name ?? ""; E.location.value = s?.location ?? "";
      if (type === "camera") {
        E.source_mode.value = s?.demo_video ? "video" : "url";
        E.url.value = s?.demo_video ? "" : s?.url ?? "";
        $("#source-video-current").textContent = s?.demo_video ? `Video hiện tại: ${s.video_name}. Chọn tệp mới để thay thế.` : "";
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
        E.lat.value = s?.lat ?? ""; E.lon.value = s?.lon ?? "";
        E.enabled.checked = s ? !!s.enabled : true;
      }
      $("#dev-cancel").onclick = () => d.close();
      f.onsubmit = async e => {
        e.preventDefault();
        const body = type === "camera"
          ? new FormData()
          : { type, name: E.name.value, url: E.url.value, location: E.location.value, lat: E.lat.value, lon: E.lon.value, enabled: E.enabled.checked };
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
        try { await api(s ? `/api/sources/${s.id}` : "/api/sources", s ? "PUT" : "POST", body); d.close(); toast("Đã lưu thiết bị"); await this.show(); }
        catch (err) { toast("Lưu thất bại, kiểm tra lại thông tin"); }
      };
      d.onclick = null; d.showModal();
    },
  };
}
["camera", "drone", "robot"].forEach(t => VIEWS[`dev-${t}`] = deviceView(t));

VIEWS.map = {
  show() {
    $("#view-map").innerHTML = `<div class="mapbox big" id="big-map"></div>`;
    S.maps.big = makeMap($("#big-map")); setTimeout(() => S.maps.big?.m.invalidateSize(), 80);
  },
  tick() { updateMap(S.maps.big); },
};

function settingsForm(viewId, title, fields, extra = "", description = "", saveAfterExtra = false) {
  const el = $(`#view-${viewId}`);
  const groups = new Map();
  fields.forEach(field => {
    const section = field.section || "Cài đặt chung";
    if (!groups.has(section)) groups.set(section, []);
    groups.get(section).push(field);
  });
  const fieldHtml = field => {
    const cls = `field${field.wide || field.type === "checkbox" || field.type === "switch" ? " field-wide" : ""}`;
    const hint = field.hint ? `<span class="hint">${field.hint}</span>` : "";
    if (field.type === "checkbox") return `<label class="chk ${cls}"><input type="checkbox" name="${field.k}"> ${field.label}${hint}</label>`;
    if (field.type === "switch") return `<div class="theme-setting ${cls}"><span>${field.offLabel}</span><label class="switch"><input type="checkbox" name="${field.k}" aria-label="${field.label}"><span class="switch-slider"></span></label><span>${field.onLabel}</span><span class="hint">${field.label}</span></div>`;
    if (field.type === "select") return `<label class="${cls}">${field.label}<select name="${field.k}">${field.options.map(([value, label]) => `<option value="${value}">${label}</option>`).join("")}</select>${hint}</label>`;
    return `<label class="${cls}">${field.label}<input type="${field.type || "text"}" name="${field.k}" ${field.step ? `step="${field.step}"` : ""} ${field.min !== undefined ? `min="${field.min}"` : ""} ${field.max !== undefined ? `max="${field.max}"` : ""}>${hint}</label>`;
  };
  const sections = [...groups.entries()].map(([section, sectionFields]) =>
    `<section class="settings-card"><header class="settings-card-header"><h3>${section}</h3></header><div class="settings-fields">${sectionFields.map(fieldHtml).join("")}</div></section>`
  ).join("");
  const saveButton = `<div class="settings-actions${saveAfterExtra ? " notifications-save" : ""}"><button class="btn primary" ${saveAfterExtra ? `type="submit" form="sf-${viewId}"` : ""}>Lưu thay đổi</button></div>`;
  el.innerHTML = `<header class="admin-page-header"><h2>${title}</h2>${description ? `<p>${description}</p>` : ""}</header>
    <form class="settings-form" id="sf-${viewId}">${sections}${saveAfterExtra ? "" : saveButton}</form>${extra}${saveAfterExtra ? saveButton : ""}`;
  const form = $(`#sf-${viewId}`), E = form.elements;
  fields.forEach(f => {
    if (f.type === "checkbox") E[f.k].checked = !!S.settings[f.k];
    else if (f.type === "switch") E[f.k].checked = S.settings[f.k] === f.onValue;
    else E[f.k].value = S.settings[f.k] ?? "";
  });
  const themeSwitch = fields.find(f => f.type === "switch");
  if (themeSwitch) E[themeSwitch.k].onchange = async () => {
    const body = { [themeSwitch.k]: E[themeSwitch.k].checked ? themeSwitch.onValue : themeSwitch.offValue };
    try {
      S.settings = await api("/api/settings", "PUT", body);
      applySettings();
      toast("Đã đổi chế độ giao diện");
    } catch (error) {
      E[themeSwitch.k].checked = S.settings[themeSwitch.k] === themeSwitch.onValue;
      toast(`Không thể đổi chế độ giao diện (${error.message})`);
    }
  };
  form.onsubmit = async e => {
    e.preventDefault(); const body = {};
    fields.forEach(f => {
      body[f.k] = f.type === "checkbox" ? E[f.k].checked
        : f.type === "switch" ? (E[f.k].checked ? f.onValue : f.offValue)
          : E[f.k].value;
    });
    S.settings = await api("/api/settings", "PUT", body);
    applySettings();
    toast("Đã lưu cài đặt");
  };
}
VIEWS.site = { show() { settingsForm("site", "Site", [
  { k: "site_name", label: "Tên địa điểm", section: "Thông tin địa điểm" },
  { k: "site_address", label: "Địa chỉ", section: "Thông tin địa điểm", wide: true },
  { k: "site_lat", label: "Vĩ độ", type: "number", step: "any", section: "Vị trí trên bản đồ" },
  { k: "site_lon", label: "Kinh độ", type: "number", step: "any", section: "Vị trí trên bản đồ" },
], "", "Quản lý thông tin địa điểm và tọa độ trung tâm được dùng trên bản đồ."); } };
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
VIEWS.settings = { show() { settingsForm("settings", "Settings", [
  { k: "theme", label: "Chế độ tối", type: "switch", offValue: "light", onValue: "dark", offLabel: "Sáng", onLabel: "Tối", section: "Giao diện" },
  { k: "operator", label: "Tên nhân viên trực", hint: "Tên này xuất hiện trong lịch sử thao tác dispatch và xóa cảnh báo.", section: "Trực ca và cảnh báo" },
  { k: "sound", label: "Phát âm báo khi có cảnh báo mới", type: "checkbox", section: "Trực ca và cảnh báo" },
  ...DETECTION_CLASSES.map(([name, label]) => ({
    k: `${name}_conf_threshold`,
    label: `Ngưỡng tin cậy ${label} (${name})`,
    type: "number", min: "0", max: "1", step: "0.01",
    hint: "Ngưỡng cao lọc dự đoán yếu nhiều hơn nhưng có thể bỏ sót vật thể thật.",
    section: "Ngưỡng nhận diện theo lớp",
  })),
  { k: "confirm_frames", label: "Số lần nhận diện liên tiếp để tạo cảnh báo", type: "number", section: "Nhận diện" },
  { k: "alert_cooldown", label: "Thời gian chờ giữa hai cảnh báo cùng thiết bị (giây)", type: "number", section: "Nhận diện" },
  { k: "imgsz", label: "Kích thước ảnh đưa vào model", type: "number", hint: "Tăng kích thước có thể hỗ trợ vật thể nhỏ hoặc ở xa nhưng xử lý chậm hơn.", section: "Hiệu năng xử lý" },
  { k: "detect_fps", label: "Số lần nhận diện tối đa mỗi giây cho mỗi thiết bị", type: "number", hint: "Mặc định tối đa 45 lần/giây. Đây là mức trần, không phải FPS đảm bảo; tốc độ thực tế phụ thuộc phần cứng và số nguồn chạy cùng lúc.", section: "Hiệu năng xử lý" },
], "", "Cấu hình giao diện, xử lý cảnh báo và hiệu năng nhận diện."); } };
VIEWS.notify = { show() {
  settingsForm("notify", "Notifications", [
    { k: "telegram_enabled", label: "Gửi thông báo tới điện thoại khi Dispatch", type: "checkbox", section: "Gửi thông báo" },
    { k: "telegram_token", label: "Bot token", type: "password", section: "Gửi thông báo" }],
    `<div class="box mobile-notifications">
      <h3>Thiết bị di động nhận thông báo</h3>
      <p class="hint">Trên mỗi điện thoại, mở bot Telegram và gửi /start. Sau đó nhập tên thiết bị và Chat ID bên dưới. Bỏ chọn “Nhận thông báo” để tạm ngừng gửi tới thiết bị.</p>
      <div id="mobile-device-list" class="mobile-device-list"><span class="hint">Đang tải thiết bị...</span></div>
      <button class="btn sm" id="add-mobile-device" type="button">Thêm thiết bị di động</button>
      <form id="mobile-device-form" class="mobile-device-form" hidden>
        <label>Tên thiết bị<input name="name" required maxlength="80" placeholder="Ví dụ: Điện thoại trực ca"></label>
        <label>Chat ID Telegram<input name="chat_id" required inputmode="numeric" placeholder="Nhập Chat ID"></label>
        <div class="mobile-device-actions"><button class="btn primary sm" type="submit">Thêm</button>
          <button class="btn sm" id="cancel-mobile-device" type="button">Hủy</button></div>
      </form>
      <button class="btn sm" id="tg-test" type="button">Gửi tin thử tới tất cả thiết bị đang bật</button>
    </div>`, "Thiết lập kênh Telegram và quản lý các điện thoại nhận thông báo.", true);
  const list = $("#mobile-device-list");
  const drawDevices = async () => {
    try {
      const devices = await api("/api/mobile-devices");
      list.innerHTML = devices.length
        ? devices.map(device => `<div class="mobile-device-row">
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
            <button class="btn sm" type="button" data-mobile-delete="${device.id}">Xóa</button></div>`).join("")
        : '<div class="empty">Chưa có thiết bị di động nào.</div>';
    } catch (error) {
      list.innerHTML = '<div class="empty">Không tải được danh sách thiết bị di động.</div>';
      toast(`Không tải được thiết bị di động (${error.message})`);
    }
  };
  const form = $("#mobile-device-form");
  $("#add-mobile-device").onclick = () => { form.hidden = !form.hidden; };
  $("#cancel-mobile-device").onclick = () => { form.reset(); form.hidden = true; };
  form.onsubmit = async event => {
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
  list.onclick = async event => {
    const testButton = event.target.closest("[data-mobile-test]");
    const deleteButton = event.target.closest("[data-mobile-delete]");
    const editButton = event.target.closest("[data-mobile-edit]");
    const cancelButton = event.target.closest("[data-mobile-edit-cancel]");
    if (editButton) {
      list.querySelector(`[data-mobile-edit-form="${editButton.dataset.mobileEdit}"]`).hidden = false;
      return;
    }
    if (cancelButton) {
      list.querySelector(`[data-mobile-edit-form="${cancelButton.dataset.mobileEditCancel}"]`).hidden = true;
      return;
    }
    try {
      if (testButton) {
        const result = await api(`/api/mobile-devices/${testButton.dataset.mobileTest}/test`, "POST");
        toast(result.info);
      } else if (deleteButton) {
        if (!confirm("Xóa thiết bị di động này?")) return;
        await api(`/api/mobile-devices/${deleteButton.dataset.mobileDelete}`, "DELETE");
        toast("Đã xóa thiết bị di động");
        await drawDevices();
      }
    } catch (error) {
      toast(`Không thể xử lý thiết bị di động (${error.message})`);
    }
  };
  list.onchange = async event => {
    const checkbox = event.target.closest("[data-mobile-enabled]");
    if (!checkbox) return;
    try {
      await api(`/api/mobile-devices/${checkbox.dataset.mobileEnabled}`, "PUT", { enabled: checkbox.checked });
      toast(checkbox.checked ? "Đã bật nhận thông báo cho thiết bị" : "Đã tắt nhận thông báo cho thiết bị");
      await drawDevices();
    } catch (error) {
      checkbox.checked = checkbox.dataset.enabled === "true";
      toast(`Không thể cập nhật thiết bị (${error.message})`);
    }
  };
  list.onsubmit = async event => {
    const form = event.target.closest("[data-mobile-edit-form]");
    if (!form) return;
    event.preventDefault();
    const name = new FormData(form).get("name");
    try {
      await api(`/api/mobile-devices/${form.dataset.mobileEditForm}`, "PUT", { name });
      toast("Đã cập nhật tên thiết bị");
      await drawDevices();
    } catch (error) {
      toast(`Không thể sửa tên thiết bị (${error.message})`);
    }
  };
  drawDevices();
} };

VIEWS.logs = { async show() {
  S.logs = await api("/api/logs");
  $("#view-logs").innerHTML = `<header class="admin-page-header"><h2>System Log</h2><p>Lịch sử sự kiện và hoạt động gần đây của hệ thống.</p></header>
    <section class="settings-card log-card"><header class="settings-card-header"><h3>Nhật ký hoạt động</h3><span class="count-badge">${S.logs.length} mục</span></header>
    ${logTable(S.logs)}</section>`;
} };

async function loadSources() { S.sources = await api("/api/sources"); }

async function refresh(force) {
  if (S.refreshing) return;
  S.refreshing = true;
  try {
    const [src, pend] = await Promise.all([api("/api/sources"), api("/api/alerts?status=pending")]);
    S.sources = src; S.pending = pend;
    if (force || S.tickN++ % 3 === 0) { [S.stats, S.logs] = await Promise.all([api("/api/stats"), api("/api/logs")]); }
    $("#conn").textContent = "Đã kết nối"; $("#conn").classList.remove("bad");
  } catch (e) { $("#conn").textContent = "Mất kết nối"; $("#conn").classList.add("bad"); return; }
  finally { S.refreshing = false; }

  const fresh = S.pending.filter(a => !S.known.has(a.id));
  fresh.forEach(a => S.known.add(a.id));
  if (fresh.length && !S.first) {
    beep();
    const selectedIsPending = S.pending.some(a => a.id === S.selected);
    if (S.view !== "verify" || !selectedIsPending) S.selected = fresh[0].id;
    toast(`Có ${fresh.length} cảnh báo mới cần xác minh`, "Mở Alerts", () => showView("verify"));
  }
  S.first = false;

  const b = $("#badge"); b.hidden = !S.pending.length; b.textContent = S.pending.length;
  document.title = (S.pending.length ? `(${S.pending.length}) ` : "") + "SAFESIGHT";
  tickCurrent();
}

async function start() {
  buildShell();
  S.settings = await api("/api/settings"); applySettings();
  setInterval(() => $("#clock").textContent = new Date().toLocaleTimeString("vi-VN"), 1000);
  await refresh(true);
  showView("dashboard");
  setInterval(refresh, 2000);
}
start();

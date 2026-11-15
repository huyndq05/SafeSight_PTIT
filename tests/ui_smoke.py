"""Local browser smoke test using isolated SQLite data and mocked notifications.

Run: python tests/ui_smoke.py (requires playwright and installed Chrome).
"""

import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np
from flask import Response
from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server
from werkzeug.serving import WSGIRequestHandler

from weapon_detection import config
from weapon_detection.storage import db
import weapon_detection.web.app as web


class QuietHandler(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        pass


def main():
    output = Path(tempfile.gettempdir()) / "safesight-ui-review"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        with (
            patch.object(config, "DB_PATH", root / "ui.db"),
            patch.object(config, "ALERT_DIR", root),
            patch.object(
                web.notifier, "send_dispatch", return_value=(True, "Test log only")
            ) as dispatch_mock,
        ):
            db.init()
            db.set_settings({"sound": False, "site_name": "SafeSight Test"})
            for source in db.list_sources():
                db.delete_source(source["id"])
            frame = np.full((540, 960, 3), (48, 58, 68), np.uint8)
            cv2.putText(
                frame,
                "SAFESIGHT - TEST CAMERA",
                (170, 230),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (230, 230, 230),
                2,
            )
            cv2.imwrite(str(root / "fixture.jpg"), frame)
            jpeg = (root / "fixture.jpg").read_bytes()
            original_feed = web.app.view_functions["video_feed"]
            portrait = cv2.imencode(".jpg", cv2.resize(frame, (360, 640)))[1].tobytes()
            square = cv2.imencode(".jpg", cv2.resize(frame, (480, 480)))[1].tobytes()
            web.app.view_functions["video_feed"] = lambda sid: Response(
                portrait if sid == "test1" else square if sid == "test2" else jpeg,
                mimetype="image/jpeg",
            )
            try:
                for index in range(4):
                    src = dict(
                        id=f"test{index}",
                        name=f"Camera {index + 1}" if index != 3 else "Camera Cổng Đông",
                        type="camera",
                        url="0",
                        location=f"Gate {index + 1}",
                        lat=None,
                        lon=None,
                        enabled=int(index == 0),
                    )
                    db.save_source(src)
                    detections = [{"label": "knife", "conf": 0.91, "box": (430, 300, 540, 390)}]
                    aid = db.create_alert(src, detections, "fixture.jpg")
                    for evidence_index in range(1, 4):
                        image_name = f"evidence-{evidence_index}.jpg"
                        (root / image_name).write_bytes(jpeg)
                        db.add_alert_evidence(aid, image_name, detections, datetime.now())
                server = make_server(
                    "127.0.0.1", 0, web.app, threaded=True, request_handler=QuietHandler
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    with sync_playwright() as pw:
                        browser = pw.chromium.launch(channel="chrome", headless=True)
                        page = browser.new_page(
                            viewport={"width": 1600, "height": 1000}, device_scale_factor=1
                        )
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        # Test the app's offline map fallback; do not depend on external CDNs.
                        page.route("https://**/*", lambda route: route.abort())
                        page.goto(
                            f"http://127.0.0.1:{server.server_port}", wait_until="networkidle"
                        )
                        if "/login" in page.url:
                            page.screenshot(path=str(output / "login-setup.png"), full_page=True)
                            page.locator("input[name=display_name]").fill("Test Operator")
                            page.locator("input[name=username]").fill("admin-test")
                            page.locator("input[name=password]").fill("BrowserTest123!")
                            page.get_by_role("button", name="Tạo tài khoản", exact=True).click()
                            expect(page.locator("input[name=display_name]")).to_have_count(0)
                            page.locator("input[name=username]").fill("admin-test")
                            page.locator("input[name=password]").fill("BrowserTest123!")
                            page.screenshot(path=str(output / "login.png"), full_page=True)
                            page.get_by_role(
                                "button", name="Đăng nhập và nhận ca", exact=True
                            ).click()
                            page.wait_for_url(f"http://127.0.0.1:{server.server_port}/")
                        expect(page.locator("#view-live")).to_be_visible()
                        expect(page.locator("#view-live .live-queue")).to_have_count(0)
                        page.locator(".nav[data-view=live]").click()
                        page.locator("[data-live-mode=simple]").click()
                        expect(page.locator("[data-live-mode=simple]")).to_have_attribute(
                            "aria-pressed", "true"
                        )
                        expect(page.locator("body")).to_have_class(
                            __import__("re").compile(r".*simplified-shell.*")
                        )
                        assert abs(page.locator(".topbar").bounding_box()["height"] - 28) <= 1
                        assert abs(page.locator("#sidebar").bounding_box()["width"] - 44) <= 1
                        expect(page.locator("#p-test0 .pbar")).to_be_hidden()
                        assert (
                            page.locator("#streams").evaluate("(el) => getComputedStyle(el).gap")
                            == "0px"
                        )
                        assert (
                            page.locator("#p-test0 img").evaluate(
                                '(el) => new URL(el.src).searchParams.get("simple")'
                            )
                            == "1"
                        )
                        page.screenshot(path=str(output / "live-simplified.png"), full_page=True)
                        page.locator(".nav[data-view=live]").click()
                        page.locator("[data-live-mode=full]").click()
                        expect(page.locator("#p-test0 .pbar")).to_be_visible()
                        expect(page.locator("[data-live-mode=full]")).to_have_attribute(
                            "aria-pressed", "true"
                        )
                        assert abs(page.locator(".topbar").bounding_box()["height"] - 40) <= 1
                        # Camera OpenCV output and demo Canvas must share colors and label format.
                        from weapon_detection.detection.model import draw_detections
                        from weapon_detection.detection.presentation import detection_label

                        sample = {"label": "knife", "conf": 0.925, "box": [20, 60, 120, 260]}
                        server_frame = draw_detections(np.zeros((320, 180, 3), np.uint8), [sample])
                        overlay_sample = page.evaluate(
                            """d => {
                            const canvas = document.createElement('canvas');
                            canvas.width = 180; canvas.height = 320;
                            canvas.style.width = '180px'; canvas.style.height = '320px';
                            document.body.appendChild(canvas);
                            const ctx = canvas.getContext('2d'), labels = [];
                            const originalText = ctx.fillText.bind(ctx);
                            ctx.fillText = (text, ...args) => { labels.push(text); originalText(text, ...args); };
                            drawDemoDetections(canvas, [d], 180, 320);
                            const result = {pixel: [...ctx.getImageData(20, 160, 1, 1).data], labels};
                            canvas.remove();
                            return result;
                        }""",
                            sample,
                        )
                        assert overlay_sample["pixel"][:3] == server_frame[160, 20].tolist()[::-1]
                        assert overlay_sample["labels"] == [detection_label(sample)]
                        # Upload playback is available before processing; processing is explicit.
                        scan_state = {"ready": False, "posts": 0}

                        def analysis_route(route):
                            if route.request.method == "POST":
                                scan_state["posts"] += 1
                                scan_state["ready"] = True
                            import json

                            result = (
                                dict(
                                    width=640,
                                    height=360,
                                    frames=[dict(time=0, detections=[sample])],
                                )
                                if "results=1" in route.request.url
                                else dict(
                                    state="ready" if scan_state["ready"] else "idle",
                                    progress=100 if scan_state["ready"] else 0,
                                )
                            )
                            route.fulfill(content_type="application/json", body=json.dumps(result))

                        page.route("**/api/sources/demo-ui/analysis*", analysis_route)
                        page.evaluate("""() => {
                            const panel = document.createElement('div'); panel.id = 'demo-ui-test';
                            panel.innerHTML = `<div class="demo-tools"><button class="video-version active" data-version="original">Original</button><button class="video-version" data-version="detected" disabled>Detected</button><button class="process-video">Process</button></div><div class="scan-progress"><i></i><span class="scan-percent"></span><span class="scan-progress-label"></span></div><div style="position:relative;width:640px;height:360px"><video controls></video><canvas class="tracking-overlay" style="width:640px;height:360px"></canvas></div><div class="demo-error"></div>`;
                            document.body.appendChild(panel);
                            connectDemoVideo(panel.querySelector('video'), panel, 'demo-ui');
                        }""")
                        demo = page.locator("#demo-ui-test")
                        expect(demo.locator(".scan-progress-label")).to_have_text("Chưa xử lý")
                        assert not demo.locator("video").evaluate("(video) => video.controls")
                        assert scan_state["posts"] == 0
                        expect(demo.locator("[data-version=detected]")).to_be_disabled()
                        demo.locator(".process-video").click()
                        expect(demo.locator(".scan-percent")).to_have_text("100%")
                        expect(demo.locator("[data-version=detected]")).to_be_enabled()
                        assert scan_state["posts"] == 1
                        demo.locator("[data-version=detected]").click()
                        assert (
                            demo.locator("canvas").evaluate(
                                '(canvas) => canvas.getContext("2d").getImageData(20,160,1,1).data[3]'
                            )
                            > 0
                        )
                        demo.evaluate("""panel => {
                            panel.classList.add('simplified-live');
                            panel.querySelector('canvas').parentElement.classList.add('streams');
                        }""")
                        expect(demo.locator("canvas")).to_be_visible()
                        assert (
                            demo.locator("canvas").evaluate(
                                '(canvas) => canvas.getContext("2d").getImageData(20,160,1,1).data[3]'
                            )
                            > 0
                        )
                        demo.locator("[data-version=original]").click()
                        assert (
                            demo.locator("canvas").evaluate(
                                '(canvas) => canvas.getContext("2d").getImageData(20,160,1,1).data[3]'
                            )
                            == 0
                        )
                        demo.evaluate("""panel => {
                            panel.classList.add('simplified-live');
                            const video = panel.querySelector('video');
                            let paused = true;
                            window.simplePlaybackCalls = {play:0,pause:0};
                            Object.defineProperty(video,'paused',{get:()=>paused,configurable:true});
                            video.play = () => { paused=false; simplePlaybackCalls.play++; return Promise.resolve(); };
                            video.pause = () => { paused=true; simplePlaybackCalls.pause++; };
                        }""")
                        demo.locator("video").dispatch_event("click")
                        assert page.evaluate("simplePlaybackCalls.play") == 1
                        demo.locator("video").dispatch_event("click")
                        assert page.evaluate("simplePlaybackCalls.pause") == 1
                        demo.locator("video").dispatch_event("keydown", {"key": "Enter"})
                        assert page.evaluate("simplePlaybackCalls.play") == 2
                        page.evaluate('document.querySelector("#demo-ui-test").remove()')
                        page.evaluate(
                            'window.searchOriginalPanel = document.querySelector("#p-test3")'
                        )
                        page.locator("#live-search").fill(" CONG DONG ")
                        expect(page.locator("#streams .panel:visible")).to_have_count(1)
                        expect(page.locator("#p-test3")).to_be_visible()
                        assert page.evaluate(
                            'window.searchOriginalPanel === document.querySelector("#p-test3")'
                        )
                        page.locator("#live-search").fill("khong-ton-tai")
                        expect(page.locator(".filter-empty")).to_be_visible()
                        page.locator("#live-search").fill("")
                        expect(page.locator("#streams .panel:visible")).to_have_count(4)
                        page.locator('.nav[data-view="dev-camera"]').click()
                        page.locator("#camera-search").fill("cong DONG")
                        camera_rows = page.locator(
                            "#view-dev-camera tbody tr[data-source-name]:visible"
                        )
                        expect(camera_rows).to_have_count(1)
                        expect(camera_rows.first).to_contain_text("Camera Cổng Đông")
                        page.locator("#camera-search").fill("khong-ton-tai")
                        expect(camera_rows).to_have_count(0)
                        expect(page.locator("#camera-search-empty")).to_be_visible()
                        page.locator("#camera-search").fill("")
                        expect(camera_rows).to_have_count(4)
                        page.locator('.nav[data-view="live"]').click()
                        page.locator("#live-filter").select_option("drone")
                        expect(page.locator(".filter-empty")).to_be_visible()
                        expect(page.locator("#streams .panel:visible")).to_have_count(0)
                        page.locator("#live-filter").select_option("all")
                        page.locator("#live-layout").select_option("2")
                        tiles = page.locator("#streams .panel:visible")
                        dimensions = tiles.evaluate_all(
                            "(els) => els.map(el => ({width:el.getBoundingClientRect().width,height:el.getBoundingClientRect().height}))"
                        )
                        assert (
                            max(d["height"] for d in dimensions)
                            - min(d["height"] for d in dimensions)
                            < 1
                        ), dimensions
                        assert (
                            max(d["width"] for d in dimensions)
                            - min(d["width"] for d in dimensions)
                            < 1
                        ), dimensions
                        preview = page.locator("#p-test1 .tracking-stage").bounding_box()
                        assert abs(preview["width"] / preview["height"] - 16 / 9) < 0.01
                        page.locator("#p-test1 .pbar").click()
                        expect(page.locator("#p-test1")).to_have_class("panel focus-main")
                        focused = page.locator("#p-test1 .tracking-stage").bounding_box()
                        assert (
                            focused["width"] > preview["width"]
                            and focused["height"] > preview["height"]
                        )
                        assert abs(focused["width"] / focused["height"] - 16 / 9) < 0.01
                        assert focused["y"] + focused["height"] <= page.viewport_size["height"] + 2
                        assert (
                            page.locator("#p-test1 img").evaluate(
                                "(img) => getComputedStyle(img).objectFit"
                            )
                            == "contain"
                        )
                        page.locator("#p-test1 .fs-btn").click()
                        page.wait_for_function("!!document.fullscreenElement")
                        fullscreen = page.locator("#p-test1 .tracking-stage").bounding_box()
                        assert abs(fullscreen["width"] / fullscreen["height"] - 16 / 9) < 0.01
                        assert (
                            fullscreen["y"] + fullscreen["height"]
                            <= page.viewport_size["height"] + 2
                        )
                        page.evaluate("document.exitFullscreen()")
                        page.wait_for_function("!document.fullscreenElement")
                        page.locator("#live-grid-view").click()
                        # Regression: two uploaded videos must not collapse the focused
                        # panel to the 190px height of the only thumbnail row.
                        page.route(
                            "**/api/sources/test*/analysis",
                            lambda route: route.fulfill(
                                content_type="application/json",
                                body='{"state":"idle","progress":0}',
                            ),
                        )
                        page.evaluate("""() => {
                            window.focusTestSources = S.sources;
                            S.refreshing = true;
                            S.sources = S.sources.slice(0,2).map(source => ({...source,demo_video:true,
                              name:'Video_Tự_quay_kiểm_tra_tên_camera_dài_'+source.id}));
                            S.liveStreamsSignature = null;
                            VIEWS.live.tick();
                        }""")
                        page.locator("#p-test0").evaluate('(panel) => panel.style.width = "390px"')
                        title = page.locator("#p-test0 .camera-heading>b")
                        assert title.evaluate(
                            '(el) => getComputedStyle(el).textOverflow !== "ellipsis"'
                        )
                        assert title.evaluate("(el) => el.scrollHeight <= el.clientHeight + 1")
                        assert page.locator("#p-test0 .pbar").evaluate(
                            "(el) => el.scrollWidth <= el.clientWidth + 1"
                        )
                        expect(page.locator("#p-test0 .demo-tools")).to_be_hidden()
                        expect(page.locator("#p-test0 .scan-progress")).to_be_hidden()
                        expect(page.locator("#p-test0 .source-location")).to_be_hidden()
                        page.screenshot(
                            path=str(output / "video-header-long-name.png"), full_page=True
                        )
                        page.locator("#p-test0").evaluate('(panel) => panel.style.width = ""')
                        page.locator("#p-test0 .camera-heading>b").click()
                        main_panel = page.locator("#p-test0")
                        expect(main_panel).to_have_class("panel focus-main")
                        expect(main_panel.locator(".demo-tools")).to_be_visible()
                        expect(main_panel.locator(".scan-progress")).to_be_visible()
                        focused_video = main_panel.locator(".tracking-stage").bounding_box()
                        assert focused_video["height"] > 350, focused_video
                        assert (
                            focused_video["y"] + focused_video["height"]
                            <= page.viewport_size["height"] + 2
                        )
                        assert main_panel.locator(".pbar").evaluate(
                            "(bar) => bar.scrollWidth <= bar.clientWidth + 2"
                        )
                        expect(main_panel.locator(".video-controls")).to_have_count(1)
                        expect(main_panel.locator(".fs-btn")).to_have_count(1)
                        assert not main_panel.locator("video").evaluate("(video) => video.controls")
                        main_panel.locator(".player-mute").click()
                        assert main_panel.locator("video").evaluate("(video) => video.muted")
                        main_panel.locator(".player-volume").evaluate(
                            '(el) => { el.value = .4; el.dispatchEvent(new Event("input",{bubbles:true})); }'
                        )
                        assert (
                            abs(
                                main_panel.locator("video").evaluate("(video) => video.volume")
                                - 0.4
                            )
                            < 0.01
                        )
                        main_panel.locator("video").evaluate(
                            '(video) => { Object.defineProperty(video,"duration",{value:90,configurable:true}); video.dispatchEvent(new Event("loadedmetadata")); }'
                        )
                        main_panel.locator(".player-seek").evaluate(
                            '(el) => { el.value = 30; el.dispatchEvent(new Event("input",{bubbles:true})); }'
                        )
                        assert (
                            main_panel.locator("video").evaluate("(video) => video.currentTime")
                            == 30
                        )
                        main_panel.locator(".fs-btn").click()
                        page.wait_for_function("!!document.fullscreenElement")
                        assert page.evaluate(
                            '!!document.fullscreenElement.querySelector("video") && !!document.fullscreenElement.querySelector(".tracking-overlay")'
                        )
                        page.evaluate("document.exitFullscreen()")
                        page.wait_for_function("!document.fullscreenElement")
                        expect(page.locator("#p-test1 .demo-tools")).to_be_hidden()
                        thumb = page.locator("#p-test1")
                        assert abs(thumb.bounding_box()["height"] - 160) <= 1
                        assert abs(thumb.locator(".pbar").bounding_box()["height"] - 30) <= 1
                        assert (
                            page.locator("#streams").evaluate("(el) => getComputedStyle(el).rowGap")
                            == "6px"
                        )
                        page.screenshot(path=str(output / "focus-two-videos.png"), full_page=True)
                        page.evaluate("""() => {
                            S.sources = window.focusTestSources;
                            S.refreshing = false;
                            S.focusedSource = null; S.liveStreamsSignature = null;
                            VIEWS.live.tick();
                        }""")
                        page.screenshot(path=str(output / "live-desktop.png"), full_page=True)
                        page.locator(".nav[data-view=verify]").click()
                        expect(page.locator(".verify-workspace")).to_be_visible()
                        expect(page.locator(".facts dt", has_text="Hung khí")).to_have_count(1)
                        expect(page.locator(".facts dt", has_text="Độ tin cậy")).to_have_count(1)
                        expect(
                            page.locator(".review-panel summary", has_text="Diễn biến cảnh báo")
                        ).to_have_count(0)
                        expect(
                            page.locator(".review-panel summary", has_text="Thao tác hàng loạt")
                        ).to_have_count(0)
                        assert abs(page.locator(".topbar").bounding_box()["height"] - 40) <= 1
                        expect(page.locator(".queue-item.sel")).to_have_count(1)
                        expect(
                            page.get_by_role("button", name="Xác nhận & gửi cảnh báo", exact=True)
                        ).to_be_visible()
                        assert page.locator(".page-heading p").count() == 0
                        overlay = page.locator(".alert-detections-canvas")
                        alpha_pixels = '(canvas) => canvas.getContext("2d").getImageData(0,0,canvas.width,canvas.height).data.some((v,i) => i % 4 === 3 && v > 0)'
                        assert overlay.evaluate(alpha_pixels), (
                            "Visible AI overlay should contain pixels"
                        )
                        page.locator("#show-detection-labels").uncheck()
                        assert not overlay.evaluate(alpha_pixels), (
                            "AI off must hide boxes and labels"
                        )
                        for evidence_canvas in page.locator(".evidence-detections-canvas").all():
                            assert not evidence_canvas.evaluate(alpha_pixels)
                        page.locator(".evidence-frame").first.click()
                        expect(page.locator("#alert-image")).to_have_attribute("alt", "Ảnh 1")
                        expect(page.locator("#alert-image-label")).to_have_count(0)
                        assert not overlay.evaluate(alpha_pixels)
                        page.get_by_role("button", name="Ảnh ban đầu", exact=True).click()
                        expect(page.locator("#alert-image")).to_have_attribute(
                            "alt", "Ảnh phát hiện ban đầu"
                        )
                        assert not overlay.evaluate(alpha_pixels)
                        page.locator("#show-detection-labels").check()
                        assert overlay.evaluate(alpha_pixels)
                        expect(page.locator("#note-1")).to_have_count(0)
                        page.locator(".nav[data-view=live]").click()
                        page.locator(".nav[data-view=verify]").click()
                        expect(
                            page.get_by_role("button", name="Lưu ghi chú", exact=True)
                        ).to_have_count(0)
                        page.screenshot(path=str(output / "verify-desktop.png"), full_page=True)
                        page.get_by_role(
                            "button", name="Xác nhận & gửi cảnh báo", exact=True
                        ).click()
                        expect(page.locator(".notification-result")).to_have_text("Test log only")
                        dispatch_mock.assert_called_once()
                        assert db.get_alert(1)["status"] == "confirmed"
                        page.get_by_role("button", name="Hoàn tất xử lý", exact=True).click()
                        expect(page.locator(".alert-queue .queue-item")).to_have_count(3)
                        page.get_by_role(
                            "button", name="Đánh dấu nhận diện sai", exact=True
                        ).click()
                        expect(page.locator("#dlg")).to_be_visible()
                        page.locator("#false-alarm-form select[name=reason]").select_option(
                            label="Sai loại vật thể"
                        )
                        page.locator("#false-alarm-form select[name=actual_label]").select_option(
                            "hammer"
                        )
                        page.locator("#false-alarm-form textarea").fill("UI test")
                        page.get_by_role("button", name="Lưu kết quả xác minh", exact=True).click()
                        expect(page.locator(".alert-queue .queue-item")).to_have_count(2)
                        assert "UI test" in db.get_alert(2)["events"][-1]["text"]
                        page.locator(".nav[data-view=history]").click()
                        expect(page.locator("#hf")).to_be_visible()
                        page.locator("#hf").select_option("completed")
                        expect(page.locator("#hbody tbody tr")).to_have_count(1)
                        expect(page.locator("#export-history-csv")).to_have_attribute(
                            "href", "/api/alerts/export?status=completed&format=csv"
                        )
                        page.locator("#hf").select_option("deleted")
                        expect(page.locator("#export-history-zip")).to_have_attribute(
                            "href", "/api/alerts/export?status=deleted&format=zip"
                        )
                        with page.expect_download() as export_download:
                            page.locator("#export-history-csv").click()
                        assert export_download.value.suggested_filename.endswith(".csv")
                        with page.expect_download() as export_images:
                            page.locator("#export-history-zip").click()
                        assert export_images.value.suggested_filename.endswith(".zip")
                        expect(page.locator("#export-history-excel")).to_have_attribute(
                            "href", "/api/alerts/export?status=deleted&format=xlsx"
                        )
                        with page.expect_download() as export_excel:
                            page.locator("#export-history-excel").click()
                        assert export_excel.value.suggested_filename.endswith(".xlsx")
                        page.locator(".nav[data-view=dashboard]").click()
                        expect(page.locator(".dashboard-metrics .metric-card")).to_have_count(4)
                        page.locator("#dashboard-period").select_option("30")
                        expect(page.locator(".trend-chart")).to_have_attribute(
                            "aria-label", "Cảnh báo theo ngày trong 30 ngày"
                        )
                        page.screenshot(path=str(output / "dashboard-desktop.png"), full_page=True)
                        page.locator("#dashboard-period").select_option("7")
                        expect(page.locator(".trend-chart")).to_have_attribute(
                            "aria-label", "Cảnh báo theo ngày trong 7 ngày"
                        )
                        for view in [
                            "dashboard",
                            "dev-camera",
                            "dev-drone",
                            "dev-robot",
                            "map",
                            "site",
                            "notify",
                            "settings",
                            "logs",
                        ]:
                            page.locator(f'.nav[data-view="{view}"]').click()
                            expect(page.locator(f"#view-{view}")).to_be_visible()
                        page.locator(".nav[data-view=verify]").click()
                        for width, height in [(1280, 800), (768, 1024), (390, 844)]:
                            page.set_viewport_size({"width": width, "height": height})
                            assert page.evaluate(
                                "document.documentElement.scrollWidth <= innerWidth"
                            ), f"Page overflow at {width}"
                            assert page.locator("#main").evaluate(
                                "(el) => el.scrollWidth <= el.clientWidth + 1"
                            ), f"Main overflow at {width}"
                            page.screenshot(
                                path=str(output / f"verify-{width}.png"), full_page=True
                            )
                        for view in [
                            "live",
                            "history",
                            "dashboard",
                            "dev-camera",
                            "dev-drone",
                            "dev-robot",
                            "map",
                            "site",
                            "notify",
                            "settings",
                            "logs",
                        ]:
                            page.locator(f'.nav[data-view="{view}"]').click()
                            expect(page.locator(f"#view-{view}")).to_be_visible()
                            assert page.locator("#main").evaluate(
                                "(el) => el.scrollWidth <= el.clientWidth + 1"
                            ), f"Mobile overflow in {view}"
                            if view == "dashboard":
                                page.screenshot(
                                    path=str(output / "dashboard-mobile.png"), full_page=True
                                )
                        page.set_viewport_size({"width": 1600, "height": 1000})
                        page.locator(".nav[data-view=settings]").click()
                        expect(page.locator("#settings-submenu [role=tab]")).to_have_count(5)
                        expect(page.locator("#settings-submenu")).to_be_visible()
                        page.locator(".nav[data-view=settings] .settings-expand").click()
                        expect(page.locator("#settings-submenu")).to_be_hidden()
                        page.locator(".nav[data-view=settings] .settings-expand").click()
                        expect(page.locator("#settings-submenu")).to_be_visible()
                        page.get_by_role("tab", name="Nhận diện hung khí", exact=True).click()
                        expect(
                            page.locator("#view-settings [role=tabpanel]:visible")
                        ).to_have_count(1)
                        expect(page.locator(".weapon-setting")).to_have_count(10)
                        knife_toggle = page.locator("input[name=knife_enabled]")
                        threshold = page.locator("input[name=knife_conf_threshold]")
                        knife_toggle.check()
                        threshold.fill("0.63")
                        page.locator("input[name=color_knife]").fill("#ff2244")
                        knife_toggle.uncheck()
                        expect(threshold).to_be_disabled()
                        page.get_by_role("tab", name="Hiệu năng xử lý", exact=True).click()
                        page.get_by_role("tab", name="Nhận diện hung khí", exact=True).click()
                        expect(threshold).to_have_value("0.63")
                        expect(knife_toggle).not_to_be_checked()
                        page.screenshot(path=str(output / "settings-weapons.png"), full_page=True)
                        page.locator("#sf-settings").get_by_role(
                            "button", name="Lưu thay đổi", exact=True
                        ).click()
                        page.wait_for_function(
                            "S.settings.knife_enabled === false && S.settings.knife_conf_threshold === 0.63"
                        )
                        page.wait_for_function('S.preferences.color_knife === "#ff2244"')
                        page.get_by_role("tab", name="Giao diện", exact=True).click()
                        page.locator("select[name=density]").select_option("compact")
                        page.locator("select[name=font_size]").select_option("large")
                        page.locator("select[name=camera_columns]").select_option("3")
                        page.locator("input[name=box_width]").fill("6")
                        page.locator("input[name=reduce_motion]").check()
                        page.locator("#sf-settings").get_by_role(
                            "button", name="Lưu thay đổi", exact=True
                        ).click()
                        page.wait_for_function(
                            'S.preferences.box_width === 6 && S.preferences.camera_columns === "3"'
                        )
                        expect(page.locator("body")).to_have_attribute("data-density", "compact")
                        expect(page.locator("body")).to_have_attribute("data-font-size", "large")
                        expect(page.locator("body")).to_have_attribute("data-reduce-motion", "true")
                        page.get_by_role(
                            "button", name="Khôi phục giao diện mặc định", exact=True
                        ).click()
                        page.wait_for_function(
                            'S.preferences.box_width === 4 && S.preferences.density === "standard"'
                        )
                        expect(page.locator("input[name=box_width]")).to_have_value("4")
                        expect(page.locator("input[name=color_knife]")).to_have_value("#22c55e")
                        assert db.get_settings()["knife_conf_threshold"] == 0.63
                        # Only this test database changes theme.
                        switch = page.locator("input[name=theme]")
                        switch.check()
                        expect(page.locator("html")).to_have_attribute("data-theme", "dark")
                        page.locator(".nav[data-view=verify]").click()
                        page.screenshot(path=str(output / "verify-theme.png"), full_page=True)
                        page.locator(".nav[data-view=dashboard]").click()
                        page.screenshot(path=str(output / "dashboard-dark.png"), full_page=True)
                        # Audit every main view across desktop, laptop, tablet and phone.
                        audit_views = [
                            "live",
                            "verify",
                            "history",
                            "dashboard",
                            "dev-camera",
                            "dev-drone",
                            "dev-robot",
                            "map",
                            "site",
                            "notify",
                            "settings",
                            "logs",
                        ]
                        for width, height in [(1600, 1000), (1280, 800), (768, 1024), (390, 844)]:
                            page.set_viewport_size({"width": width, "height": height})
                            for view in audit_views:
                                page.locator(f'.nav[data-view="{view}"]').click()
                                if view == "settings" and width <= 1100:
                                    page.get_by_role("tab", name="Giao diện", exact=True).click()
                                assert page.locator("#main").evaluate(
                                    "(el) => el.scrollWidth <= el.clientWidth + 1"
                                ), f"Audit overflow: {view}/{width}"
                                assert page.evaluate(
                                    "document.documentElement.scrollWidth <= innerWidth"
                                ), f"Viewport overflow: {view}/{width}"
                                if width == 390 and view != "settings":
                                    assert not page.evaluate(
                                        'document.body.classList.contains("mobile-nav-open")'
                                    ), f"Drawer masks {view}"
                                if view in [
                                    "dev-camera",
                                    "site",
                                    "notify",
                                    "settings",
                                    "history",
                                    "logs",
                                ]:
                                    page.screenshot(
                                        path=str(output / f"audit-{view}-{width}.png"),
                                        full_page=True,
                                    )
                        page.set_viewport_size({"width": 1600, "height": 1000})
                        page.locator(".nav[data-view=verify]").click()
                        page.get_by_role(
                            "button", name="Đánh dấu sai hàng loạt", exact=True
                        ).click()
                        expect(page.locator(".bulk-select")).to_have_count(2)
                        page.locator('.bulk-select[value="3"]').check()
                        page.get_by_role("button", name="Đánh dấu sai đã chọn", exact=True).click()
                        page.locator("#false-alarm-form select[name=reason]").select_option(
                            label="Sai loại vật thể"
                        )
                        page.get_by_role("button", name="Lưu kết quả xác minh", exact=True).click()
                        expect(page.locator(".alert-queue .queue-item")).to_have_count(1)
                        assert db.get_alert(3)["status"] == "deleted"
                        assert db.get_alert(4)["status"] == "pending"
                        page.get_by_role("button", name="Xóa hàng loạt", exact=True).click()
                        page.locator('.bulk-select[value="4"]').check()
                        page.once("dialog", lambda dialog: dialog.accept())
                        page.get_by_role("button", name="Xóa đã chọn", exact=True).click()
                        expect(page.locator(".alert-queue")).to_have_count(0)
                        assert db.get_alert(4) is None
                        assert db.get_alert(3) is not None
                        assert not errors, errors
                        browser.close()
                        print(f"Browser smoke checks passed; screenshots: {output}")
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
            finally:
                web.app.view_functions["video_feed"] = original_feed


if __name__ == "__main__":
    main()



from datetime import datetime

import requests

from weapon_detection import config
from weapon_detection.storage import db

LOG_FILE = config.BASE_DIR / "data" / "dispatch.log"


def build_message(a):
    s = db.get_settings()
    detail = ", ".join(f"{n} {k}" for k, n in a["summary"].items())
    lines = [
        "CẢNH BÁO HUNG KHÍ - ĐÃ XÁC NHẬN",
        f"Địa điểm: {s['site_name']} / {a['location'] or '-'}",
        f"Nguồn: {a['source_name']} ({a['source_type']})",
    ]
    if a.get("lat") is not None and a.get("lon") is not None:
        lines.append(f"Tọa độ: {a['lat']}, {a['lon']}")
    lines += [
        f"Thời gian: {a['created_at']}",
        f"Hung khí: {detail}",
        f"Mã cảnh báo: #{a['id']}",
    ]
    return "\n".join(lines)


def _telegram(text, chat_id, image_path=None):
    s = db.get_settings()
    base = f"https://api.telegram.org/bot{s['telegram_token']}"
    if image_path:
        with open(image_path, "rb") as f:
            r = requests.post(f"{base}/sendPhoto", data={"chat_id": chat_id, "caption": text[:1000]},
                              files={"photo": f}, timeout=20)
    else:
        r = requests.post(f"{base}/sendMessage", data={"chat_id": chat_id, "text": text}, timeout=20)
    r.raise_for_status()


def _telegram_error(error):
    response = error.response
    if response is not None:
        status = response.status_code
        if status == 404:
            return "Telegram trả về HTTP 404. Token bot có thể không hợp lệ; hãy thu hồi token đã lộ và nhập token mới từ BotFather."
        if status == 400:
            return "Telegram từ chối yêu cầu (HTTP 400). Hãy kiểm tra Chat ID và nội dung yêu cầu."
        return f"Telegram trả về lỗi HTTP {status}."
    if isinstance(error, requests.Timeout):
        return "Hết thời gian chờ khi kết nối Telegram."
    if isinstance(error, requests.ConnectionError):
        return "Không thể kết nối tới Telegram."
    return "Không thể gửi yêu cầu tới Telegram."


def send_dispatch(a):

    msg = build_message(a)
    path = config.ALERT_DIR / a["image"]
    print(f"\n===== DISPATCH =====\n{msg}\nẢnh: {path}\n====================\n")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}]\n{msg}\n\n")

    s = db.get_settings()
    if s["telegram_enabled"] and s["telegram_token"]:
        devices = [device for device in db.list_mobile_devices() if device["enabled"]]
        if not devices:
            return False, "Chưa có thiết bị di động nào được bật để nhận thông báo."
        delivered, failures = [], []
        for device in devices:
            try:
                _telegram(msg, device["chat_id"], path)
                delivered.append(device["name"])
            except requests.RequestException as e:
                failures.append(f"{device['name']}: {_telegram_error(e)}")
            except OSError:
                failures.append(f"{device['name']}: Không thể đọc ảnh cảnh báo.")
        if failures:
            summary = f"Đã gửi tới {len(delivered)}/{len(devices)} thiết bị."
            return False, f"{summary} " + " ".join(failures)
        return True, f"Đã gửi thông báo tới {len(delivered)} thiết bị di động."
    return True, "chỉ ghi log (Telegram đang tắt)"


def send_test(chat_id, device_name="thiết bị"):
    s = db.get_settings()
    if not s["telegram_token"]:
        return False, "Chưa nhập token bot."
    try:
        _telegram("SAFESIGHT: tin nhắn thử nghiệm", chat_id)
        return True, f"Đã gửi tin thử tới {device_name}."
    except requests.RequestException as e:
        return False, f"Lỗi: {_telegram_error(e)}"

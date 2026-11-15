"""Local staff accounts and signed login sessions."""

import secrets
import sqlite3
import time
from collections import defaultdict
from datetime import timedelta

from flask import abort, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from weapon_detection import config
from weapon_detection.storage import db


def install(app):
    key_path = config.BASE_DIR / "data" / "runtime" / "session.key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with key_path.open("x", encoding="ascii") as stream:
            stream.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    app.secret_key = key_path.read_text(encoding="ascii").strip()
    app.config.update(
        AUTH_REQUIRED=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    )
    attempts = defaultdict(list)

    def token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(24)
        return session["csrf"]

    def check_csrf():
        supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf", "")
        if not secrets.compare_digest(str(supplied), str(session.get("csrf", ""))) or not supplied:
            abort(400, "Invalid session token. Reload the page.")

    def users():
        with db._db() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT id,username,display_name,is_admin FROM users ORDER BY id"
                )
            ]

    @app.context_processor
    def auth_context():
        return dict(current_user=getattr(g, "user", None), csrf_token=token)

    @app.before_request
    def authenticate():
        g.user = None
        if not app.config["AUTH_REQUIRED"]:
            return
        user_id = session.get("user_id")
        if user_id:
            with db._db() as connection:
                row = connection.execute(
                    "SELECT id,username,display_name,is_admin FROM users WHERE id=?", (user_id,)
                ).fetchone()
            g.user = dict(row) if row else None
        if request.endpoint in ("static", "login"):
            return
        if not g.user:
            if request.path.startswith("/api/"):
                return jsonify(error="Vui lòng đăng nhập"), 401
            return redirect(url_for("login"))
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            check_csrf()

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect("/")
        first = not users()
        error = None
        if request.method == "POST":
            check_csrf()
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            now = time.monotonic()
            address = request.remote_addr or "local"
            attempts[address] = [stamp for stamp in attempts[address] if now - stamp < 300]
            if len(attempts[address]) >= 10:
                error = "Bạn đã thử nhiều lần. Vui lòng chờ 5 phút."
            elif first:
                try:
                    create_user(
                        username, password, request.form.get("display_name", ""), first=True
                    )
                    return redirect(url_for("login"))
                except (ValueError, sqlite3.IntegrityError) as exc:
                    error = str(exc)
            else:
                with db._db() as connection:
                    row = connection.execute(
                        "SELECT * FROM users WHERE username=?", (username,)
                    ).fetchone()
                if row and check_password_hash(row["password_hash"], password):
                    session.clear()
                    session["user_id"] = row["id"]
                    session.permanent = True
                    token()
                    attempts.pop(address, None)
                    db.log("INFO", "Nhân viên nhận ca", row["display_name"])
                    return redirect("/")
                attempts[address].append(now)
                error = "Tài khoản hoặc mật khẩu không đúng."
        return render_template("login.html", first=first, error=error)

    def create_user(username, password, display_name, first=False):
        display_name = display_name.strip()
        if not username or len(username) > 64 or not display_name or len(display_name) > 100:
            raise ValueError("Vui lòng nhập tài khoản và tên nhân viên hợp lệ.")
        if len(password) < 8 or len(password) > 256:
            raise ValueError("Mật khẩu cần từ 8 đến 256 ký tự.")
        hashed = generate_password_hash(password)
        with db._db() as connection:
            # Recheck in the same transaction so only the first account is an administrator.
            connection.execute("BEGIN IMMEDIATE")
            if first and connection.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise ValueError("Tài khoản quản trị đã được tạo. Vui lòng đăng nhập.")
            connection.execute(
                "INSERT INTO users(username,display_name,password_hash,is_admin) VALUES(?,?,?,?)",
                (username, display_name, hashed, int(first)),
            )

    @app.post("/logout")
    def logout():
        db.log("INFO", "Nhân viên kết thúc ca", g.user["display_name"])
        session.clear()
        return redirect(url_for("login"))

    @app.route("/accounts", methods=["GET", "POST"])
    def accounts():
        if not g.user or not g.user["is_admin"]:
            abort(403)
        error = None
        if request.method == "POST":
            try:
                create_user(
                    request.form.get("username", "").strip().lower(),
                    request.form.get("password", ""),
                    request.form.get("display_name", ""),
                )
                db.log("INFO", "Tạo tài khoản nhân viên", g.user["display_name"])
                return redirect(url_for("accounts"))
            except (ValueError, sqlite3.IntegrityError):
                error = "Không thể tạo tài khoản. Kiểm tra thông tin, mật khẩu tối thiểu 8 ký tự và tên tài khoản chưa trùng."
        return render_template("login.html", manage=True, staff=users(), error=error)

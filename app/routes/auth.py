from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.captcha import generate_captcha, verify_captcha
from app.models import User
from app.permissions import log_action

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        captcha_input = request.form.get("captcha", "").strip()
        if not verify_captcha(captcha_input):
            flash("验证码错误，请重新输入", "danger")
            return render_template("login.html", captcha_code=generate_captcha())

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.is_active and user.check_password(password):
            login_user(user)
            log_action("login", resource=user.username)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("main.dashboard"))
        flash("用户名或密码错误", "danger")
        return render_template("login.html", captcha_code=generate_captcha())

    return render_template("login.html", captcha_code=generate_captcha())


@bp.route("/login/captcha")
def refresh_captcha():
    return jsonify({"captcha": generate_captcha()})


@bp.route("/logout")
@login_required
def logout():
    log_action("logout", resource=current_user.username)
    logout_user()
    return redirect(url_for("auth.login"))

from flask import Blueprint, redirect, url_for
from flask_login import login_required

from app.permissions import role_required
from app.models import ROLE_ORG_ADMIN

bp = Blueprint("users", __name__)


@bp.route("/")
@login_required
@role_required(ROLE_ORG_ADMIN)
def list_users():
    return redirect(url_for("admin.users"))


@bp.route("/new")
@login_required
@role_required(ROLE_ORG_ADMIN)
def create():
    return redirect(url_for("admin.user_create"))


@bp.route("/<int:user_id>/edit")
@login_required
@role_required(ROLE_ORG_ADMIN)
def edit(user_id):
    return redirect(url_for("admin.user_edit", user_id=user_id))

from flask import Blueprint, redirect, url_for
from flask_login import login_required

from app.models import ROLE_ORG_ADMIN
from app.permissions import role_required

bp = Blueprint("orgs", __name__)


@bp.route("/")
@login_required
@role_required(ROLE_ORG_ADMIN)
def list_orgs():
    return redirect(url_for("admin.departments"))


@bp.route("/new")
@login_required
@role_required(ROLE_ORG_ADMIN)
def create():
    return redirect(url_for("admin.department_create"))

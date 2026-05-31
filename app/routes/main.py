from flask import Blueprint, render_template
from flask_login import login_required

from app.models import AuditLog, Organization, User
from app.permissions import visible_credentials

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/dashboard")
@login_required
def dashboard():
    creds = visible_credentials(current_user)[:10]
    return render_template(
        "dashboard.html",
        cred_count=len(visible_credentials(current_user)),
        user_count=User.query.count(),
        org_count=Organization.query.count(),
        recent_creds=creds,
        logs=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all(),
    )


from flask_login import current_user  # noqa: E402

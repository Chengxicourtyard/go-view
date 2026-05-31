from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.constants import SYSTEM_TYPES
from app.crypto import decrypt_secret, encrypt_secret
from app.extensions import db
from app.models import (
    ROLE_MANAGER,
    Credential,
    CredentialPermission,
    Organization,
    User,
    VIS_ORG,
    VIS_PRIVATE,
)
from app.permissions import (
    VISIBILITY_CHOICES,
    can_edit_credential,
    can_view_credential,
    log_action,
    visible_credentials,
)

bp = Blueprint("credentials", __name__)


@bp.route("/")
@login_required
def list_credentials():
    q = request.args.get("q", "").strip().lower()
    dept = request.args.get("dept", "").strip()
    creds = visible_credentials(current_user)
    if dept:
        creds = [c for c in creds if c.use_department == dept or c.department_display == dept]
    if q:
        creds = [
            c
            for c in creds
            if q in c.system_name.lower()
            or q in (c.account or "").lower()
            or q in (c.url or "").lower()
            or q in (c.use_department or "").lower()
            or q in (c.system_type or "").lower()
            or q in (c.notes or "").lower()
        ]
    departments = sorted({c.department_display for c in visible_credentials(current_user) if c.department_display != "-"})
    return render_template(
        "credentials/list.html",
        credentials=creds,
        q=q,
        dept=dept,
        departments=departments,
        system_types=SYSTEM_TYPES,
        manager_own_only=current_user.role_level == ROLE_MANAGER,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if not current_user.can_write_credentials():
        abort(403)
    orgs = _editable_orgs()
    if request.method == "POST":
        org_id = int(request.form["org_id"]) if request.form.get("org_id") else None
        use_department = _resolve_department(request.form, org_id)
        visibility = _resolve_visibility(request.form)
        if current_user.role_level == ROLE_MANAGER:
            org_id = current_user.org_id
            if not use_department and current_user.organization:
                use_department = current_user.organization.name
        cred = Credential(
            system_name=request.form["system_name"].strip(),
            account=request.form.get("account", "").strip(),
            password_encrypted=encrypt_secret(request.form.get("password", "")),
            url=request.form.get("url", "").strip(),
            use_department=use_department,
            system_type=request.form.get("system_type", "").strip(),
            notes=request.form.get("notes", "").strip(),
            visibility=visibility,
            org_id=org_id,
            owner_id=current_user.id,
            updated_at=datetime.utcnow(),
        )
        db.session.add(cred)
        db.session.commit()
        log_action("create_credential", resource=f"credential:{cred.id}", detail=cred.system_name)
        flash("系统账号记录已创建", "success")
        return redirect(url_for("credentials.list_credentials"))
    return render_template(
        "credentials/form.html",
        credential=None,
        orgs=orgs,
        visibility_choices=VISIBILITY_CHOICES,
        system_types=SYSTEM_TYPES,
        manager_own_only=current_user.role_level == ROLE_MANAGER,
    )


@bp.route("/<int:cred_id>")
@login_required
def detail(cred_id):
    cred = Credential.query.get_or_404(cred_id)
    if not can_view_credential(current_user, cred):
        abort(403)
    log_action("view_credential", resource=f"credential:{cred.id}", detail=cred.system_name)
    if request.args.get("reveal") and can_view_credential(current_user, cred):
        password = decrypt_secret(cred.password_encrypted)
    else:
        password = "********"
    grants = CredentialPermission.query.filter_by(credential_id=cred.id).all()
    users = User.query.filter(User.is_active.is_(True)).order_by(User.username).all()
    return render_template(
        "credentials/detail.html",
        credential=cred,
        password=password,
        can_edit=can_edit_credential(current_user, cred),
        grants=grants,
        users=users,
    )


@bp.route("/<int:cred_id>/edit", methods=["GET", "POST"])
@login_required
def edit(cred_id):
    cred = Credential.query.get_or_404(cred_id)
    if not can_edit_credential(current_user, cred):
        abort(403)
    orgs = _editable_orgs()
    if request.method == "POST":
        org_id = int(request.form["org_id"]) if request.form.get("org_id") else None
        cred.system_name = request.form["system_name"].strip()
        cred.account = request.form.get("account", "").strip()
        if request.form.get("password"):
            cred.password_encrypted = encrypt_secret(request.form["password"])
        cred.url = request.form.get("url", "").strip()
        cred.use_department = _resolve_department(request.form, org_id)
        cred.system_type = request.form.get("system_type", "").strip()
        cred.notes = request.form.get("notes", "").strip()
        cred.visibility = _resolve_visibility(request.form, cred)
        cred.org_id = org_id
        cred.updated_at = datetime.utcnow()
        db.session.commit()
        log_action("update_credential", resource=f"credential:{cred.id}", detail=cred.system_name)
        flash("系统账号记录已更新", "success")
        return redirect(url_for("credentials.detail", cred_id=cred.id))
    return render_template(
        "credentials/form.html",
        credential=cred,
        orgs=orgs,
        visibility_choices=VISIBILITY_CHOICES,
        system_types=SYSTEM_TYPES,
        manager_own_only=current_user.role_level == ROLE_MANAGER,
    )


@bp.route("/<int:cred_id>/delete", methods=["POST"])
@login_required
def delete(cred_id):
    cred = Credential.query.get_or_404(cred_id)
    if not can_edit_credential(current_user, cred):
        abort(403)
    name = cred.system_name
    db.session.delete(cred)
    db.session.commit()
    log_action("delete_credential", resource=f"credential:{cred_id}", detail=name)
    flash("记录已删除", "success")
    return redirect(url_for("credentials.list_credentials"))


@bp.route("/<int:cred_id>/grant", methods=["POST"])
@login_required
def grant(cred_id):
    cred = Credential.query.get_or_404(cred_id)
    if not can_edit_credential(current_user, cred):
        abort(403)
    user_id = int(request.form["user_id"])
    can_edit = request.form.get("can_edit") == "on"
    existing = CredentialPermission.query.filter_by(
        credential_id=cred.id, user_id=user_id
    ).first()
    if existing:
        existing.can_edit = can_edit
    else:
        db.session.add(
            CredentialPermission(credential_id=cred.id, user_id=user_id, can_edit=can_edit)
        )
    db.session.commit()
    log_action("grant_credential", resource=f"credential:{cred.id}", detail=f"user:{user_id}")
    flash("授权已更新", "success")
    return redirect(url_for("credentials.detail", cred_id=cred.id))


@bp.route("/<int:cred_id>/revoke/<int:user_id>", methods=["POST"])
@login_required
def revoke(cred_id, user_id):
    cred = Credential.query.get_or_404(cred_id)
    if not can_edit_credential(current_user, cred):
        abort(403)
    grant = CredentialPermission.query.filter_by(
        credential_id=cred.id, user_id=user_id
    ).first()
    if grant:
        db.session.delete(grant)
        db.session.commit()
        log_action("revoke_credential", resource=f"credential:{cred.id}", detail=f"user:{user_id}")
    flash("已撤销授权", "success")
    return redirect(url_for("credentials.detail", cred_id=cred.id))


def _editable_orgs():
    if current_user.is_superadmin():
        return Organization.query.order_by(Organization.name).all()
    if current_user.org_id:
        org = Organization.query.get(current_user.org_id)
        if current_user.role_level == ROLE_MANAGER:
            return [org] if org else []
        ids = org.subtree_ids() if org else []
        return Organization.query.filter(Organization.id.in_(ids)).order_by(Organization.name).all()
    return []


def _resolve_department(form, org_id):
    use_department = form.get("use_department", "").strip()
    if use_department:
        return use_department
    if org_id:
        org = Organization.query.get(org_id)
        if org:
            return org.name
    return ""


def _resolve_visibility(form, credential=None):
    if current_user.role_level == ROLE_MANAGER:
        return VIS_PRIVATE
    return form.get("visibility", VIS_ORG)


from flask_login import current_user  # noqa: E402

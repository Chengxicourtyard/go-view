from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.admin_service import (
    admin_stats,
    assignable_roles,
    build_org_tree,
    can_delete_org,
    can_delete_user,
    can_manage_user,
    list_manageable_users,
    manageable_orgs,
    org_credential_count,
    org_user_count,
    user_owned_credential_count,
)
from app.extensions import db
from app.models import ROLE_ORG_ADMIN, AuditLog, CredentialPermission, Organization, User
from app.permissions import log_action, role_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@login_required
@role_required(ROLE_ORG_ADMIN)
def index():
    stats = admin_stats(current_user)
    return render_template("admin/index.html", stats=stats)


@bp.route("/users")
@login_required
@role_required(ROLE_ORG_ADMIN)
def users():
    role = request.args.get("role")
    org_id = request.args.get("org_id", type=int)
    q = request.args.get("q", "").strip().lower()
    role_filter = int(role) if role not in (None, "") else None

    user_list = list_manageable_users(current_user, role=role_filter, org_id=org_id)
    if q:
        user_list = [
            u for u in user_list
            if q in u.username.lower() or q in u.email.lower()
        ]
    orgs = manageable_orgs(current_user)
    user_items = [
        {
            "user": u,
            "can_delete": can_delete_user(current_user, u)[0],
        }
        for u in user_list
    ]
    return render_template(
        "admin/users/list.html",
        users=user_list,
        user_items=user_items,
        orgs=orgs,
        role_choices=assignable_roles(current_user),
        q=q,
        role_filter=role_filter,
        org_filter=org_id,
    )


@bp.route("/users/new", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ORG_ADMIN)
def user_create():
    orgs = manageable_orgs(current_user)
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip()
        if User.query.filter_by(username=username).first():
            flash("用户名已存在", "danger")
        elif User.query.filter_by(email=email).first():
            flash("邮箱已被使用", "danger")
        else:
            org_id = int(request.form["org_id"]) if request.form.get("org_id") else None
            if org_id and not current_user.manages_org(org_id) and not current_user.is_superadmin():
                abort(403)
            role_level = int(request.form["role_level"])
            if role_level < current_user.role_level and not current_user.is_superadmin():
                flash("不能创建比自己权限更高的用户", "danger")
            else:
                user = User(
                    username=username,
                    email=email,
                    role_level=role_level,
                    org_id=org_id,
                )
                user.set_password(request.form["password"])
                db.session.add(user)
                db.session.commit()
                log_action("create_user", resource=f"user:{user.id}", detail=username)
                flash("用户已创建", "success")
                return redirect(url_for("admin.users"))
    return render_template(
        "admin/users/form.html",
        user=None,
        orgs=orgs,
        role_choices=assignable_roles(current_user),
    )


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ORG_ADMIN)
def user_edit(user_id):
    user = User.query.get_or_404(user_id)
    if not can_manage_user(current_user, user):
        abort(403)
    orgs = manageable_orgs(current_user)
    if request.method == "POST":
        email = request.form["email"].strip()
        if User.query.filter(User.email == email, User.id != user.id).first():
            flash("邮箱已被其他用户使用", "danger")
        else:
            org_id = int(request.form["org_id"]) if request.form.get("org_id") else None
            if org_id and not current_user.manages_org(org_id) and not current_user.is_superadmin():
                abort(403)
            role_level = int(request.form["role_level"])
            if role_level < current_user.role_level and not current_user.is_superadmin():
                flash("不能分配比自己更高的权限", "danger")
            else:
                user.email = email
                user.org_id = org_id
                user.role_level = role_level
                user.is_active = request.form.get("is_active") == "on"
                if request.form.get("password"):
                    user.set_password(request.form["password"])
                db.session.commit()
                log_action("update_user", resource=f"user:{user.id}", detail=user.username)
                flash("用户已更新", "success")
                return redirect(url_for("admin.users"))
    can_delete, delete_reason = can_delete_user(current_user, user)
    return render_template(
        "admin/users/form.html",
        user=user,
        orgs=orgs,
        role_choices=assignable_roles(current_user),
        can_delete=can_delete,
        delete_reason=delete_reason,
        cred_count=user_owned_credential_count(user.id),
    )


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@role_required(ROLE_ORG_ADMIN)
def user_delete(user_id):
    user = User.query.get_or_404(user_id)
    ok, msg = can_delete_user(current_user, user)
    if not ok:
        flash(msg, "danger")
        return redirect(url_for("admin.user_edit", user_id=user_id))
    username = user.username
    CredentialPermission.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    log_action("delete_user", resource=f"user:{user_id}", detail=username)
    flash(f"用户「{username}」已删除", "success")
    return redirect(url_for("admin.users"))


@bp.route("/departments")
@login_required
@role_required(ROLE_ORG_ADMIN)
def departments():
    orgs = manageable_orgs(current_user)
    tree = build_org_tree(orgs)
    org_details = [
        {
            "org": o,
            "user_count": org_user_count(o.id),
            "cred_count": org_credential_count(o.id),
            "child_count": len(o.children),
        }
        for o in orgs
    ]
    return render_template("admin/departments/list.html", tree=tree, org_details=org_details)


@bp.route("/departments/new", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ORG_ADMIN)
def department_create():
    parents = manageable_orgs(current_user)
    if request.method == "POST":
        parent_id = int(request.form["parent_id"]) if request.form.get("parent_id") else None
        if parent_id and not current_user.manages_org(parent_id) and not current_user.is_superadmin():
            flash("无权在该部门下创建子部门", "danger")
        else:
            org = Organization(name=request.form["name"].strip(), parent_id=parent_id)
            db.session.add(org)
            db.session.commit()
            log_action("create_org", resource=f"org:{org.id}", detail=org.name)
            flash("部门已创建", "success")
            return redirect(url_for("admin.departments"))
    return render_template("admin/departments/form.html", org=None, parents=parents)


@bp.route("/departments/<int:org_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ORG_ADMIN)
def department_edit(org_id):
    org = Organization.query.get_or_404(org_id)
    if not current_user.manages_org(org_id) and not current_user.is_superadmin():
        abort(403)
    parents = [o for o in manageable_orgs(current_user) if o.id != org_id]
    if request.method == "POST":
        parent_id = int(request.form["parent_id"]) if request.form.get("parent_id") else None
        if parent_id == org_id:
            flash("上级部门不能是自己", "danger")
        elif parent_id and not current_user.manages_org(parent_id) and not current_user.is_superadmin():
            abort(403)
        else:
            org.name = request.form["name"].strip()
            org.parent_id = parent_id
            db.session.commit()
            log_action("update_org", resource=f"org:{org.id}", detail=org.name)
            flash("部门已更新", "success")
            return redirect(url_for("admin.departments"))
    return render_template("admin/departments/form.html", org=org, parents=parents)


@bp.route("/departments/<int:org_id>/delete", methods=["POST"])
@login_required
@role_required(ROLE_ORG_ADMIN)
def department_delete(org_id):
    org = Organization.query.get_or_404(org_id)
    if not current_user.manages_org(org_id) and not current_user.is_superadmin():
        abort(403)
    ok, msg = can_delete_org(org)
    if not ok:
        flash(msg, "danger")
    else:
        name = org.name
        db.session.delete(org)
        db.session.commit()
        log_action("delete_org", resource=f"org:{org_id}", detail=name)
        flash("部门已删除", "success")
    return redirect(url_for("admin.departments"))


@bp.route("/roles")
@login_required
@role_required(ROLE_ORG_ADMIN)
def roles():
    from app.models import ROLE_LABELS, ROLE_MANAGER, ROLE_ORG_ADMIN, ROLE_READONLY, ROLE_SUPERADMIN, ROLE_USER

    matrix = [
        ("系统管理员", "全校范围，管理所有用户、部门与系统账号"),
        ("院系管理员", "管理本院系及下级部门的用户与账号，可查看部门内共享记录"),
        ("科室负责人", "可新增系统账号记录，仅可查看与编辑本人添加的记录"),
        ("普通教职工", "查看授权范围内的系统账号"),
        ("只读用户", "仅查看，不可修改"),
    ]
    levels = [
        (ROLE_SUPERADMIN, ROLE_LABELS[ROLE_SUPERADMIN]),
        (ROLE_ORG_ADMIN, ROLE_LABELS[ROLE_ORG_ADMIN]),
        (ROLE_MANAGER, ROLE_LABELS[ROLE_MANAGER]),
        (ROLE_USER, ROLE_LABELS[ROLE_USER]),
        (ROLE_READONLY, ROLE_LABELS[ROLE_READONLY]),
    ]
    return render_template("admin/roles.html", matrix=matrix, levels=levels)


@bp.route("/audit-logs")
@login_required
@role_required(ROLE_ORG_ADMIN)
def audit_logs():
    page = request.args.get("page", 1, type=int)
    pagination = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template("admin/audit_logs.html", pagination=pagination, logs=pagination.items)

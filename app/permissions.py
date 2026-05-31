from functools import wraps

from flask import abort, redirect, url_for
from flask_login import current_user

from app.models import (
    ROLE_MANAGER,
    ROLE_ORG_ADMIN,
    ROLE_READONLY,
    ROLE_SUPERADMIN,
    ROLE_USER,
    ROLE_LABELS,
    Credential,
    CredentialPermission,
    Organization,
    VIS_ORG,
    VIS_PRIVATE,
    VIS_SUBTREE,
)


def role_required(max_level: int):
    """max_level 为允许访问的最高角色等级（数字越小权限越高）。"""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role_level > max_level:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def log_action(action: str, resource: str = "", detail: str = "") -> None:
    from app.extensions import db
    from app.models import AuditLog

    actor_id = None
    actor_username = ""
    if current_user.is_authenticated:
        actor_id = current_user.id
        actor_username = current_user.username

    entry = AuditLog(
        user_id=actor_id,
        username=actor_username,
        action=action,
        resource=resource,
        detail=detail,
    )
    db.session.add(entry)
    db.session.commit()


def can_view_credential(user, cred: Credential) -> bool:
    if user.is_superadmin():
        return True
    if cred.owner_id == user.id:
        return True
    grant = CredentialPermission.query.filter_by(
        credential_id=cred.id, user_id=user.id
    ).first()
    if grant:
        return True

    # 科室负责人仅可见本人创建的记录（及被单独授权的记录，见上）
    if user.role_level == ROLE_MANAGER:
        return False

    if cred.visibility == VIS_PRIVATE:
        return False

    if not user.org_id or not cred.org_id:
        return False

    user_org = Organization.query.get(user.org_id)
    if not user_org:
        return False

    if cred.visibility == VIS_ORG:
        if user.org_id != cred.org_id:
            return False
        return user.role_level <= ROLE_READONLY

    if cred.visibility == VIS_SUBTREE:
        subtree = user_org.subtree_ids()
        if cred.org_id not in subtree:
            return False
        if user.org_id == cred.org_id:
            return user.role_level <= ROLE_READONLY
        return user.role_level <= ROLE_ORG_ADMIN

    return False


def can_edit_credential(user, cred: Credential) -> bool:
    if user.is_superadmin():
        return True
    if cred.owner_id == user.id:
        return True
    grant = CredentialPermission.query.filter_by(
        credential_id=cred.id, user_id=user.id
    ).first()
    if grant and grant.can_edit:
        return True
    if user.role_level == ROLE_MANAGER:
        return False
    if not user.can_write_credentials():
        return False
    if cred.org_id and user.manages_org(cred.org_id):
        return True
    if user.org_id == cred.org_id and user.role_level <= ROLE_ORG_ADMIN:
        return True
    return False


def visible_credentials(user):
    return [c for c in Credential.query.order_by(Credential.updated_at.desc()).all() if can_view_credential(user, c)]


ROLE_CHOICES = [
    (ROLE_SUPERADMIN, ROLE_LABELS[ROLE_SUPERADMIN]),
    (ROLE_ORG_ADMIN, ROLE_LABELS[ROLE_ORG_ADMIN]),
    (ROLE_MANAGER, ROLE_LABELS[ROLE_MANAGER]),
    (ROLE_USER, ROLE_LABELS[ROLE_USER]),
    (ROLE_READONLY, ROLE_LABELS[ROLE_READONLY]),
]

VISIBILITY_CHOICES = [
    (VIS_PRIVATE, "私有（仅本人与授权）"),
    (VIS_ORG, "组织内可见"),
    (VIS_SUBTREE, "组织及下级可见"),
]

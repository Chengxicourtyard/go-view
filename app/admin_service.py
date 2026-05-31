from typing import List, Optional, Tuple

from app.models import (
    ROLE_LABELS,
    ROLE_ORG_ADMIN,
    ROLE_SUPERADMIN,
    AuditLog,
    Credential,
    CredentialPermission,
    Organization,
    User,
)

ROLE_CHOICES = [(level, ROLE_LABELS[level]) for level in sorted(ROLE_LABELS.keys())]


def manageable_orgs(user: User) -> List[Organization]:
    if user.is_superadmin():
        return Organization.query.order_by(Organization.name).all()
    if user.org_id:
        org = Organization.query.get(user.org_id)
        ids = org.subtree_ids() if org else []
        return Organization.query.filter(Organization.id.in_(ids)).order_by(Organization.name).all()
    return []


def assignable_roles(user: User) -> List[Tuple[int, str]]:
    if user.is_superadmin():
        return ROLE_CHOICES
    return [(level, label) for level, label in ROLE_CHOICES if level >= user.role_level]


def can_manage_user(actor: User, target: User) -> bool:
    if actor.is_superadmin():
        return True
    if target.id == actor.id:
        return False
    if target.role_level < actor.role_level:
        return False
    if not target.org_id or not actor.org_id:
        return False
    return actor.manages_org(target.org_id)


def can_delete_user(actor: User, target: User) -> Tuple[bool, str]:
    if target.id == actor.id:
        return False, "不能删除当前登录账号"
    if not can_manage_user(actor, target):
        return False, "无权删除该用户"
    if Credential.query.filter_by(owner_id=target.id).count():
        return False, "该用户名下还有系统账号记录，请先转移或删除后再删用户"
    if target.is_superadmin():
        active_admins = User.query.filter_by(role_level=ROLE_SUPERADMIN, is_active=True).count()
        if active_admins <= 1:
            return False, "不能删除唯一的系统管理员"
    return True, ""


def user_owned_credential_count(user_id: int) -> int:
    return Credential.query.filter_by(owner_id=user_id).count()


def list_manageable_users(actor: User, role: Optional[int] = None, org_id: Optional[int] = None, active_only: bool = False):
    if actor.is_superadmin():
        query = User.query
    elif actor.org_id:
        org = Organization.query.get(actor.org_id)
        ids = org.subtree_ids() if org else []
        query = User.query.filter(User.org_id.in_(ids))
    else:
        query = User.query.filter(False)

    if role is not None:
        query = query.filter(User.role_level == role)
    if org_id:
        query = query.filter(User.org_id == org_id)
    if active_only:
        query = query.filter(User.is_active.is_(True))
    return query.order_by(User.role_level, User.username).all()


def build_org_tree(orgs: List[Organization]):
    by_parent = {}
    for org in orgs:
        by_parent.setdefault(org.parent_id, []).append(org)

    def walk(parent_id=None, depth=0):
        nodes = []
        for org in sorted(by_parent.get(parent_id, []), key=lambda o: o.name):
            nodes.append({"org": org, "depth": depth})
            nodes.extend(walk(org.id, depth + 1))
        return nodes

    return walk()


def org_user_count(org_id: int) -> int:
    return User.query.filter_by(org_id=org_id).count()


def org_credential_count(org_id: int) -> int:
    return Credential.query.filter_by(org_id=org_id).count()


def can_delete_org(org: Organization) -> Tuple[bool, str]:
    if org.children:
        return False, "该部门下还有子部门，请先删除或移走子部门"
    if org_user_count(org.id):
        return False, "该部门下还有用户，请先调整用户所属部门"
    if org_credential_count(org.id):
        return False, "该部门下还有系统账号记录，请先转移或删除"
    return True, ""


def admin_stats(actor: User) -> dict:
    users = list_manageable_users(actor)
    orgs = manageable_orgs(actor)
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(8).all()
    return {
        "user_count": len(users),
        "active_user_count": sum(1 for u in users if u.is_active),
        "org_count": len(orgs),
        "cred_count": Credential.query.count() if actor.is_superadmin() else sum(org_credential_count(o.id) for o in orgs),
        "role_distribution": _role_distribution(users),
        "recent_logs": logs,
    }


def _role_distribution(users: List[User]) -> List[Tuple[str, int]]:
    counts = {}
    for u in users:
        counts[u.role_name] = counts.get(u.role_name, 0) + 1
    return sorted(counts.items(), key=lambda x: x[0])

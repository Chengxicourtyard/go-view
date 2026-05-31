from datetime import datetime
from typing import List, Optional

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

# 角色等级：数字越小权限越高
ROLE_SUPERADMIN = 0
ROLE_ORG_ADMIN = 1
ROLE_MANAGER = 2
ROLE_USER = 3
ROLE_READONLY = 4

ROLE_LABELS = {
    ROLE_SUPERADMIN: "系统管理员",
    ROLE_ORG_ADMIN: "院系管理员",
    ROLE_MANAGER: "科室负责人",
    ROLE_USER: "普通教职工",
    ROLE_READONLY: "只读用户",
}

# 可见范围
VIS_PRIVATE = "private"          # 仅创建者与授权用户
VIS_ORG = "org"                  # 本组织内按角色可见
VIS_SUBTREE = "subtree"          # 本组织及下级组织


class Organization(db.Model):
    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    parent = db.relationship("Organization", remote_side=[id], backref="children")
    users = db.relationship("User", backref="organization", lazy=True)
    credentials = db.relationship("Credential", backref="organization", lazy=True)

    def subtree_ids(self) -> List[int]:
        ids = [self.id]
        for child in self.children:
            ids.extend(child.subtree_ids())
        return ids

    @staticmethod
    def ancestors(org_id: Optional[int]) -> List[int]:
        if not org_id:
            return []
        org = Organization.query.get(org_id)
        if not org:
            return []
        chain = [org.id]
        current = org
        while current.parent_id:
            chain.append(current.parent_id)
            current = Organization.query.get(current.parent_id)
            if not current:
                break
        return chain


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role_level = db.Column(db.Integer, default=ROLE_USER, nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owned_credentials = db.relationship(
        "Credential", backref="owner", lazy=True, foreign_keys="Credential.owner_id"
    )
    permissions = db.relationship("CredentialPermission", backref="user", lazy=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def role_name(self) -> str:
        return ROLE_LABELS.get(self.role_level, "未知")

    def is_superadmin(self) -> bool:
        return self.role_level == ROLE_SUPERADMIN

    def can_manage_users(self) -> bool:
        return self.role_level <= ROLE_ORG_ADMIN

    def can_manage_orgs(self) -> bool:
        return self.role_level <= ROLE_ORG_ADMIN

    def can_write_credentials(self) -> bool:
        return self.role_level <= ROLE_MANAGER

    def is_department_manager(self) -> bool:
        return self.role_level == ROLE_MANAGER

    def manages_org(self, org_id: Optional[int]) -> bool:
        if self.is_superadmin():
            return True
        if not org_id or not self.org_id:
            return False
        if self.role_level > ROLE_ORG_ADMIN:
            return False
        return org_id in Organization.query.get(self.org_id).subtree_ids()


class Credential(db.Model):
    __tablename__ = "credentials"

    id = db.Column(db.Integer, primary_key=True)
    system_name = db.Column(db.String(200), nullable=False)  # 系统名称
    account = db.Column(db.String(200), default="")  # 账户
    password_encrypted = db.Column(db.Text, default="")  # 密码（加密存储）
    url = db.Column(db.String(500), default="")  # 网址
    use_department = db.Column(db.String(120), default="")  # 使用部门
    system_type = db.Column(db.String(80), default="")  # 系统类型
    notes = db.Column(db.Text, default="")  # 备注
    visibility = db.Column(db.String(20), default=VIS_ORG)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    grants = db.relationship(
        "CredentialPermission", backref="credential", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def department_display(self) -> str:
        if self.use_department:
            return self.use_department
        if self.organization:
            return self.organization.name
        return "-"


class CredentialPermission(db.Model):
    __tablename__ = "credential_permissions"

    id = db.Column(db.Integer, primary_key=True)
    credential_id = db.Column(db.Integer, db.ForeignKey("credentials.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    can_edit = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("credential_id", "user_id"),)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    username = db.Column(db.String(80), default="")  # 操作时的实际登录用户名
    action = db.Column(db.String(80), nullable=False)
    resource = db.Column(db.String(200), default="")
    detail = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="audit_logs")

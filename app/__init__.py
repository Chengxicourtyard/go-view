from flask import Flask
from flask_login import LoginManager

from app.extensions import db
from app.migrate import migrate_schema
from config import Config


login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "请先登录"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.routes.admin import bp as admin_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.main import bp as main_bp
    from app.routes.credentials import bp as cred_bp
    from app.routes.users import bp as users_bp
    from app.routes.orgs import bp as orgs_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(cred_bp, url_prefix="/credentials")
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(orgs_bp, url_prefix="/organizations")

    with app.app_context():
        db.create_all()
        migrate_schema()
        _seed_defaults()
        _ensure_it_manager()

    @app.context_processor
    def inject_globals():
        from app.models import ROLE_LABELS

        return {"ROLE_LABELS": ROLE_LABELS, "SITE_NAME": "高校信息系统账号管理平台"}

    return app


def _seed_defaults():
    from app.crypto import encrypt_secret
    from app.models import (
        ROLE_MANAGER,
        ROLE_SUPERADMIN,
        ROLE_USER,
        Credential,
        Organization,
        User,
        VIS_ORG,
    )

    if User.query.first():
        return

    root = Organization(name="某某大学")
    db.session.add(root)
    db.session.flush()

    dept_xx = Organization(name="信息中心", parent_id=root.id)
    dept_jwc = Organization(name="教务处", parent_id=root.id)
    dept_xgc = Organization(name="学生工作处", parent_id=root.id)
    dept_cwc = Organization(name="财务处", parent_id=root.id)
    dept_jsj = Organization(name="计算机学院", parent_id=root.id)
    dept_tsg = Organization(name="图书馆", parent_id=root.id)
    db.session.add_all([dept_xx, dept_jwc, dept_xgc, dept_cwc, dept_jsj, dept_tsg])
    db.session.flush()

    admin = User(
        username="admin",
        email="admin@university.edu.cn",
        role_level=ROLE_SUPERADMIN,
        org_id=dept_xx.id,
    )
    admin.set_password("admin123")

    jwc_manager = User(
        username="jwc_manager",
        email="jwc@university.edu.cn",
        role_level=ROLE_MANAGER,
        org_id=dept_jwc.id,
    )
    jwc_manager.set_password("manager123")

    it_manager = User(
        username="it_manager",
        email="it@university.edu.cn",
        role_level=ROLE_MANAGER,
        org_id=dept_xx.id,
    )
    it_manager.set_password("manager123")

    staff = User(
        username="staff",
        email="staff@university.edu.cn",
        role_level=ROLE_USER,
        org_id=dept_xx.id,
    )
    staff.set_password("staff123")

    db.session.add_all([admin, jwc_manager, it_manager, staff])
    db.session.flush()

    samples = [
        Credential(
            system_name="教务管理系统",
            account="jwc_admin",
            password_encrypted=encrypt_secret("Jw2024@Admin"),
            url="https://jw.university.edu.cn",
            use_department="教务处",
            system_type="教务管理系统",
            notes="教务处统一管理账号，每学期初需更新密码",
            visibility=VIS_ORG,
            org_id=dept_jwc.id,
            owner_id=admin.id,
        ),
        Credential(
            system_name="校园 VPN",
            account="vpn_xxzx",
            password_encrypted=encrypt_secret("Vpn#Secure99"),
            url="https://vpn.university.edu.cn",
            use_department="信息中心",
            system_type="VPN 远程接入",
            notes="供教职工远程访问内网资源",
            visibility=VIS_ORG,
            org_id=dept_xx.id,
            owner_id=admin.id,
        ),
        Credential(
            system_name="财务综合平台",
            account="cwc_ops",
            password_encrypted=encrypt_secret("Cw$Finance88"),
            url="https://cw.university.edu.cn",
            use_department="财务处",
            system_type="财务管理系统",
            notes="预算与报销相关，限财务处及授权人员使用",
            visibility=VIS_ORG,
            org_id=dept_cwc.id,
            owner_id=admin.id,
        ),
    ]
    db.session.add_all(samples)
    db.session.commit()


def _ensure_it_manager():
    """确保 it_manager 存在且为科室负责人，可新增系统账号记录。"""
    from app.models import ROLE_MANAGER, Organization, User

    org = Organization.query.filter_by(name="信息中心").first()
    if not org:
        org = Organization.query.filter_by(name="信息技术部").first()
    if not org:
        org = Organization.query.filter(Organization.name.contains("信息")).first()

    user = User.query.filter_by(username="it_manager").first()
    if not user:
        user = User(
            username="it_manager",
            email="it@university.edu.cn",
            role_level=ROLE_MANAGER,
            org_id=org.id if org else None,
            is_active=True,
        )
        db.session.add(user)
    else:
        user.role_level = ROLE_MANAGER
        user.is_active = True
        if org:
            user.org_id = org.id
        if not user.email:
            user.email = "it@university.edu.cn"
    user.set_password("manager123")
    db.session.commit()

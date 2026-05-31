from sqlalchemy import inspect, text

from app.extensions import db


def _backfill_audit_usernames() -> None:
    from app.models import AuditLog, User

    if "audit_logs" not in inspect(db.engine).get_table_names():
        return

    audit_cols = {c["name"] for c in inspect(db.engine).get_columns("audit_logs")}
    if "username" not in audit_cols:
        return

    updated = False
    for log in AuditLog.query.filter(
        (AuditLog.username == "") | (AuditLog.username.is_(None))
    ).all():
        if log.user_id:
            user = User.query.get(log.user_id)
            if user:
                log.username = user.username
                updated = True
    if updated:
        db.session.commit()


def migrate_schema() -> None:
    """兼容旧版数据库字段，平滑升级至高校版结构。"""
    insp = inspect(db.engine)
    if "credentials" not in insp.get_table_names():
        return

    cols = {c["name"] for c in insp.get_columns("credentials")}
    statements = []

    if "title" in cols and "system_name" not in cols:
        statements.append("ALTER TABLE credentials RENAME COLUMN title TO system_name")
    if "account_username" in cols and "account" not in cols:
        statements.append("ALTER TABLE credentials RENAME COLUMN account_username TO account")
    if "use_department" not in cols:
        statements.append(
            "ALTER TABLE credentials ADD COLUMN use_department VARCHAR(120) DEFAULT ''"
        )
    if "system_type" not in cols:
        statements.append(
            "ALTER TABLE credentials ADD COLUMN system_type VARCHAR(80) DEFAULT ''"
        )

    if "audit_logs" in insp.get_table_names():
        audit_cols = {c["name"] for c in insp.get_columns("audit_logs")}
        if "username" not in audit_cols:
            statements.append(
                "ALTER TABLE audit_logs ADD COLUMN username VARCHAR(80) DEFAULT ''"
            )

    if not statements:
        _backfill_audit_usernames()
        return

    with db.engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))

    _backfill_audit_usernames()

    # 旧数据：若使用部门为空，尝试从组织名称回填
    if "use_department" in {c["name"] for c in insp.get_columns("credentials")} or statements:
        from app.models import Credential, Organization

        for cred in Credential.query.filter(
            (Credential.use_department == "") | (Credential.use_department.is_(None))
        ).all():
            if cred.org_id:
                org = Organization.query.get(cred.org_id)
                if org:
                    cred.use_department = org.name
        db.session.commit()

# VaultPlatform — 分级多用户密码管理平台

Python + Flask 实现的团队密码管理系统，支持组织架构、角色分级、凭据加密与细粒度授权。

## 功能

- **5 级角色**：超级管理员 → 组织管理员 → 部门经理 → 普通用户 → 只读用户
- **树形组织**：支持多级部门，凭据可按组织 / 组织及下级可见
- **凭据管理**：账号、密码、URL、标签、备注
- **加密存储**：密码使用 Fernet（AES）加密后入库
- **细粒度授权**：可对单个用户授予查看/编辑权限
- **审计日志**：记录登录、查看、创建、修改等操作

## 快速开始

```bash
cd ~/Documents/vault-platform
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

浏览器访问：http://127.0.0.1:5001

> **注意**：macOS 默认会占用 5000 端口（AirPlay），本项目使用 **5001** 端口。

## 演示账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 超级管理员 |
| it_manager | manager123 | 科室负责人（信息中心），可添加记录 |
| jwc_manager | manager123 | 教务处负责人 |
| staff | staff123 | 普通用户（信息技术部） |

## 环境变量（生产环境务必修改）

```bash
export SECRET_KEY="随机长字符串"
export ENCRYPTION_KEY="另一随机长字符串"
export DATABASE_URL="sqlite:///vault.db"   # 或 postgresql://...
```

## 权限说明

| 可见范围 | 说明 |
|----------|------|
| private | 仅创建者与显式授权用户 |
| org | 同组织内按角色可见 |
| subtree | 本组织及所有下级组织可见（经理及以上可看跨下级） |

## 项目结构

```
vault-platform/
├── app/
│   ├── models.py        # 用户、组织、凭据、审计
│   ├── permissions.py   # 权限判断
│   ├── crypto.py        # 加解密
│   ├── routes/          # 路由
│   └── templates/       # 页面
├── config.py
├── run.py
└── requirements.txt
```

## 安全提示

此为可运行的基础版本，生产部署请额外考虑：

- 启用 HTTPS
- 修改默认密码与密钥
- 使用 PostgreSQL 等生产数据库
- 增加登录失败锁定、2FA、密码强度策略
- 定期备份数据库

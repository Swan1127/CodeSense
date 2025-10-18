# 快速参考指南

## 🚀 新用户快速开始

### 1. 克隆项目
```bash
git clone https://gitee.com/your_username/codesense.git
cd codesense
```

### 2. 配置环境
```bash
# 使用快速启动脚本（推荐）
python scripts/quick_start.py

# 或手动配置
cp env.example .env
# 编辑 .env 文件填入配置
```

### 3. 安装依赖
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. 初始化数据库
```bash
python init_db.py
```

### 5. 启动应用
```bash
python app.py
# 访问 http://127.0.0.1:5000
```

---

## 🔑 环境变量快速配置

### 开发环境最小配置

```env
FLASK_CONFIG=development
SECRET_KEY=<运行以下命令生成>
```

生成SECRET_KEY：
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 生产环境完整配置

```env
FLASK_CONFIG=production
SECRET_KEY=<64位十六进制密钥>
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/student_code_review
ZHIPU_API_KEY=<你的智谱AI密钥>
SECURE_COOKIES=true
```

---

## 🛠️ 常用命令

### 开发环境

```bash
# 启动应用
python app.py

# 初始化数据库
python init_db.py

# 运行安全检查
python scripts/security_check.py

# 运行测试
python -m pytest tests/
```

### 生产环境（宝塔面板）

```bash
# 启动应用
pm2 start "gunicorn -c gunicorn_config.py wsgi:application" --name codesense

# 重启应用
pm2 restart codesense

# 查看日志
pm2 logs codesense
tail -f logs/app.log

# 查看状态
pm2 status
```

---

## 📁 项目结构速查

```
codesense/
├── app.py                    # 应用入口
├── config.py                 # 配置文件（已移除硬编码）
├── wsgi.py                   # WSGI入口
├── gunicorn_config.py        # Gunicorn配置
├── .env                      # 环境变量（不提交到Git）
├── env.example               # 环境变量模板
├── requirements.txt          # Python依赖
│
├── models/                   # 数据模型
├── routes/                   # 路由
├── services/                 # 业务逻辑
├── utils/                    # 工具函数
├── static/                   # 静态资源
├── templates/                # HTML模板
├── scripts/                  # 工具脚本
│   ├── security_check.py    # 安全检查
│   └── quick_start.py       # 快速启动
│
├── logs/                     # 日志目录
├── uploads/                  # 上传文件
├── flask_session/            # Session数据
│
├── DEPLOYMENT.md             # 部署指南
├── SECURITY.md               # 安全指南
├── README.md                 # 项目说明
└── CHANGELOG_SECURITY.md     # 安全更新日志
```

---

## 🔍 故障排查

### 问题：应用启动失败

```bash
# 检查环境变量
python scripts/security_check.py

# 查看错误日志
tail -f logs/error.log
```

### 问题：数据库连接失败

```bash
# 检查数据库配置
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('DATABASE_URL'))"

# 测试数据库连接
python -c "from app import app; from models import db; app.app_context().push(); db.engine.connect(); print('OK')"
```

### 问题：AI功能不可用

```bash
# 检查API密钥
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('ZHIPU:', 'SET' if os.getenv('ZHIPU_API_KEY') else 'NOT SET')"
```

### 问题：Session丢失

```bash
# 检查flask_session目录权限
ls -ld flask_session
chmod 755 flask_session
```

---

## 📚 文档导航

| 文档 | 说明 | 适用场景 |
|------|------|---------|
| [README.md](README.md) | 项目概述和基础说明 | 了解项目 |
| [DEPLOYMENT.md](DEPLOYMENT.md) | 详细部署指南 | 部署到服务器 |
| [SECURITY.md](SECURITY.md) | 安全配置最佳实践 | 安全配置 |
| [CHANGELOG_SECURITY.md](CHANGELOG_SECURITY.md) | 安全更新日志 | 了解变更 |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | 本文档 | 快速查阅 |

---

## 🔐 安全检查清单

### 推送到Git前

- [ ] `.env` 文件不在Git中（运行 `git status` 确认）
- [ ] 代码中无硬编码密码
- [ ] 已更新 `.gitignore`

### 部署到生产环境前

- [ ] 已设置强SECRET_KEY（至少32字符）
- [ ] 数据库密码不是默认值
- [ ] `.env` 文件权限为600
- [ ] 运行 `python scripts/security_check.py` 通过
- [ ] 已配置SSL证书
- [ ] `SECURE_COOKIES=true`
- [ ] 5000端口未对外开放

---

## 💡 实用技巧

### 生成强密码

```bash
# SECRET_KEY（64字符）
python -c "import secrets; print(secrets.token_hex(32))"

# 数据库密码（20字符）
python -c "import secrets, string; chars=string.ascii_letters+string.digits; print(''.join(secrets.choice(chars) for _ in range(20)))"
```

### 查看应用日志

```bash
# 实时查看所有日志
tail -f logs/*.log

# 只看错误
tail -f logs/error.log

# 查看最近100条访问日志
tail -n 100 logs/access.log
```

### 备份数据库

```bash
# MySQL备份
mysqldump -u username -p student_code_review > backup_$(date +%Y%m%d).sql

# 恢复
mysql -u username -p student_code_review < backup_20251017.sql
```

### 更新代码后

```bash
# 拉取最新代码
git pull origin main

# 更新依赖（如有变化）
pip install -r requirements.txt

# 重启应用
pm2 restart codesense

# 查看是否正常
pm2 logs codesense --lines 50
```

---

## ⚡ 性能优化提示

### Gunicorn Workers

```python
# 推荐配置（自动）
workers = CPU核心数 * 2 + 1

# 手动设置（gunicorn_config.py）
workers = 4  # 根据服务器配置调整
```

### 数据库连接池

```python
# config.py 或 .env
SQLALCHEMY_POOL_SIZE=10
SQLALCHEMY_MAX_OVERFLOW=20
```

### 静态文件缓存

```nginx
# Nginx配置
location /static {
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

---

## 🆘 获取帮助

1. **查看文档**：先查看 DEPLOYMENT.md 和 SECURITY.md
2. **运行诊断**：`python scripts/security_check.py`
3. **查看日志**：`tail -f logs/error.log`
4. **提交Issue**：在Gitee/GitHub提交问题
5. **联系支持**：查看README.md中的联系方式

---

## 🔄 版本信息

- **当前版本**：v0.2.1
- **最后更新**：2025-10-17
- **重要更新**：安全配置全面升级

---

## 📝 待办事项模板

开发环境：
- [ ] 克隆项目
- [ ] 创建 .env 文件
- [ ] 安装依赖
- [ ] 初始化数据库
- [ ] 启动应用

生产环境：
- [ ] 创建数据库
- [ ] 克隆代码到服务器
- [ ] 配置 .env
- [ ] 配置Gunicorn
- [ ] 配置Nginx
- [ ] 配置SSL
- [ ] 启动PM2
- [ ] 测试访问
- [ ] 配置备份

---

**💡 提示**：将此文档加入书签，方便随时查阅！


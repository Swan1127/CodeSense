# 安全配置升级变更日志

## v0.2.1 - 安全配置升级 (2025-10-17)

### 🔒 安全性改进

本次更新完全移除了代码中所有硬编码的敏感信息，采用环境变量管理所有配置。这是一次**重要的安全升级**，强烈建议所有用户更新。

### 主要变更

#### 1. 配置文件重构 (`config.py`)

**移除的硬编码信息：**
- ❌ `SECRET_KEY = 'dev'` （默认密钥）
- ❌ `OPENAI_API_KEY = 'your-api-key-here'` （示例API密钥）
- ❌ 数据库连接中的 `root:root` （硬编码密码）

**新的安全实现：**
- ✅ 所有敏感信息从环境变量读取
- ✅ 生产环境启动前进行配置完整性检查
- ✅ SECRET_KEY 强度验证（至少32字符）
- ✅ 开发环境自动生成临时密钥（不影响开发体验）
- ✅ 生产环境强制使用强密钥和安全配置

**改进的配置类：**

```python
# 之前（不安全）
SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev'
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:root@localhost/...'

# 现在（安全）
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    # 开发环境自动生成，生产环境会在init_app中检查
    SECRET_KEY = secrets.token_hex(32)

SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
# 生产环境如果未设置会抛出明确的错误
```

#### 2. 新增配置文件

| 文件 | 说明 |
|------|------|
| `env.example` | 环境变量配置模板（可提交到Git） |
| `DEPLOYMENT.md` | 详细的部署指南，包含宝塔面板部署步骤 |
| `SECURITY.md` | 安全配置最佳实践和应急响应指南 |
| `gunicorn_config.py` | 生产环境Gunicorn配置 |
| `CHANGELOG_SECURITY.md` | 本变更日志 |

#### 3. 新增工具脚本

| 脚本 | 功能 |
|------|------|
| `scripts/security_check.py` | 自动检查安全配置是否正确 |
| `scripts/quick_start.py` | 快速配置开发环境 |

#### 4. 更新的文件

**`.gitignore`**
- 明确排除 `.env`、`.env.local`、`.env.production` 等敏感文件
- 添加 `!env.example` 允许模板文件提交

**`README.md`**
- 添加安全配置提示
- 更新安装步骤，引导用户配置环境变量
- 添加到部署和安全文档的链接

### 升级指南

#### 对于新用户

1. 克隆代码后，复制环境变量模板：
   ```bash
   cp env.example .env
   ```

2. 生成安全密钥：
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. 编辑 `.env` 文件，填入密钥和其他配置

4. 运行安全检查：
   ```bash
   python scripts/security_check.py
   ```

5. 或使用快速启动脚本自动配置：
   ```bash
   python scripts/quick_start.py
   ```

#### 对于现有用户

1. **更新代码**：
   ```bash
   git pull origin main
   ```

2. **创建 `.env` 文件**：
   ```bash
   cp env.example .env
   ```

3. **迁移现有配置**：
   
   如果你之前在 `config.py` 中修改了配置，现在需要移到 `.env`：
   
   ```bash
   # 之前在 config.py 中
   SECRET_KEY = 'my-secret-key'
   SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://user:pass@localhost/db'
   
   # 现在在 .env 中
   SECRET_KEY=my-secret-key
   DATABASE_URL=mysql+pymysql://user:pass@localhost/db
   ```

4. **生成新的强密钥**（推荐）：
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   
   将生成的密钥填入 `.env` 文件

5. **验证配置**：
   ```bash
   python scripts/security_check.py
   ```

6. **重启应用**：
   ```bash
   pm2 restart codesense
   # 或
   python app.py
   ```

### 环境变量对照表

| 旧配置位置 | 新环境变量 | 必需 |
|-----------|-----------|------|
| `Config.SECRET_KEY` | `SECRET_KEY` | 生产必需 |
| `DevelopmentConfig.SQLALCHEMY_DATABASE_URI` | `DEV_DATABASE_URL` | 否（默认SQLite） |
| `ProductionConfig.SQLALCHEMY_DATABASE_URI` | `DATABASE_URL` | 生产必需 |
| `Config.OPENAI_API_KEY` | `OPENAI_API_KEY` | 否（AI功能） |
| 新增 | `ZHIPU_API_KEY` | 否（AI功能） |
| 新增 | `SECURE_COOKIES` | 生产推荐 |
| 新增 | `FLASK_CONFIG` | 否（默认development） |

### 破坏性变更

⚠️ **注意：** 以下行为已改变：

1. **生产环境强制检查**
   - 之前：缺少配置会使用默认值
   - 现在：缺少必需配置会拒绝启动，并显示明确错误信息

2. **开发环境数据库**
   - 之前：默认使用 MySQL (`root:root@localhost`)
   - 现在：默认使用 SQLite（更方便开发）
   - 如需 MySQL：在 `.env` 中设置 `DEV_DATABASE_URL`

3. **SECRET_KEY**
   - 之前：默认 `'dev'`
   - 现在：开发环境自动生成随机密钥，生产环境必须显式设置

### 安全检查清单

部署前请确认：

- [ ] 已创建 `.env` 文件
- [ ] `SECRET_KEY` 至少32个字符（生产环境至少64字符）
- [ ] 数据库密码不是默认值
- [ ] `.env` 文件不在Git仓库中
- [ ] `.env` 文件权限设置为 600（Linux/Mac）
- [ ] 运行 `python scripts/security_check.py` 全部通过
- [ ] 生产环境设置 `FLASK_CONFIG=production`
- [ ] 生产环境设置 `SECURE_COOKIES=true`（启用HTTPS后）

### 性能改进

1. **配置初始化优化**
   - 环境变量只读取一次
   - 开发环境减少不必要的检查

2. **Gunicorn配置**
   - 自动计算最优worker数量
   - 配置worker重启策略防止内存泄漏
   - 优化超时设置适应AI调用

### 文档更新

- 📖 新增 `DEPLOYMENT.md` - 完整的部署指南
- 🔒 新增 `SECURITY.md` - 安全最佳实践
- 📝 更新 `README.md` - 添加环境配置说明
- 🔧 新增 `gunicorn_config.py` - 生产环境服务器配置

### 工具和脚本

- 🛠️ `scripts/security_check.py` - 安全配置验证工具
- 🚀 `scripts/quick_start.py` - 开发环境快速配置工具

### 向后兼容性

虽然配置方式改变了，但应用功能保持完全兼容：

- ✅ 所有现有功能正常工作
- ✅ 数据库结构无变化
- ✅ API接口无变化
- ✅ 前端无需修改

### 已知问题

无

### 致谢

感谢所有关注项目安全的用户和贡献者。

### 获取帮助

如遇到问题：

1. 查看 `DEPLOYMENT.md` 部署指南
2. 查看 `SECURITY.md` 安全配置说明
3. 运行 `python scripts/security_check.py` 诊断问题
4. 查看 `logs/error.log` 错误日志
5. 提交 Issue 到项目仓库

---

**重要提醒：**
- 永远不要将 `.env` 文件提交到 Git
- 定期更新 `SECRET_KEY` 和数据库密码
- 保持依赖包版本最新以修复安全漏洞


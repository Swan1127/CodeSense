# 部署指南

## 环境变量配置

本项目已移除所有硬编码的敏感信息，所有配置通过环境变量管理。

### 快速开始

#### 1. 创建环境变量文件

```bash
# 复制模板文件
cp env.example .env

# 编辑配置文件
nano .env  # 或使用其他编辑器
```

#### 2. 生成安全的SECRET_KEY

```bash
# 使用Python生成强密钥
python -c "import secrets; print(secrets.token_hex(32))"
```

将生成的密钥复制到 `.env` 文件中的 `SECRET_KEY` 字段。

#### 3. 配置数据库

根据你的环境选择合适的配置：

**开发环境（使用SQLite）：**
```env
FLASK_CONFIG=development
# 不设置DATABASE_URL，将自动使用SQLite
```

**开发环境（使用MySQL）：**
```env
FLASK_CONFIG=development
DEV_DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/student_code_review
```

**生产环境（必须使用MySQL）：**
```env
FLASK_CONFIG=production
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/student_code_review
SECRET_KEY=你生成的64位十六进制密钥
SECURE_COOKIES=true
```

#### 4. 配置AI API密钥

从以下渠道获取API密钥：
- **智谱AI**（推荐）: https://open.bigmodel.cn/
- **OpenAI**: https://platform.openai.com/

```env
ZHIPU_API_KEY=your_actual_api_key_here
```

### 环境变量说明

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `FLASK_CONFIG` | 否 | development | 运行环境：development/testing/production |
| `SECRET_KEY` | 生产必需 | 自动生成（开发） | Flask应用密钥，至少32个字符 |
| `DATABASE_URL` | 生产必需 | - | 生产环境数据库连接URI |
| `DEV_DATABASE_URL` | 否 | SQLite | 开发环境数据库连接URI |
| `ZHIPU_API_KEY` | AI功能必需 | - | 智谱AI API密钥 |
| `OPENAI_API_KEY` | AI功能可选 | - | OpenAI API密钥（备选） |
| `SECURE_COOKIES` | 否 | false | 生产环境HTTPS启用时设为true |

## 宝塔面板部署步骤

### 1. 准备服务器环境

在宝塔面板安装：
- Python 3.8+
- MySQL 5.7+
- Nginx
- Python项目管理器（或PM2）

### 2. 创建数据库

宝塔面板 → 数据库 → 添加数据库：
```
数据库名：student_code_review
用户名：codesense_user（建议不使用root）
密码：设置强密码
访问权限：本地服务器
```

### 3. 克隆项目

SSH连接到服务器：
```bash
cd /www/wwwroot
git clone https://gitee.com/your_username/your_repo.git codesense
cd codesense
```

### 4. 配置环境变量

创建 `.env` 文件：
```bash
nano .env
```

填入配置（**务必修改为实际值**）：
```env
FLASK_CONFIG=production
SECRET_KEY=使用python命令生成的64位密钥
DATABASE_URL=mysql+pymysql://codesense_user:数据库密码@localhost:3306/student_code_review
ZHIPU_API_KEY=你的智谱AI密钥
SECURE_COOKIES=true
```

**安全提示：** 确保 `.env` 文件权限设置正确：
```bash
chmod 600 .env  # 只有所有者可读写
```

### 5. 安装依赖

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install gunicorn
```

### 6. 初始化数据库

```bash
python init_db.py
```

### 7. 配置Gunicorn

创建 `gunicorn_config.py`：
```python
import multiprocessing
import os

bind = "127.0.0.1:5000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
timeout = 120
keepalive = 5

accesslog = "logs/gunicorn_access.log"
errorlog = "logs/gunicorn_error.log"
loglevel = "info"

proc_name = "codesense"
preload_app = True
daemon = False
```

### 8. 配置Nginx反向代理

在宝塔面板 → 网站 → 你的站点 → 配置文件，添加：

```nginx
location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    proxy_connect_timeout 120s;
    proxy_read_timeout 120s;
    proxy_send_timeout 120s;
}

location /static {
    alias /www/wwwroot/codesense/static;
    expires 30d;
}
```

### 9. 使用PM2管理进程

```bash
# 安装PM2
npm install -g pm2

# 启动应用
cd /www/wwwroot/codesense
source venv/bin/activate
pm2 start "gunicorn -c gunicorn_config.py wsgi:application" --name codesense

# 设置开机自启
pm2 startup
pm2 save

# 查看状态
pm2 status
pm2 logs codesense
```

### 10. 配置SSL证书

宝塔面板 → 网站 → SSL：
- 申请Let's Encrypt免费证书
- 开启强制HTTPS

### 11. 设置权限

```bash
cd /www/wwwroot/codesense

# 确保必要目录可写
chmod 755 logs uploads flask_session
chown -R www:www logs uploads flask_session

# 确保.env文件安全
chmod 600 .env
```

## 更新部署

当代码更新时：

```bash
cd /www/wwwroot/codesense

# 拉取最新代码
git pull origin main

# 更新依赖（如有变化）
source venv/bin/activate
pip install -r requirements.txt

# 重启应用
pm2 restart codesense

# 查看日志
pm2 logs codesense
```

## 故障排查

### 1. 检查环境变量是否加载

```bash
cd /www/wwwroot/codesense
source venv/bin/activate
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('SECRET_KEY:', 'SET' if os.getenv('SECRET_KEY') else 'NOT SET'); print('DATABASE_URL:', 'SET' if os.getenv('DATABASE_URL') else 'NOT SET')"
```

### 2. 检查数据库连接

```bash
python -c "from app import app; from models import db; app.app_context().push(); db.engine.connect(); print('Database connected successfully')"
```

### 3. 查看应用日志

```bash
# 应用日志
tail -f logs/app.log

# Gunicorn日志
tail -f logs/gunicorn_error.log

# PM2日志
pm2 logs codesense
```

### 4. 检查进程状态

```bash
# 查看PM2进程
pm2 status

# 查看端口占用
netstat -tlnp | grep 5000

# 查看Nginx状态
systemctl status nginx
```

## 安全检查清单

部署完成后，请确认：

- [ ] `.env` 文件不在Git仓库中
- [ ] `.env` 文件权限为 600
- [ ] SECRET_KEY 已设置为强密钥（至少32个字符）
- [ ] 数据库密码已修改为强密码
- [ ] 5000端口未在防火墙开放
- [ ] 已启用SSL证书（HTTPS）
- [ ] SECURE_COOKIES 已设置为 true
- [ ] 定期备份数据库
- [ ] 日志轮转正常工作

## 监控与维护

### 性能监控

使用宝塔面板的监控功能：
- CPU/内存使用率
- 磁盘空间
- 网络流量

### 日志管理

应用已配置日志轮转：
- `logs/app.log` - 每天轮转，保留30天
- `logs/error.log` - 按10MB轮转，保留5份
- `logs/access.log` - 每天轮转，保留7天

### 备份策略

建议备份：
1. 数据库（每天自动备份）
2. 上传的文件 `uploads/`
3. 环境变量文件 `.env`（加密保存）

宝塔面板 → 计划任务 → 添加备份任务

## 常见问题

**Q: 忘记设置SECRET_KEY会怎样？**  
A: 开发环境会自动生成临时密钥；生产环境会抛出错误拒绝启动。

**Q: 可以在代码中看到数据库密码吗？**  
A: 不能。所有敏感信息都在 `.env` 文件中，该文件不会提交到Git。

**Q: 如何切换AI API提供商？**  
A: 在 `.env` 中设置 `ZHIPU_API_KEY` 或 `OPENAI_API_KEY`，应用会自动选择可用的。

**Q: 开发环境需要配置.env吗？**  
A: 不是必须的。不配置会使用SQLite和临时密钥，但建议配置以保持环境一致。

## 获取帮助

如遇到问题：
1. 查看 `logs/error.log`
2. 检查环境变量配置
3. 确认数据库连接
4. 查看GitHub Issues

---

**重要提醒：** 
- 永远不要将 `.env` 文件提交到Git
- 定期更新依赖包以修复安全漏洞
- 保持数据库备份习惯


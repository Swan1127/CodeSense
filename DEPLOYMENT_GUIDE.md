# CodeSense 云端部署优化指南

## 已完成的优化

### 1. ✅ .gitignore 检查
你的 `.gitignore` 已经包含了所有必要的敏感文件忽略规则：
- `.env` 及其变体被正确忽略
- 缓存、日志、IDE配置都被排除
- 这防止了本地配置被意外上传到 GitHub

### 2. ✅ 创建 `.env.example`
**文件位置**: `e:\CodeSense\源代码\.env.example`

这是一个不含敏感信息的环境变量模板，包含：
- 数据库配置示例
- API 密钥占位符
- 应用配置参数
- 模型加载开关

**使用方法**:
```bash
# 云端首次部署
cp .env.example .env
# 然后编辑 .env 填入实际的数据库地址、API密钥等
```

### 3. ✅ 创建 `update.sh` 一键更新脚本
**文件位置**: `e:\CodeSense\源代码\update.sh`

自动化云端更新流程：
```bash
bash update.sh
```

脚本会自动执行：
1. `git pull origin main` - 拉取最新代码
2. `pip install -r requirements.txt --no-cache-dir` - 更新依赖（2G内存优化）
3. `sudo systemctl restart codesense` - 重启服务
4. `systemctl status codesense` - 检查服务状态

### 4. ✅ 创建 `deploy.sh` 首次部署脚本
**文件位置**: `e:\CodeSense\源代码\deploy.sh`

云端首次部署使用：
```bash
bash deploy.sh
```

脚本会自动执行：
1. 检查/创建 `.env` 文件
2. 创建 Python 虚拟环境
3. 安装所有依赖
4. 初始化数据库
5. 创建必要的目录

### 5. ✅ 代码中的模型加载优化
**修改文件**: `app.py`

添加了 `LOAD_LOCAL_MODEL` 环境变量开关：

```python
load_local_model = os.getenv('LOAD_LOCAL_MODEL', 'False').lower() == 'true'

if load_local_model:
    # 加载本地模型（需要 2GB+ 内存）
    initialize_models()
    initialize_guidance_system()
    initialize_code_advisor()
else:
    # API-only 模式（节省 1GB+ 内存）
    print("✓ 运行在 API-only 模式，跳过本地模型加载以节省内存")
```

**云端配置**:
```env
# .env 中设置
LOAD_LOCAL_MODEL=False
```

这样云端 2G 内存的服务器就不会因为加载大模型而崩溃。

---

## 云端部署流程

### 首次部署（新服务器）
```bash
# 1. 克隆仓库
git clone <your-repo-url>
cd 源代码

# 2. 运行首次部署脚本
bash deploy.sh

# 3. 编辑 .env 配置
nano .env
# 填入：数据库地址、SECRET_KEY、API密钥等

# 4. 测试运行
python app.py

# 5. 配置 Systemd 服务（生产环境）
sudo nano /etc/systemd/system/codesense.service
# 配置服务文件后：
sudo systemctl daemon-reload
sudo systemctl enable codesense
sudo systemctl start codesense
```

### 后续更新（已部署的服务器）
```bash
cd /path/to/codesense
bash update.sh
```

---

## 关键配置说明

### .env 必填项
```env
# 数据库（必填）
DATABASE_URL='mysql+pymysql://user:password@host:3306/dbname'

# 应用密钥（必填，生产环境至少32个字符）
SECRET_KEY='your_secret_key_here'

# AI API（至少配置一个）
ZHIPU_API_KEY='your_key'
OPENAI_API_KEY='your_key'

# 云端 2G 内存必须设置
LOAD_LOCAL_MODEL=False
```

### 数据库变量兼容性
代码已支持多种数据库变量名：
- `DATABASE_URL` ✓
- `DEV_DATABASE_URL` ✓
- 默认 `sqlite:///dev_student_code_review.db` ✓

### 内存优化
- **本地开发**: `LOAD_LOCAL_MODEL=True` - 加载所有本地模型
- **云端 2G**: `LOAD_LOCAL_MODEL=False` - 仅使用 API，节省 1GB+ 内存

---

## 故障排查

### 问题：云端 git pull 后配置被覆盖
**解决**: 确保 `.env` 在 `.gitignore` 中（已完成 ✓）

### 问题：内存不足导致服务崩溃
**解决**: 在 `.env` 中设置 `LOAD_LOCAL_MODEL=False`

### 问题：更新后服务无法启动
**解决**: 
```bash
# 查看日志
journalctl -u codesense -n 50

# 手动测试
python app.py
```

### 问题：数据库连接失败
**解决**: 检查 `.env` 中的 `DATABASE_URL` 是否正确

---

## 总结

✅ **已完成的优化**:
1. `.gitignore` 防止敏感文件上传
2. `.env.example` 提供配置模板
3. `update.sh` 一键更新脚本
4. `deploy.sh` 首次部署脚本
5. `app.py` 模型加载优化（内存节省）

🚀 **立即可用**:
- 本地开发: `LOAD_LOCAL_MODEL=True`
- 云端部署: `LOAD_LOCAL_MODEL=False`
- 更新: `bash update.sh`

# 安全配置指南

## 概述

本项目已完全移除硬编码的敏感信息，所有配置通过环境变量管理。本文档说明安全配置的最佳实践。

## 核心安全原则

### ✅ 已实施的安全措施

1. **环境变量管理**
   - 所有敏感配置从环境变量读取
   - `.env` 文件已加入 `.gitignore`
   - 提供 `env.example` 作为配置模板

2. **密钥管理**
   - `SECRET_KEY` 必须至少32个字符
   - 生产环境缺少密钥将拒绝启动
   - 开发环境自动生成临时密钥

3. **数据库安全**
   - 数据库凭证完全从环境变量读取
   - 不同环境使用独立配置
   - 生产环境强制检查配置完整性

4. **Session安全**
   - 生产环境启用 `SESSION_COOKIE_SECURE`（仅HTTPS）
   - 启用 `SESSION_COOKIE_HTTPONLY`（防止XSS）
   - 设置 `SESSION_COOKIE_SAMESITE`（防止CSRF）

5. **网络安全**
   - 应用绑定到 `127.0.0.1:5000`（不对外暴露）
   - 通过Nginx反向代理访问
   - 5000端口不在防火墙开放

## 配置安全检查

### 推送到Git前的检查

运行以下命令确保没有敏感信息被提交：

```bash
# 检查是否有.env文件被追踪
git status | grep ".env"

# 检查代码中是否还有硬编码密码（应该没有结果）
grep -r "password.*=.*['\"]" --include="*.py" . | grep -v "def\|#\|environ"

# 检查是否有API密钥被硬编码（应该没有结果）
grep -r "api.*key.*=.*['\"]" --include="*.py" . | grep -v "def\|#\|environ"

# 查看即将提交的文件
git diff --cached --name-only
```

### 部署前的安全检查

```bash
# 1. 检查.env文件存在且权限正确
test -f .env && echo "✅ .env文件存在" || echo "❌ .env文件不存在"
ls -l .env | grep "rw-------" && echo "✅ .env权限正确" || echo "⚠️  .env权限过宽"

# 2. 检查必需的环境变量
python3 << EOF
import os
from dotenv import load_dotenv
load_dotenv()

required = ['SECRET_KEY', 'DATABASE_URL', 'FLASK_CONFIG']
missing = [var for var in required if not os.getenv(var)]

if missing:
    print(f"❌ 缺少环境变量: {', '.join(missing)}")
else:
    print("✅ 必需的环境变量都已设置")

# 检查SECRET_KEY长度
secret_key = os.getenv('SECRET_KEY', '')
if len(secret_key) >= 32:
    print(f"✅ SECRET_KEY长度足够 ({len(secret_key)}字符)")
else:
    print(f"❌ SECRET_KEY长度不足 ({len(secret_key)}字符，至少需要32)")
EOF

# 3. 检查数据库连接
python3 -c "
from app import app
from models import db
try:
    with app.app_context():
        db.engine.connect()
    print('✅ 数据库连接成功')
except Exception as e:
    print(f'❌ 数据库连接失败: {e}')
"
```

## 生产环境部署清单

### 部署前

- [ ] 已创建 `.env` 文件并填写所有必需配置
- [ ] `SECRET_KEY` 已设置为强密钥（至少32字符）
- [ ] 数据库密码已修改为强密码（非默认）
- [ ] `.env` 文件权限设置为 `600`
- [ ] 已设置 `FLASK_CONFIG=production`
- [ ] 已配置AI API密钥（如需AI功能）
- [ ] `.env` 文件不在Git仓库中

### 服务器配置

- [ ] 应用绑定到 `127.0.0.1:5000`（不是 `0.0.0.0`）
- [ ] Nginx反向代理配置正确
- [ ] 5000端口未在防火墙开放
- [ ] SSL证书已配置（强制HTTPS）
- [ ] `SECURE_COOKIES=true` 已设置
- [ ] 日志目录有正确的写入权限
- [ ] uploads目录有正确的写入权限
- [ ] flask_session目录有正确的写入权限

### 数据库安全

- [ ] 数据库用户不使用root账户
- [ ] 数据库用户只有必需的权限
- [ ] 数据库密码为强密码
- [ ] 数据库只允许本地连接
- [ ] 已配置定期备份

### 持续监控

- [ ] 定期检查错误日志
- [ ] 监控磁盘空间（日志轮转正常）
- [ ] 监控进程状态
- [ ] 定期更新依赖包
- [ ] 定期备份数据

## 生成安全密钥

### SECRET_KEY

```bash
# 方法1：使用Python secrets模块（推荐）
python -c "import secrets; print(secrets.token_hex(32))"

# 方法2：使用openssl
openssl rand -hex 32

# 方法3：使用urandom
python -c "import os; print(os.urandom(32).hex())"
```

将生成的64位十六进制字符串设置为 `SECRET_KEY`。

### 数据库密码

```bash
# 生成20字符的随机密码
python -c "import secrets, string; chars=string.ascii_letters+string.digits+'!@#$%^&*'; print(''.join(secrets.choice(chars) for _ in range(20)))"
```

## 环境变量文件权限

### Linux/Mac

```bash
# 设置.env文件为只有所有者可读写
chmod 600 .env

# 验证权限
ls -l .env
# 应显示: -rw------- 1 user group ...
```

### Windows（宝塔面板）

```bash
# 在SSH中执行
chmod 600 .env

# 或通过宝塔文件管理器设置权限为600
```

## 敏感信息泄露预防

### Git提交前检查

安装pre-commit钩子来防止敏感信息泄露：

```bash
# 创建.git/hooks/pre-commit文件
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash

# 检查是否尝试提交.env文件
if git diff --cached --name-only | grep -q "^\.env$"; then
    echo "❌ 错误：不能提交.env文件！"
    exit 1
fi

# 检查是否有可疑的密码或密钥
if git diff --cached | grep -iE "(password|secret|api_key).*=.*['\"][^'\"]{8,}"; then
    echo "⚠️  警告：检测到可能的硬编码密码或密钥"
    echo "请确认是否为敏感信息"
    read -p "继续提交？(y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

exit 0
EOF

chmod +x .git/hooks/pre-commit
```

### 使用git-secrets（可选）

```bash
# 安装git-secrets
# Ubuntu/Debian
apt-get install git-secrets

# Mac
brew install git-secrets

# 配置
git secrets --register-aws
git secrets --install
git secrets --scan
```

## 应急响应

### 如果密钥泄露

1. **立即更改密钥**
   ```bash
   # 生成新密钥
   python -c "import secrets; print(secrets.token_hex(32))"
   
   # 更新.env文件
   nano .env
   
   # 重启应用
   pm2 restart codesense
   ```

2. **撤销泄露的密钥**
   - 如果是API密钥，立即在服务商控制台撤销
   - 生成新的API密钥并更新配置

3. **检查访问日志**
   ```bash
   # 检查是否有异常访问
   tail -n 1000 logs/access.log | grep -i "suspicious"
   ```

4. **如果密钥已提交到Git**
   ```bash
   # 从Git历史中移除（需要强制推送）
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch .env" \
     --prune-empty --tag-name-filter cat -- --all
   
   # 强制推送（警告：会改写历史）
   git push origin --force --all
   ```
   
   **注意**：Git历史改写是危险操作，确保团队成员都知道。已泄露的密钥即使从历史中移除，仍应视为已泄露。

## 安全配置验证脚本

创建 `scripts/security_check.py`：

```python
#!/usr/bin/env python3
"""安全配置检查脚本"""
import os
import sys
from dotenv import load_dotenv

def check_env_file():
    """检查.env文件"""
    if not os.path.exists('.env'):
        print("❌ .env 文件不存在")
        return False
    
    # 检查权限（仅Linux/Mac）
    if sys.platform != 'win32':
        stat_info = os.stat('.env')
        mode = oct(stat_info.st_mode)[-3:]
        if mode != '600':
            print(f"⚠️  .env 文件权限为 {mode}，建议设置为 600")
            return False
    
    print("✅ .env 文件存在且权限正确")
    return True

def check_env_vars():
    """检查环境变量"""
    load_dotenv()
    
    required = {
        'SECRET_KEY': 32,  # 最小长度
        'DATABASE_URL': 10,
        'FLASK_CONFIG': 1,
    }
    
    all_ok = True
    for var, min_len in required.items():
        value = os.getenv(var)
        if not value:
            print(f"❌ {var} 未设置")
            all_ok = False
        elif len(value) < min_len:
            print(f"❌ {var} 长度不足 ({len(value)}/{min_len})")
            all_ok = False
        else:
            print(f"✅ {var} 已正确设置")
    
    return all_ok

def check_production_config():
    """检查生产环境配置"""
    load_dotenv()
    
    if os.getenv('FLASK_CONFIG') != 'production':
        print("ℹ️  非生产环境，跳过生产环境检查")
        return True
    
    checks = [
        ('SECURE_COOKIES', 'true'),
        ('DATABASE_URL', 'mysql'),  # 生产环境应使用MySQL
    ]
    
    all_ok = True
    for var, expected in checks:
        value = os.getenv(var, '')
        if expected not in value.lower():
            print(f"⚠️  生产环境 {var} 配置可能不正确")
            all_ok = False
        else:
            print(f"✅ {var} 配置正确")
    
    return all_ok

def main():
    """主函数"""
    print("=" * 60)
    print("安全配置检查")
    print("=" * 60)
    
    checks = [
        check_env_file(),
        check_env_vars(),
        check_production_config(),
    ]
    
    print("=" * 60)
    if all(checks):
        print("✅ 所有检查通过")
        return 0
    else:
        print("❌ 存在安全配置问题，请修复")
        return 1

if __name__ == '__main__':
    sys.exit(main())
```

运行检查：
```bash
python scripts/security_check.py
```

## 总结

遵循以上安全实践，可以确保：
- ✅ 敏感信息不会泄露到Git仓库
- ✅ 生产环境使用强密钥和安全配置
- ✅ 数据库凭证得到妥善保护
- ✅ 应用不会直接暴露到公网
- ✅ 会话Cookie安全传输

如有任何安全问题，请立即处理并参考本文档的应急响应部分。


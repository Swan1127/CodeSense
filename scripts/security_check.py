#!/usr/bin/env python3
"""
安全配置检查脚本
用于验证部署前的安全配置是否正确
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
except ImportError:
    print("❌ python-dotenv 未安装，请运行: pip install python-dotenv")
    sys.exit(1)


def check_env_file():
    """检查.env文件是否存在及权限"""
    env_path = project_root / '.env'
    
    if not env_path.exists():
        print("❌ .env 文件不存在")
        print("   请复制 env.example 为 .env 并填写配置")
        return False
    
    # 检查权限（仅Linux/Mac）
    if sys.platform != 'win32':
        stat_info = env_path.stat()
        mode = oct(stat_info.st_mode)[-3:]
        if mode != '600':
            print(f"⚠️  .env 文件权限为 {mode}，建议设置为 600")
            print(f"   运行: chmod 600 {env_path}")
            # 不返回False，只是警告
    
    print("✅ .env 文件存在")
    return True


def check_env_vars():
    """检查必需的环境变量"""
    load_dotenv(project_root / '.env')
    
    required_vars = {
        'SECRET_KEY': 32,      # 最小长度32字符
        'FLASK_CONFIG': 1,     # 必须设置
    }
    
    # 根据环境添加额外检查
    flask_config = os.getenv('FLASK_CONFIG', 'development')
    if flask_config == 'production':
        required_vars['DATABASE_URL'] = 10
    
    all_ok = True
    for var, min_len in required_vars.items():
        value = os.getenv(var, '')
        if not value:
            print(f"❌ {var} 未设置")
            all_ok = False
        elif len(value) < min_len:
            print(f"❌ {var} 长度不足 (当前:{len(value)}字符, 最小:{min_len}字符)")
            all_ok = False
        else:
            # 不显示实际值，只显示长度
            print(f"✅ {var} 已设置 ({len(value)}字符)")
    
    return all_ok


def check_ai_config():
    """检查AI配置"""
    zhipu_key = os.getenv('ZHIPU_API_KEY', '')
    openai_key = os.getenv('OPENAI_API_KEY', '')
    
    if not zhipu_key and not openai_key:
        print("⚠️  未配置 AI API 密钥")
        print("   AI评估功能将不可用")
        print("   请设置 ZHIPU_API_KEY 或 OPENAI_API_KEY")
        return False
    
    if zhipu_key:
        print(f"✅ ZHIPU_API_KEY 已设置 ({len(zhipu_key)}字符)")
    if openai_key:
        print(f"✅ OPENAI_API_KEY 已设置 ({len(openai_key)}字符)")
    
    return True


def check_production_config():
    """检查生产环境特定配置"""
    flask_config = os.getenv('FLASK_CONFIG', 'development')
    
    if flask_config != 'production':
        print(f"ℹ️  当前环境: {flask_config} (非生产环境)")
        return True
    
    print("🔍 检查生产环境配置...")
    
    all_ok = True
    
    # 检查数据库URL
    db_url = os.getenv('DATABASE_URL', '')
    if 'mysql' not in db_url.lower():
        print("⚠️  生产环境建议使用 MySQL 数据库")
        all_ok = False
    else:
        print("✅ 使用 MySQL 数据库")
    
    # 检查SECURE_COOKIES
    secure_cookies = os.getenv('SECURE_COOKIES', 'false').lower()
    if secure_cookies != 'true':
        print("⚠️  生产环境应设置 SECURE_COOKIES=true (启用HTTPS后)")
    else:
        print("✅ SECURE_COOKIES 已启用")
    
    # 检查SECRET_KEY强度
    secret_key = os.getenv('SECRET_KEY', '')
    if len(secret_key) < 64:
        print(f"⚠️  SECRET_KEY 建议至少64字符 (当前:{len(secret_key)})")
        print("   生成强密钥: python -c \"import secrets; print(secrets.token_hex(32))\"")
        all_ok = False
    else:
        print(f"✅ SECRET_KEY 强度足够 ({len(secret_key)}字符)")
    
    return all_ok


def check_gitignore():
    """检查.gitignore是否包含敏感文件"""
    gitignore_path = project_root / '.gitignore'
    
    if not gitignore_path.exists():
        print("❌ .gitignore 文件不存在")
        return False
    
    with open(gitignore_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    required_ignores = ['.env', 'logs/', 'flask_session/', '*.log']
    missing = []
    
    for pattern in required_ignores:
        if pattern not in content:
            missing.append(pattern)
    
    if missing:
        print(f"⚠️  .gitignore 缺少以下规则: {', '.join(missing)}")
        return False
    
    print("✅ .gitignore 配置正确")
    return True


def check_git_status():
    """检查Git状态，确保敏感文件未被追踪"""
    try:
        import subprocess
        
        # 检查是否是Git仓库
        result = subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print("ℹ️  不是 Git 仓库，跳过 Git 检查")
            return True
        
        # 检查.env是否被追踪
        result = subprocess.run(
            ['git', 'ls-files', '.env'],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        if result.stdout.strip():
            print("❌ .env 文件被 Git 追踪！")
            print("   请运行: git rm --cached .env")
            return False
        
        print("✅ 敏感文件未被 Git 追踪")
        return True
        
    except FileNotFoundError:
        print("ℹ️  Git 未安装，跳过 Git 检查")
        return True


def check_database_connection():
    """检查数据库连接（可选）"""
    print("\n🔍 测试数据库连接...")
    
    try:
        # 动态导入，避免在没有数据库配置时报错
        from app import app
        from models import db
        
        with app.app_context():
            # 尝试连接数据库
            db.engine.connect()
        
        print("✅ 数据库连接成功")
        return True
        
    except ImportError as e:
        print(f"⚠️  无法导入应用模块: {e}")
        print("   跳过数据库连接测试")
        return True
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("   请检查 DATABASE_URL 配置")
        return False


def main():
    """主函数"""
    print("=" * 70)
    print("🔒 安全配置检查工具")
    print("=" * 70)
    print()
    
    # 执行所有检查
    checks = {
        "环境变量文件": check_env_file(),
        "环境变量配置": check_env_vars(),
        "AI API配置": check_ai_config(),
        "生产环境配置": check_production_config(),
        "Git忽略配置": check_gitignore(),
        "Git状态检查": check_git_status(),
    }
    
    # 可选检查（失败不影响结果）
    print()
    check_database_connection()
    
    # 总结
    print()
    print("=" * 70)
    print("📊 检查结果汇总")
    print("=" * 70)
    
    passed = sum(1 for v in checks.values() if v)
    total = len(checks)
    
    for name, result in checks.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name:20s} {status}")
    
    print("-" * 70)
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print()
        print("✅ 所有检查通过！可以安全部署")
        return 0
    else:
        print()
        print("❌ 存在配置问题，请修复后再部署")
        print()
        print("💡 提示:")
        print("  1. 确保已创建 .env 文件并填写所有必需配置")
        print("  2. 生成强密钥: python -c \"import secrets; print(secrets.token_hex(32))\"")
        print("  3. 检查数据库配置是否正确")
        print("  4. 确保 .env 文件不在 Git 仓库中")
        print()
        print("📖 详细文档: 参考 DEPLOYMENT.md 和 SECURITY.md")
        return 1


if __name__ == '__main__':
    sys.exit(main())

